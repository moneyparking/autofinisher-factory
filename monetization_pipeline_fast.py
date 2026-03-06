from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from competitor_intel import competitor_profile
from etsy_mcp_scraper import inspect_listing, scan_keywords as etsy_scan_keywords
from google_niche_scraper import scan_google_niches
from monetization_scorer import ranking_payload
from performance_intel import performance_feedback_score
from review_intel import review_intelligence
from niche_profit_engine import get_ebay_metrics
from fms_decision import aggregate_data_quality, decide_for_item, infer_source_quality
from fms_engine import compute_fms_components, compute_fms_score
from winner_duplicator import process_niche

BASE_DIR = Path("/home/agent/autofinisher-factory")
VERTICALS_PATH = Path(os.getenv("VERTICALS_PATH", str(BASE_DIR / "vertical_families.json")))
ACCEPTED_DIR = BASE_DIR / "niche_engine" / "accepted"
OUTPUT_PATH = ACCEPTED_DIR / "niche_package.json"
SEED_STATUS_PATH = ACCEPTED_DIR / "seed_statuses.json"
BATCH_PROGRESS_PATH = ACCEPTED_DIR / "batch_progress.json"
TARGET_COUNT = int(os.getenv("TARGET_COUNT", "15"))
GOOGLE_MAX_PAGES_FAST = int(os.getenv("GOOGLE_MAX_PAGES_FAST", "1"))
GOOGLE_REQUESTS_PER_SEED_MAX = int(os.getenv("GOOGLE_REQUESTS_PER_SEED_MAX", "1"))
MAX_GOOGLE_REQUESTS_PER_BATCH = int(os.getenv("MAX_GOOGLE_REQUESTS_PER_BATCH", "20"))
ETSY_REQUESTS_PER_SEED_MAX = int(os.getenv("ETSY_REQUESTS_PER_SEED_MAX", "1"))
ETSY_MAX_LISTINGS_FAST = int(os.getenv("ETSY_MAX_LISTINGS_FAST", "24"))
MAX_ETSY_REQUESTS_PER_BATCH = int(os.getenv("MAX_ETSY_REQUESTS_PER_BATCH", "40"))
MAX_SHORTLIST_PER_SEED = int(os.getenv("MAX_SHORTLIST_PER_SEED", "3"))
MAX_APPROVED_PER_VERTICAL = int(os.getenv("MAX_APPROVED_PER_VERTICAL", "14"))
MIN_MONETIZATION_SCORE = float(os.getenv("MIN_MONETIZATION_SCORE", "42.0"))
MIN_STR_FOR_ACCEPT = float(os.getenv("MIN_STR_FOR_ACCEPT", "15.0"))
MIN_SOLD_FOR_ACCEPT = int(os.getenv("MIN_SOLD_FOR_ACCEPT", "20"))
MIN_ACTIVE = int(os.getenv("MIN_ACTIVE", "8"))
MAX_ACTIVE = int(os.getenv("MAX_ACTIVE", "5000"))

# If true, evaluate ONLY the original seed keyword (no Google candidate expansion / no title-derived expansion).
MONEY_NICHE_HUNTER_DISABLE_EXPANSION = os.getenv("MONEY_NICHE_HUNTER_DISABLE_EXPANSION", "").strip().lower() in {"1", "true", "yes", "on"}
SCRAPER_RETRIES = int(os.getenv("SCRAPER_RETRIES", "2"))
SCRAPER_BACKOFF = float(os.getenv("SCRAPER_BACKOFF", "1.0"))
MAX_ETSY_INSPECT_PER_SEED = int(os.getenv("MAX_ETSY_INSPECT_PER_SEED", "0"))
MAX_NETWORK_FAILURES_PER_SEED = int(os.getenv("MAX_NETWORK_FAILURES_PER_SEED", "2"))


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


def load_verticals() -> list[dict[str, Any]]:
    if not VERTICALS_PATH.exists():
        return []
    payload = json.loads(VERTICALS_PATH.read_text(encoding="utf-8"))
    return [x for x in payload.get("vertical_families", []) if isinstance(x, dict)]


def total_seed_count(verticals: list[dict[str, Any]]) -> int:
    total = 0
    for vertical in verticals:
        seeds = vertical.get("seed_keywords", [])
        if isinstance(seeds, list):
            total += len(seeds)
    return total


