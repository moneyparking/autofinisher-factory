from __future__ import annotations

import json
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

BASE_DIR = Path("/home/agent/autofinisher-factory")
VERTICALS_PATH = BASE_DIR / "vertical_families.json"
ACCEPTED_DIR = BASE_DIR / "niche_engine" / "accepted"
OUTPUT_PATH = ACCEPTED_DIR / "niche_package.json"
SEED_STATUS_PATH = ACCEPTED_DIR / "seed_statuses.json"
TARGET_COUNT = 15
GOOGLE_MAX_PAGES_FAST = 1
GOOGLE_REQUESTS_PER_SEED_MAX = 1
MAX_GOOGLE_REQUESTS_PER_BATCH = 20
ETSY_REQUESTS_PER_SEED_MAX = 1
ETSY_MAX_LISTINGS_FAST = 24
MAX_ETSY_REQUESTS_PER_BATCH = 40
MAX_SHORTLIST_PER_SEED = 3
MAX_APPROVED_PER_VERTICAL = 14
MIN_MONETIZATION_SCORE = 42.0
MIN_ACTIVE = 8
MAX_ACTIVE = 5000
SCRAPER_RETRIES = 2
SCRAPER_BACKOFF = 1.0
MAX_ETSY_INSPECT_PER_SEED = 0
MAX_NETWORK_FAILURES_PER_SEED = 2


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


def load_verticals() -> list[dict[str, Any]]:
    if not VERTICALS_PATH.exists():
        return []
    payload = json.loads(VERTICALS_PATH.read_text(encoding="utf-8"))
    return [x for x in payload.get("vertical_families", []) if isinstance(x, dict)]


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


def collect_google_candidates(seed: str) -> tuple[list[str], str]:
    try:
        response = scan_google_niches(
            build_google_queries(seed)[:GOOGLE_REQUESTS_PER_SEED_MAX],
            country="US",
            language="en",
            max_pages=GOOGLE_MAX_PAGES_FAST,
        )
    except Exception as exc:
        print(f"[monetization_pipeline_fast] Google scan failed for '{seed}': {exc}")
        return [], "timeout"
    candidates: list[str] = []
    seen = set()
    for result in response.get("results", []):
        for cand in result.get("related_searches", []) + result.get("niche_candidates", []):
            norm = normalize(cand)
            if not norm or norm in seen:
                continue
            seen.add(norm)
            candidates.append(norm)
            if len(candidates) >= MAX_SHORTLIST_PER_SEED:
                return candidates, "ok"
    return candidates[:MAX_SHORTLIST_PER_SEED], "ok"


def collect_etsy_shortlist(seed: str, google_candidates: list[str]) -> tuple[list[dict[str, Any]], str]:
    scan_terms = [seed][:ETSY_REQUESTS_PER_SEED_MAX]
    try:
        response = etsy_scan_keywords(scan_terms, max_listings_per_keyword=ETSY_MAX_LISTINGS_FAST)
    except Exception as exc:
        print(f"[monetization_pipeline_fast] Etsy scan failed for '{seed}': {exc}")
        return [], "timeout"
    shortlist: list[dict[str, Any]] = []
    seen = set()
    for result in response.get("results", []):
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
    return shortlist[:MAX_SHORTLIST_PER_SEED], "ok"


def ebay_metrics_with_retry(keyword: str) -> dict[str, Any]:
    last_exc: Exception | None = None
    for attempt in range(SCRAPER_RETRIES + 1):
        try:
            return get_ebay_metrics(keyword)
        except Exception as exc:
            last_exc = exc
            if attempt < SCRAPER_RETRIES:
                sleep_for = SCRAPER_BACKOFF * (attempt + 1)
                print(f"[monetization_pipeline_fast] eBay retry {attempt + 1}/{SCRAPER_RETRIES} for '{keyword}': {exc}")
                time.sleep(sleep_for)
                continue
            raise
    if last_exc is not None:
        raise last_exc
    return {"active": 0, "sold": 0}