def build_google_queries(seed: str) -> list[str]:
    return [f"{seed} etsy"]


def fallback_seed_variants(seed: str) -> list[str]:
    candidates = [
        seed,
        f"{seed} printable",
        f"{seed} template",
        f"{seed} bundle",
    ]
    out: list[str] = []
    seen = set()
    for cand in candidates:
        norm = normalize(cand)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        out.append(norm)
    return out[:MAX_SHORTLIST_PER_SEED]


def collect_google_candidates(seed: str) -> tuple[list[str], str, dict[str, Any]]:
    # If configured, skip expansion and keep only the original seed.
    if MONEY_NICHE_HUNTER_DISABLE_EXPANSION:
        return [normalize(seed)], "skipped", infer_source_quality(
            source_name="google",
            source_status="skipped",
            warnings=["expansion_disabled"],
        )

    try:
        response = scan_google_niches(
            build_google_queries(seed)[:GOOGLE_REQUESTS_PER_SEED_MAX],
            country="US",
            language="en",
            max_pages=GOOGLE_MAX_PAGES_FAST,
        )
    except Exception as exc:
        print(f"[monetization_pipeline_fast] Google scan failed for '{seed}': {exc}")
        return [], "timeout", infer_source_quality(
            source_name="google",
            source_status="failed",
            warnings=["timeout", "retry_exhausted"],
            failure_stage="request",
        )

    candidates: list[str] = []
    seen = set()
    request_meta_items: list[dict[str, Any]] = []
    for result in response.get("results", []):
        request_meta_items.extend(result.get("request_meta") or [])
        for cand in result.get("related_searches", []) + result.get("niche_candidates", []):
            norm = normalize(cand)
            if not norm or norm in seen:
                continue
            seen.add(norm)
            candidates.append(norm)

    final_status = "ok"
    retry_count = 0
    latency_ms = 0.0
    warnings: list[str] = []
    failure_stage = None
    for item in request_meta_items:
        meta = item.get("meta") if isinstance(item, dict) else {}
        if not isinstance(meta, dict):
            continue
        retry_count = max(retry_count, int(meta.get("retry_count") or 0))
        latency_ms += float(meta.get("latency_ms") or 0.0)
        for warning in meta.get("warnings") or []:
            value = str(warning or "")
            if value and value not in warnings:
                warnings.append(value)
        if str(meta.get("final_status") or "ok") == "failed":
            final_status = "failed"
            failure_stage = str(meta.get("failure_stage") or "request")

    if final_status == "failed":
        return [], "timeout", infer_source_quality(
            source_name="google",
            source_status="failed",
            warnings=warnings or ["timeout", "retry_exhausted"],
            retry_count=retry_count,
            latency_ms=latency_ms,
            failure_stage=failure_stage or "request",
        )

    completeness = "partial" if not candidates else "full"
    source_status = "partial" if not candidates else "ok"
    if not candidates and "empty_candidate_set" not in warnings:
        warnings.append("empty_candidate_set")
    return candidates[:MAX_SHORTLIST_PER_SEED], "ok", infer_source_quality(
        source_name="google",
        source_status=source_status,
        warnings=warnings,
        retry_count=retry_count,
        latency_ms=latency_ms,
        completeness=completeness,
    )


def collect_etsy_shortlist(seed: str, google_candidates: list[str]) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
    scan_terms = [seed][:ETSY_REQUESTS_PER_SEED_MAX]
    try:
        response = etsy_scan_keywords(scan_terms, max_listings_per_keyword=ETSY_MAX_LISTINGS_FAST)
    except Exception as exc:
        print(f"[monetization_pipeline_fast] Etsy scan failed for '{seed}': {exc}")
        return [], "timeout", infer_source_quality(
            source_name="etsy",
            source_status="failed",
            warnings=["timeout", "retry_exhausted"],
            failure_stage="request",
        )

    shortlist: list[dict[str, Any]] = []
    seen = set()
    retry_count = 0
    latency_ms = 0.0
    warnings: list[str] = []
    source_status = "ok"
    failure_stage = None
    for result in response.get("results", []):
        req_meta = result.get("request_meta") or {}
        if isinstance(req_meta, dict):
            retry_count = max(retry_count, int(req_meta.get("retry_count") or 0))
            latency_ms += float(req_meta.get("latency_ms") or 0.0)
            for warning in req_meta.get("warnings") or []:
                value = str(warning or "")
                if value and value not in warnings:
                    warnings.append(value)
            if str(req_meta.get("final_status") or "ok") == "failed":
                source_status = "failed"
                failure_stage = str(req_meta.get("failure_stage") or "request")

        keyword = normalize(result.get("keyword", ""))
        aggregates = result.get("aggregates", {})
        digital_share = float(aggregates.get("digital_share") or 0)
        median_price = aggregates.get("median_price")
        comp = competitor_profile(result.get("listings", []))
        if keyword and digital_share >= 0.15:
            if keyword not in seen:
                seen.add(keyword)
                shortlist.append({
                    "niche": keyword,
                    "etsy_search": result,
                    "competition": comp,
                    "trend_score": 50.0 + min(20.0, float(result.get("search_metadata", {}).get("total_results") or 0) / 500.0),
                })
        inspected = 0
        for listing in result.get("listings", [])[:5]:
            title = normalize(listing.get("title", ""))
            if not title or title in seen:
                continue
            if not listing.get("is_digital"):
                continue
            price_ok = median_price is None or float(median_price or 0) >= 3.0
            if digital_share >= 0.15 and price_ok:
                intel = {
                    "niche": title,
                    "etsy_search": result,
                    "competition": comp,
                    "trend_score": 50.0 + min(20.0, float(result.get("search_metadata", {}).get("total_results") or 0) / 500.0),
                }
                if listing.get("url") and inspected < MAX_ETSY_INSPECT_PER_SEED:
                    try:
                        details = inspect_listing(listing["url"], max_reviews=5)
                        intel["etsy_listing"] = details
                        intel["review"] = review_intelligence(details.get("reviews", {}).get("sample", []))
                    except Exception as exc:
                        print(f"[monetization_pipeline_fast] Etsy inspect failed for '{title}': {exc}")
                    inspected += 1
                seen.add(title)
                shortlist.append(intel)
        if len(shortlist) >= MAX_SHORTLIST_PER_SEED:
            break

    if source_status == "failed":
        return [], "timeout", infer_source_quality(
            source_name="etsy",
            source_status="failed",
            warnings=warnings or ["timeout", "retry_exhausted"],
            retry_count=retry_count,
            latency_ms=latency_ms,
            failure_stage=failure_stage or "request",
        )

    completeness = "full"
    final_source_status = "ok"
    if not shortlist:
        if "empty_shortlist" not in warnings:
            warnings.append("empty_shortlist")
        completeness = "partial"
        final_source_status = "partial"
    return shortlist[:MAX_SHORTLIST_PER_SEED], "ok", infer_source_quality(
        source_name="etsy",
        source_status=final_source_status,
        warnings=warnings,
        retry_count=retry_count,
        latency_ms=latency_ms,
        completeness=completeness,
    )


def ebay_metrics_with_retry(keyword: str) -> tuple[dict[str, Any], dict[str, Any]]:
    last_exc: Exception | None = None
    started_at = time.monotonic()
    for attempt in range(SCRAPER_RETRIES + 1):
        try:
            metrics = get_ebay_metrics(keyword)
            latency_ms = (time.monotonic() - started_at) * 1000.0
            quality = infer_source_quality(
                source_name="ebay",
                source_status="ok",
                retry_count=attempt,
                latency_ms=latency_ms,
            )
            return metrics, quality
        except Exception as exc:
            last_exc = exc
            if attempt < SCRAPER_RETRIES:
                sleep_for = SCRAPER_BACKOFF * (attempt + 1)
                print(f"[monetization_pipeline_fast] eBay retry {attempt + 1}/{SCRAPER_RETRIES} for '{keyword}': {exc}")
                time.sleep(sleep_for)
                continue
            latency_ms = (time.monotonic() - started_at) * 1000.0
            quality = infer_source_quality(
                source_name="ebay",
                source_status="failed",
                warnings=["timeout", "retry_exhausted"],
                retry_count=attempt,
                latency_ms=latency_ms,
                failure_stage="request",
            )
            if last_exc is not None:
                raise RuntimeError(json.dumps({"message": str(last_exc), "source_quality": quality}, ensure_ascii=False)) from last_exc
    return {"active": 0, "sold": 0}, infer_source_quality(source_name="ebay", source_status="failed", warnings=["unknown_failure"], failure_stage="request")