def collect_candidates() -> list[dict[str, Any]]:
    approved: list[dict[str, Any]] = []
    global_seen = set()
    google_requests_used = 0
    etsy_requests_used = 0
    seed_statuses: list[dict[str, Any]] = []

    for vertical in load_verticals():
        vertical_name = str(vertical.get("name", "general"))
        vertical_approved = 0

        for seed in vertical.get("seed_keywords", []):
            if len(approved) >= TARGET_COUNT:
                write_seed_statuses(seed_statuses)
                return approved[:TARGET_COUNT]
            if vertical_approved >= MAX_APPROVED_PER_VERTICAL:
                break

            seed = normalize(seed)
            if not seed:
                continue

            print(f"[monetization_pipeline_fast] seed: {seed} ({vertical_name})")
            seed_record = {
                "seed": seed,
                "vertical": vertical_name,
                "google_status": "skipped_budget",
                "etsy_status": "skipped_budget",
                "status": "ok",
            }
            network_failures = 0
            google_candidates: list[str] = []
            shortlist: list[dict[str, Any]] = []

            if google_requests_used < MAX_GOOGLE_REQUESTS_PER_BATCH:
                google_requests_used += 1
                google_candidates, google_status = collect_google_candidates(seed)
                seed_record["google_status"] = google_status
                if google_status != "ok":
                    network_failures += 1

            if etsy_requests_used < MAX_ETSY_REQUESTS_PER_BATCH:
                etsy_requests_used += 1
                shortlist, etsy_status = collect_etsy_shortlist(seed, google_candidates)
                seed_record["etsy_status"] = etsy_status
                if etsy_status != "ok":
                    network_failures += 1

            if network_failures >= MAX_NETWORK_FAILURES_PER_SEED:
                seed_record["status"] = "network_failed"
                seed_statuses.append(seed_record)
                continue

            if not shortlist:
                shortlist = [{"niche": niche, "trend_score": 50.0} for niche in fallback_seed_variants(seed)]
                seed_record["status"] = "partial_ok"
            elif seed_record["google_status"] != "ok" or seed_record["etsy_status"] != "ok":
                seed_record["status"] = "partial_ok"

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
                    metrics = ebay_metrics_with_retry(niche)
                except Exception as exc:
                    print(f"[monetization_pipeline_fast] eBay validation failed for '{niche}': {exc}")
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
                item = {
                    "niche": niche,
                    "vertical": vertical_name,
                    "trend_score": niche_ctx.get("trend_score", 50.0),
                    "seed_status": seed_record["status"],
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

                if active < MIN_ACTIVE or active > MAX_ACTIVE:
                    continue
                if sold <= 0:
                    continue
                if rank["monetization_score"] < MIN_MONETIZATION_SCORE:
                    continue

                approved.append(item)
                vertical_approved += 1
                print(
                    f"[monetization_pipeline_fast] approved: {niche} | vertical={vertical_name} | "
                    f"score={rank['monetization_score']} | STR={str_value}% | active={active} sold={sold}"
                )

            seed_statuses.append(seed_record)

    write_seed_statuses(seed_statuses)
    approved.sort(
        key=lambda item: (
            -float(item["ranking"]["monetization_score"]),
            -float(item["metrics"]["sell_through_rate"]),
            -float(item["ranking"]["etsy_fit"]),
            item["niche"],
        )
    )
    return approved[:TARGET_COUNT]


def write_seed_statuses(seed_statuses: list[dict[str, Any]]) -> None:
    ACCEPTED_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": now_iso(),
        "seed_count": len(seed_statuses),
        "items": seed_statuses,
    }
    SEED_STATUS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_output(items: list[dict[str, Any]]) -> dict[str, Any]:
    ACCEPTED_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "2.1",
        "generated_at": now_iso(),
        "strategy": "google_etsy_ebay_monetization_pipeline_fast",
        "accepted_count": len(items),
        "items": items,
        "niches": items,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    items = collect_candidates()
    payload = write_output(items)
    print(f"[monetization_pipeline_fast] wrote {payload['accepted_count']} niches to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