def batch_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"monetization_batch_fast_{stamp}"


def etsy_signal_summary(niche_ctx: dict[str, Any]) -> dict[str, Any]:
    etsy_search = niche_ctx.get("etsy_search") or {}
    aggregates = etsy_search.get("aggregates") or {}
    search_metadata = etsy_search.get("search_metadata") or {}
    total_results = search_metadata.get("total_results")
    return {
        "digital_share": aggregates.get("digital_share", search_metadata.get("digital_share")),
        "total_results": total_results,
        "avg_reviews_top": (niche_ctx.get("competition") or {}).get("avg_reviews_top"),
    }


def decision_for_item(item: dict[str, Any]) -> dict[str, Any]:
    return decide_for_item(
        item,
        min_monetization_score=MIN_MONETIZATION_SCORE,
        min_str_for_accept=MIN_STR_FOR_ACCEPT,
        min_sold_for_accept=MIN_SOLD_FOR_ACCEPT,
        min_active=MIN_ACTIVE,
        max_active=MAX_ACTIVE,
    )


def write_batch_progress(batch_id: str, batch_stats: dict[str, Any], *, processed_seeds: int, total_seeds_planned: int, batch_status: str) -> dict[str, Any]:
    ACCEPTED_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": now_iso(),
        "batch_id": batch_id,
        "batch_status": batch_status,
        "processed_seeds": int(processed_seeds),
        "total_seeds": int(total_seeds_planned),
        "batch_stats": batch_stats,
        "network_fail_ratio": round(float(batch_stats.get("network_fail_seeds", 0)) / max(1, int(processed_seeds or 0)), 4),
    }
    BATCH_PROGRESS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def collect_candidates() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    approved: list[dict[str, Any]] = []
    global_seen = set()
    google_requests_used = 0
    etsy_requests_used = 0
    current_batch_id = batch_id()
    seed_statuses: list[dict[str, Any]] = []
    verticals = load_verticals()
    total_seeds_planned = total_seed_count(verticals)
    processed_seeds = 0
    batch_stats = {
        "batch_id": current_batch_id,
        "google_requests_used": 0,
        "google_successes": 0,
        "etsy_requests_used": 0,
        "etsy_successes": 0,
        "ebay_requests_used": 0,
        "ebay_successes": 0,
        "network_fail_seeds": 0,
        "total_seeds": 0,
        "total_seeds_planned": total_seeds_planned,
        "winner_count": 0,
        "candidate_count": 0,
        "rejected_count": 0,
        "batch_status": "running",
    }
    write_batch_progress(current_batch_id, batch_stats, processed_seeds=processed_seeds, total_seeds_planned=total_seeds_planned, batch_status="running")

    for vertical in verticals:
        vertical_name = str(vertical.get("name", "general"))
        vertical_approved = 0

        for seed_entry in vertical.get("seed_keywords", []):
            if len(approved) >= TARGET_COUNT:
                batch_stats["batch_status"] = "completed"
                write_seed_statuses(seed_statuses, batch_stats, processed_seeds=processed_seeds, total_seeds_planned=total_seeds_planned, batch_status="completed")
                write_batch_progress(current_batch_id, batch_stats, processed_seeds=processed_seeds, total_seeds_planned=total_seeds_planned, batch_status="completed")
                return approved[:TARGET_COUNT], batch_stats
            if vertical_approved >= MAX_APPROVED_PER_VERTICAL:
                break

            bucket = None
            seed_value = seed_entry
            if isinstance(seed_entry, dict):
                seed_value = seed_entry.get("seed")
                bucket = seed_entry.get("bucket")
            seed = normalize(seed_value)
            if not seed:
                continue

            batch_stats["total_seeds"] += 1
            print(f"[monetization_pipeline_fast] seed: {seed} ({vertical_name})")
            seed_record = {
                "seed": seed,
                "vertical": vertical_name,
                "bucket": bucket,
                "batch_id": current_batch_id,
                "google_status": "skipped_budget",
                "etsy_status": "skipped_budget",
                "status": "ok",
                "reason": "seed_processed",
                "decision_type": "seed_processed",
                "reason_code": "seed_processed",
                "reason_detail": "",
                "source_quality": {
                    "google": infer_source_quality(source_name="google", source_status="partial", completeness="empty", warnings=["skipped_budget"]),
                    "etsy": infer_source_quality(source_name="etsy", source_status="partial", completeness="empty", warnings=["skipped_budget"]),
                },
                "data_quality": {},
                "niche_decisions": [],
            }
            network_failures = 0
            google_candidates: list[str] = []
            shortlist: list[dict[str, Any]] = []

            if google_requests_used < MAX_GOOGLE_REQUESTS_PER_BATCH:
                google_requests_used += 1
                batch_stats["google_requests_used"] += 1
                google_candidates, google_status, google_quality = collect_google_candidates(seed)
                seed_record["google_status"] = google_status
                seed_record.setdefault("source_quality", {})["google"] = google_quality
                if google_status == "ok":
                    batch_stats["google_successes"] += 1
                else:
                    network_failures += 1

            if etsy_requests_used < MAX_ETSY_REQUESTS_PER_BATCH:
                etsy_requests_used += 1
                batch_stats["etsy_requests_used"] += 1
                shortlist, etsy_status, etsy_quality = collect_etsy_shortlist(seed, google_candidates)
                seed_record["etsy_status"] = etsy_status
                seed_record.setdefault("source_quality", {})["etsy"] = etsy_quality
                if etsy_status == "ok":
                    batch_stats["etsy_successes"] += 1
                else:
                    network_failures += 1

            if network_failures >= MAX_NETWORK_FAILURES_PER_SEED:
                seed_record["status"] = "uncertain"
                seed_record["reason"] = "network_timeouts_google_etsy"
                seed_record["decision_type"] = "data_reject"
                seed_record["reason_code"] = "data_reject_multi_source_failed"
                seed_record["reason_detail"] = "critical_seed_sources_failed"
                seed_record["data_quality"] = aggregate_data_quality(seed_record.get("source_quality") or {})
                batch_stats["network_fail_seeds"] += 1
                seed_statuses.append(seed_record)
                processed_seeds += 1
                write_seed_statuses(seed_statuses, batch_stats, processed_seeds=processed_seeds, total_seeds_planned=total_seeds_planned, batch_status="running")
                write_batch_progress(current_batch_id, batch_stats, processed_seeds=processed_seeds, total_seeds_planned=total_seeds_planned, batch_status="running")
                continue

            if not shortlist:
                shortlist = [{"niche": niche, "trend_score": 50.0} for niche in fallback_seed_variants(seed)]
                seed_record["status"] = "partial_ok"
                seed_record["reason"] = "fallback_seed_variants_used"
            elif seed_record["google_status"] != "ok" or seed_record["etsy_status"] != "ok":
                seed_record["status"] = "partial_ok"
                seed_record["reason"] = "partial_network_degradation"

            if not any(normalize(x.get("niche", "")) == seed for x in shortlist):
                shortlist = [{"niche": seed, "trend_score": 50.0}] + shortlist
            shortlist = shortlist[:MAX_SHORTLIST_PER_SEED]

            for niche_ctx in shortlist:
                if len(approved) >= TARGET_COUNT:
                    break
                if vertical_approved >= MAX_APPROVED_PER_VERTICAL:
                    break
                niche = normalize(niche_ctx.get("niche", ""))
                if not niche or niche in global_seen:
                    continue
                global_seen.add(niche)

                try:
                    batch_stats["ebay_requests_used"] += 1
                    metrics, ebay_quality = ebay_metrics_with_retry(niche)
                    batch_stats["ebay_successes"] += 1
                except Exception as exc:
                    print(f"[monetization_pipeline_fast] eBay validation failed for '{niche}': {exc}")
                    try:
                        exc_payload = json.loads(str(exc))
                        ebay_quality = exc_payload.get("source_quality") or infer_source_quality(source_name="ebay", source_status="failed", warnings=["unknown_failure"], failure_stage="request")
                    except Exception:
                        ebay_quality = infer_source_quality(source_name="ebay", source_status="failed", warnings=["unknown_failure"], failure_stage="request")
                    seed_record["niche_decisions"].append({
                        "niche": niche,
                        "status": "uncertain",
                        "decision_type": "data_reject",
                        "reason": "ebay_validation_failed",
                        "reason_code": "data_reject_ebay_failed",
                        "reason_detail": "ebay_validation_failed",
                        "source_quality": {"ebay": ebay_quality},
                        "data_quality": aggregate_data_quality({"ebay": ebay_quality}),
                    })
                    continue

                active = int(metrics.get("active", 0) or 0)
                sold = int(metrics.get("sold", 0) or 0)
                str_value = round((sold / active) * 100, 2) if active > 0 else 0.0
                comp = niche_ctx.get("competition") or {}
                review = niche_ctx.get("review") or {}
                intel = {
                    "trend_score": niche_ctx.get("trend_score", 50.0),
                    "review_opportunity_score": review.get("review_opportunity_score", 50.0),
                    "competition_profile_score": comp.get("competition_profile_score", 50.0),
                    "performance_feedback_score": performance_feedback_score(niche, vertical_name),
                    "review": review,
                    "competition": comp,
                    "etsy_search": niche_ctx.get("etsy_search"),
                    "etsy_listing": niche_ctx.get("etsy_listing"),
                }
                source_quality = {
                    "google": seed_record.get("source_quality", {}).get("google") or infer_source_quality(source_name="google", source_status="partial", completeness="empty", warnings=["missing_source_quality"]),
                    "etsy": seed_record.get("source_quality", {}).get("etsy") or infer_source_quality(source_name="etsy", source_status="partial", completeness="empty", warnings=["missing_source_quality"]),
                    "ebay": ebay_quality,
                }
                item = {
                    "niche": niche,
                    "vertical": vertical_name,
                    "bucket": bucket,
                    "trend_score": niche_ctx.get("trend_score", 50.0),
                    "seed_status": seed_record["status"],
                    "google_status": seed_record["google_status"],
                    "etsy_status": seed_record["etsy_status"],
                    "google_queries": build_google_queries(seed),
                    "google_candidate_count": len(google_candidates),
                    "source_quality": source_quality,
                    "data_quality": aggregate_data_quality(source_quality),
                    "intel": intel,
                    "metrics": {
                        "active_listings": active,
                        "sold_listings": sold,
                        "sell_through_rate": str_value,
                    },
                }
                rank = ranking_payload(item)
                item["ranking"] = rank
                item["suggested_price"] = rank["suggested_price"]
                etsy_metrics = {
                    "total_results": (intel.get("etsy_search") or {}).get("search_metadata", {}).get("total_results"),
                    "digital_share": (intel.get("etsy_search") or {}).get("aggregates", {}).get("digital_share", (intel.get("etsy_search") or {}).get("search_metadata", {}).get("digital_share")),
                    "avg_price": (intel.get("etsy_search") or {}).get("aggregates", {}).get("avg_price", (intel.get("etsy_search") or {}).get("aggregates", {}).get("median_price")),
                    "avg_reviews_top": (intel.get("competition") or {}).get("avg_reviews_top"),
                }
                ebay_metrics = {
                    "str_percent": str_value,
                    "active_count": active,
                    "sold_count": sold,
                }
                item["fms_components"] = compute_fms_components(etsy_metrics=etsy_metrics, ebay_metrics=ebay_metrics, real_performance=item.get("real_performance") or {})
                item["fms_score"] = compute_fms_score(item["fms_components"])
                item["scraping_profile"] = "fast_v1"

                decision_payload = decision_for_item(item)
                item["decision_payload"] = decision_payload
                decision = str(decision_payload.get("status") or "uncertain")
                reason = str(decision_payload.get("reason_code") or "unknown_reason")
                etsy_summary = etsy_signal_summary(niche_ctx)
                seed_record["niche_decisions"].append({
                    "niche": niche,
                    "status": decision,
                    "decision_type": decision_payload.get("decision_type"),
                    "reason": reason,
                    "reason_code": decision_payload.get("reason_code"),
                    "reason_detail": decision_payload.get("reason_detail"),
                    "fms_score": item["fms_score"],
                    "str_percent": str_value,
                    "active_count": active,
                    "sold_count": sold,
                    "etsy_digital_share": etsy_summary["digital_share"],
                    "etsy_total_results": etsy_summary["total_results"],
                    "avg_reviews_top": etsy_summary["avg_reviews_top"],
                    "data_quality": item.get("data_quality") or {},
                    "source_quality": item.get("source_quality") or {},
                })
                validation_result = process_niche(item=item, batch_id=current_batch_id, scraping_profile="fast_v1", decision=decision, reason=reason)
                item["validation"] = validation_result

                if decision != "winner":
                    if decision == "candidate":
                        batch_stats["candidate_count"] += 1
                    else:
                        batch_stats["rejected_count"] += 1
                    continue

                approved.append(item)
                batch_stats["winner_count"] += 1
                vertical_approved += 1
                seed_record["status"] = "winner"
                seed_record["reason"] = reason
                seed_record["decision_type"] = "market_accept"
                seed_record["reason_code"] = reason
                seed_record["reason_detail"] = "winner_found_in_seed"
                print(
                    f"[monetization_pipeline_fast] approved: {niche} | vertical={vertical_name} | "
                    f"score={item['fms_score']} | STR={str_value}% | active={active} sold={sold}"
                )

            seed_statuses.append(seed_record)
            processed_seeds += 1
            write_seed_statuses(seed_statuses, batch_stats, processed_seeds=processed_seeds, total_seeds_planned=total_seeds_planned, batch_status="running")
            write_batch_progress(current_batch_id, batch_stats, processed_seeds=processed_seeds, total_seeds_planned=total_seeds_planned, batch_status="running")

    batch_stats["batch_status"] = "completed"
    write_seed_statuses(seed_statuses, batch_stats, processed_seeds=processed_seeds, total_seeds_planned=total_seeds_planned, batch_status="completed")
    write_batch_progress(current_batch_id, batch_stats, processed_seeds=processed_seeds, total_seeds_planned=total_seeds_planned, batch_status="completed")
    approved.sort(
        key=lambda item: (
            -float(item.get("fms_score") or 0.0),
            -float(item["metrics"]["sell_through_rate"]),
            -float((item.get("ranking") or {}).get("etsy_fit") or 0.0),
            item["niche"],
        )
    )
    return approved[:TARGET_COUNT], batch_stats


def write_seed_statuses(
    seed_statuses: list[dict[str, Any]],
    batch_stats: dict[str, Any],
    *,
    processed_seeds: int,
    total_seeds_planned: int,
    batch_status: str,
) -> None:
    ACCEPTED_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": now_iso(),
        "batch_id": batch_stats.get("batch_id"),
        "batch_status": batch_status,
        "processed_seeds": int(processed_seeds),
        "total_seeds": int(total_seeds_planned),
        "seed_count": len(seed_statuses),
        "network_fail_ratio": round(
            float(batch_stats.get("network_fail_seeds", 0)) / max(1, int(processed_seeds or 0)),
            4,
        ),
        "batch_stats": batch_stats,
        "items": seed_statuses,
    }
    SEED_STATUS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_output(items: list[dict[str, Any]], batch_stats: dict[str, Any]) -> dict[str, Any]:
    ACCEPTED_DIR.mkdir(parents=True, exist_ok=True)
    progress = json.loads(BATCH_PROGRESS_PATH.read_text(encoding="utf-8")) if BATCH_PROGRESS_PATH.exists() else {}
    payload = {
        "schema_version": "2.2",
        "generated_at": now_iso(),
        "batch_id": batch_stats.get("batch_id"),
        "batch_status": progress.get("batch_status") or batch_stats.get("batch_status") or "completed",
        "processed_seeds": int(progress.get("processed_seeds") or batch_stats.get("total_seeds") or 0),
        "total_seeds": int(progress.get("total_seeds") or batch_stats.get("total_seeds_planned") or batch_stats.get("total_seeds") or 0),
        "strategy": "google_etsy_ebay_monetization_pipeline_fast",
        "acceptance_gates": {
            "min_monetization_score": MIN_MONETIZATION_SCORE,
            "min_str_for_accept": MIN_STR_FOR_ACCEPT,
            "min_sold_for_accept": MIN_SOLD_FOR_ACCEPT,
            "min_active": MIN_ACTIVE,
            "max_active": MAX_ACTIVE,
        },
        "accepted_count": len(items),
        "batch_stats": batch_stats,
        "items": items,
        "niches": items,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    items, batch_stats = collect_candidates()
    payload = write_output(items, batch_stats)
    print(f"[monetization_pipeline_fast] wrote {payload['accepted_count']} niches to {OUTPUT_PATH}")
    print(
        f"[monetization_pipeline_fast] batch={batch_stats['batch_id']} | winners={batch_stats['winner_count']} | "
        f"network_fail_ratio={round(float(batch_stats['network_fail_seeds']) / max(1, int(batch_stats['total_seeds'])), 4)}"
    )


if __name__ == "__main__":
    main()
