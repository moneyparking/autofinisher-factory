from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fms_decision import aggregate_data_quality
from fms_reference import compute_reference_ratios, etsy_quality_band_for

BASE_DIR = Path("/home/agent/autofinisher-factory")
DATA_DIR = BASE_DIR / "data"
VALIDATED_DIR = DATA_DIR / "validated_niches"
WINNERS_DIR = DATA_DIR / "winners"
TASKS_DIR = DATA_DIR / "sku_tasks"
VALIDATED_LOG_PATH = VALIDATED_DIR / "validated_niches.json"
VALIDATED_ITEMS_DIR = VALIDATED_DIR / "items"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return slug or "untitled"


def ensure_dirs() -> None:
    VALIDATED_DIR.mkdir(parents=True, exist_ok=True)
    VALIDATED_ITEMS_DIR.mkdir(parents=True, exist_ok=True)
    WINNERS_DIR.mkdir(parents=True, exist_ok=True)
    TASKS_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def family_for_item(item: dict[str, Any]) -> dict[str, Any]:
    niche = str(item.get("niche") or "")
    niche_lower = niche.lower()
    vertical = str(item.get("vertical") or item.get("ranking", {}).get("vertical") or "general_utility")
    sub_family = "general_systems"
    niche_family = [vertical]

    if "adhd" in niche_lower:
        niche_family.append("ADHD")
    if any(token in niche_lower for token in ["cleaning", "declutter", "chore"]):
        niche_family.extend(["home-organization", "cleaning systems"])
        sub_family = "home_cleaning_systems"
    elif any(token in niche_lower for token in ["planner", "routine", "checklist"]):
        sub_family = "structured_productivity_systems"

    deduped = []
    seen = set()
    for value in niche_family:
        norm = value.strip()
        if norm and norm not in seen:
            seen.add(norm)
            deduped.append(norm)

    return {
        "vertical_family": vertical,
        "sub_family": sub_family,
        "channel_focus": ["Etsy", "Gumroad"],
        "niche_family": deduped,
    }


def thesis_for_item(item: dict[str, Any]) -> dict[str, str]:
    niche = str(item.get("niche") or "")
    niche_lower = niche.lower()
    if "adhd" in niche_lower and "cleaning" in niche_lower:
        return {
            "buyer_intent": "ADHD users looking for simple, structured cleaning guidance they can actually follow.",
            "problem": "Overwhelm, inability to keep regular cleaning habits, need for visual and step-by-step systems.",
            "solution": "Printable checklist system that breaks cleaning into small, ADHD-friendly steps and routines.",
        }
    return {
        "buyer_intent": f"Buyers searching for {niche} want a practical digital template they can use immediately.",
        "problem": "They need a low-friction system that reduces setup time and decision fatigue.",
        "solution": "A clean, printable digital asset that structures the task into clear, usable steps.",
    }


def recommended_sku_cluster(item: dict[str, Any]) -> dict[str, Any]:
    niche = str(item.get("niche") or "")
    base_slug = safe_slug(niche)
    if niche.lower() == "adhd cleaning checklist":
        return {
            "core_skus": [
                {
                    "slug": "adhd-cleaning-checklist-printable",
                    "type": "checklist",
                    "format": ["PDF", "Printable A4/US Letter"],
                    "priority": 1,
                },
                {
                    "slug": "adhd-weekly-cleaning-system",
                    "type": "system",
                    "format": ["PDF", "Printable A4/US Letter"],
                    "priority": 2,
                },
            ],
            "audience_variants": [
                {
                    "slug": "adhd-cleaning-checklist-generic-home",
                    "audience": "generic home",
                    "priority": 1,
                },
                {
                    "slug": "adhd-cleaning-checklist-for-moms",
                    "audience": "ADHD moms / parents",
                    "priority": 2,
                },
                {
                    "slug": "adhd-cleaning-checklist-for-students",
                    "audience": "students / roommates",
                    "priority": 2,
                },
            ],
            "bundle_skus": [
                {
                    "slug": "adhd-cleaning-and-routine-bundle",
                    "includes": [
                        "adhd-cleaning-checklist-printable",
                        "adhd-daily-planner-printable",
                        "adhd-routines-reset-checklist",
                    ],
                    "priority": 3,
                },
                {
                    "slug": "adhd-cleaning-checklist-weekly-system-bundle",
                    "includes": [
                        "adhd-cleaning-checklist-printable",
                        "adhd-weekly-cleaning-system",
                    ],
                    "priority": 3,
                },
            ],
        }
    return {
        "core_skus": [
            {
                "slug": base_slug,
                "type": "template",
                "format": ["PDF", "Printable A4/US Letter"],
                "priority": 1,
            }
        ],
        "audience_variants": [],
        "bundle_skus": [],
    }


def design_guidelines_for_item(item: dict[str, Any]) -> dict[str, Any]:
    niche = str(item.get("niche") or "")
    if niche.lower() == "adhd cleaning checklist":
        return {
            "style": "clean, high-contrast, neurodivergent-friendly, minimal clutter",
            "layout": [
                "step-by-step sections",
                "daily / weekly / monthly blocks",
                "checkboxes and micro-tasks",
                "space for personalization (own rooms/tasks)",
            ],
            "accessibility": [
                "avoid tiny text",
                "clear headings and sections",
                "no heavy background textures that reduce readability",
            ],
        }
    return {
        "style": "clean, minimal, high-readability digital product layout",
        "layout": ["clear sections", "checklists or guided blocks", "usable spacing"],
        "accessibility": ["avoid tiny text", "clear headings"],
    }


def seo_hints_for_item(item: dict[str, Any]) -> dict[str, Any]:
    niche = str(item.get("niche") or "")
    if niche.lower() == "adhd cleaning checklist":
        return {
            "core_keywords": [
                "adhd cleaning checklist",
                "adhd cleaning schedule",
                "adhd friendly cleaning",
                "adhd home organization",
                "printable cleaning checklist",
            ],
            "angles": [
                "Designed for ADHD brains",
                "Breaks cleaning into tiny, doable steps",
                "Perfect for overwhelmed adults with ADHD",
            ],
        }
    return {
        "core_keywords": [niche],
        "angles": ["Printable digital system", "Fast to use", "Structured and practical"],
    }


def build_win_card(item: dict[str, Any], batch_id: str, scraping_profile: str = "fast_v1") -> dict[str, Any]:
    niche = str(item.get("niche") or "")
    ranking = item.get("ranking") or {}
    metrics = item.get("metrics") or {}
    intel = item.get("intel") or {}
    etsy_search = intel.get("etsy_search") or {}
    aggregates = etsy_search.get("aggregates") or {}
    search_metadata = etsy_search.get("search_metadata") or {}
    family = family_for_item(item)
    niche_id = f"{safe_slug(niche).replace('-', '_')}_v1"

    avg_price = aggregates.get("avg_price")
    if avg_price is None:
        median_price = aggregates.get("median_price")
        avg_price = float(median_price) if median_price is not None else None

    competition = intel.get("competition") or {}
    card = {
        "niche_id": niche_id,
        "niche_keyword": niche,
        "family": {
            "vertical_family": family["vertical_family"],
            "sub_family": family["sub_family"],
            "channel_focus": family["channel_focus"],
        },
        "validation_metrics": {
            "fms_score": float(item.get("fms_score") or ranking.get("monetization_score") or 0.0),
            "ebay": {
                "str_percent": float(metrics.get("sell_through_rate") or 0.0),
                "active_count": int(metrics.get("active_listings") or 0),
                "sold_count": int(metrics.get("sold_listings") or 0),
            },
            "etsy": {
                "total_results": search_metadata.get("total_results"),
                "digital_share": aggregates.get("digital_share", search_metadata.get("digital_share")),
                "avg_price": avg_price,
                "avg_reviews_top": competition.get("avg_reviews_top"),
            },
            "google": {
                "queries": item.get("google_queries") or [],
                "candidate_count": int(item.get("google_candidate_count") or 0),
                "status": str(item.get("google_status") or item.get("seed_status") or "unknown"),
            },
            "decision_type": (item.get("decision_payload") or {}).get("decision_type"),
            "reason_code": (item.get("decision_payload") or {}).get("reason_code"),
            "data_quality": item.get("data_quality") or aggregate_data_quality(item.get("source_quality") or {}),
            "source_quality": item.get("source_quality") or {},
            "validation_source_batch": batch_id,
            "scraping_profile": scraping_profile,
        },
        "thesis": thesis_for_item(item),
        "recommended_sku_cluster": recommended_sku_cluster(item),
        "design_guidelines": design_guidelines_for_item(item),
        "seo_and_copy_hints": seo_hints_for_item(item),
        "actions_for_pipeline": {
            "sku_factory": {
                "target_skus_to_build": 3,
                "mode": "fast",
                "deadline_days": 2,
            },
            "listing_ops": {
                "primary_channel": "Etsy",
                "secondary_channel": "Gumroad",
                "notes": "Etsy first, bundles + extended systems on Gumroad.",
            },
        },
    }
    return card


def validated_record(item: dict[str, Any], batch_id: str, decision: str, reason: str) -> dict[str, Any]:
    ranking = item.get("ranking") or {}
    metrics = item.get("metrics") or {}
    intel = item.get("intel") or {}
    family = family_for_item(item)
    niche_keyword = str(item.get("niche") or "")
    niche_id = f"{safe_slug(niche_keyword).replace('-', '_')}_v1"
    etsy_search = intel.get("etsy_search") or {}
    aggregates = etsy_search.get("aggregates") or {}
    search_metadata = etsy_search.get("search_metadata") or {}
    etsy_metrics = {
        "total_results": search_metadata.get("total_results"),
        "digital_share": aggregates.get("digital_share", search_metadata.get("digital_share")),
        "avg_price": aggregates.get("avg_price", aggregates.get("median_price")),
        "avg_reviews_top": (intel.get("competition") or {}).get("avg_reviews_top"),
    }
    ebay_metrics = {
        "str_percent": float(metrics.get("sell_through_rate") or 0.0),
        "active_count": int(metrics.get("active_listings") or 0),
        "sold_count": int(metrics.get("sold_listings") or 0),
    }
    decision_payload = item.get("decision_payload") or {}
    source_quality = item.get("source_quality") or {}
    data_quality = item.get("data_quality") or aggregate_data_quality(source_quality)
    fms_score = float(item.get("fms_score") or ranking.get("monetization_score") or 0.0)
    return {
        "recorded_at": now_iso(),
        "batch_id": batch_id,
        "niche_id": niche_id,
        "niche_keyword": niche_keyword,
        "niche": niche_keyword,
        "vertical": item.get("vertical") or ranking.get("vertical"),
        "bucket": item.get("bucket"),
        "niche_family": family["niche_family"],
        "fms_score": fms_score,
        "etsy_metrics": etsy_metrics,
        "ebay_metrics": ebay_metrics,
        "etsy_quality_band": etsy_quality_band_for(etsy_metrics.get("digital_share")),
        "vs_reference": compute_reference_ratios(fms_score, ebay_metrics),
        "status": decision,
        "decision_type": decision_payload.get("decision_type"),
        "reason": reason,
        "reason_code": decision_payload.get("reason_code") or reason,
        "reason_detail": decision_payload.get("reason_detail") or "",
        "source_quality": source_quality,
        "data_quality": data_quality,
        "validation": {
            "batch_id": batch_id,
            "scraping_profile": item.get("scraping_profile") or "fast_v1",
            "status": decision,
            "decision_type": decision_payload.get("decision_type"),
            "reason": reason,
            "reason_code": decision_payload.get("reason_code") or reason,
            "reason_detail": decision_payload.get("reason_detail") or "",
            "niche_id": niche_id,
            "validated_path": None,
            "win_card_path": None,
            "sku_task_path": None,
            "updated_at": now_iso(),
        },
        "channel_validation_profile": item.get("channel_validation_profile") or {},
        "youtube_hypothesis_intel": item.get("youtube_hypothesis_intel"),
        "buildability_profile": item.get("buildability_profile") or {},
        "fms_sync": item.get("fms_sync") or {
            "market_fms_score": fms_score,
            "youtube_hypothesis_score": None,
            "overall_fms_score": fms_score,
            "youtube_uplift": 0.0,
            "sync_mode": "market_only",
        },
        "opportunity_sync": item.get("opportunity_sync") or {
            "overall_opportunity_score": float(item.get("overall_opportunity_score") or fms_score),
            "market_component": float(item.get("fms_score") or fms_score),
            "buildability_component": 0.0,
            "channel_fit_bonus": 0.0,
        },
        "validation_metrics": {
            "fms_score": float(item.get("fms_score") or ranking.get("monetization_score") or 0.0),
            "market_fms_score": float(item.get("market_fms_score") or item.get("fms_score") or ranking.get("monetization_score") or 0.0),
            "overall_fms_score": float(item.get("fms_score") or ranking.get("monetization_score") or 0.0),
            "overall_opportunity_score": float(item.get("overall_opportunity_score") or item.get("fms_score") or ranking.get("monetization_score") or 0.0),
            "buildability_score": float(item.get("buildability_score") or 0.0),
            "youtube_hypothesis_score": float((item.get("fms_sync") or {}).get("youtube_hypothesis_score") or 0.0),
            "youtube_uplift": float((item.get("fms_sync") or {}).get("youtube_uplift") or 0.0),
            "etsy_fit": float(ranking.get("etsy_fit") or 0.0),
            "gumroad_fit": float(ranking.get("gumroad_fit") or 0.0),
            "str_percent": ebay_metrics["str_percent"],
            "active_count": ebay_metrics["active_count"],
            "sold_count": ebay_metrics["sold_count"],
            "etsy_digital_share": etsy_metrics["digital_share"],
            "avg_reviews_top": etsy_metrics["avg_reviews_top"],
        },
        "raw": {
            "google_queries": item.get("google_queries") or [],
            "google_candidate_count": int(item.get("google_candidate_count") or 0),
            "seed_status": item.get("seed_status"),
            "bucket": item.get("bucket"),
            "intel": intel,
            "ranking": ranking,
            "metrics": metrics,
            "fms_components": item.get("fms_components") or {},
            "real_performance": item.get("real_performance") or {},
            "market_fms_score": item.get("market_fms_score"),
            "fms_sync": item.get("fms_sync") or {},
            "buildability_profile": item.get("buildability_profile") or {},
            "opportunity_sync": item.get("opportunity_sync") or {},
        },
    }


def append_validated_record(record: dict[str, Any]) -> None:
    ensure_dirs()
    payload = load_json(VALIDATED_LOG_PATH, {"created_at": now_iso(), "items": []})
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        items = []
    items.append(record)
    payload = {
        "created_at": payload.get("created_at", now_iso()) if isinstance(payload, dict) else now_iso(),
        "updated_at": now_iso(),
        "count": len(items),
        "items": items,
    }
    write_json(VALIDATED_LOG_PATH, payload)


def create_sku_task_from_win_card(win_card: dict[str, Any], priority: str = "high") -> dict[str, Any]:
    ensure_dirs()
    task_id = f"sku_task_{win_card['niche_id']}"
    task = {
        "task_id": task_id,
        "created_at": now_iso(),
        "niche_id": win_card["niche_id"],
        "niche_keyword": win_card["niche_keyword"],
        "target_skus_to_build": int(win_card["actions_for_pipeline"]["sku_factory"]["target_skus_to_build"]),
        "priority": priority,
        "mode": win_card["actions_for_pipeline"]["sku_factory"]["mode"],
        "cluster": win_card["recommended_sku_cluster"],
    }
    write_json(TASKS_DIR / f"{task_id}.json", task)
    return task


def register_validated_niche(item: dict[str, Any], batch_id: str, decision: str, reason: str) -> dict[str, Any]:
    ensure_dirs()
    record = validated_record(item=item, batch_id=batch_id, decision=decision, reason=reason)
    append_validated_record(record)
    validated_path = VALIDATED_ITEMS_DIR / f"{record['niche_id']}.json"
    record["validated_path"] = str(validated_path.resolve())
    record["validation"]["validated_path"] = str(validated_path.resolve())
    write_json(validated_path, record)
    return record


def register_winner(item: dict[str, Any], batch_id: str, scraping_profile: str = "fast_v1") -> dict[str, Any]:
    ensure_dirs()
    win_card = build_win_card(item=item, batch_id=batch_id, scraping_profile=scraping_profile)
    win_card_path = WINNERS_DIR / f"{win_card['niche_id']}.json"
    task = create_sku_task_from_win_card(win_card)
    win_card["win_card_path"] = str(win_card_path.resolve())
    win_card["sku_task_path"] = str((TASKS_DIR / f"{task['task_id']}.json").resolve())
    write_json(win_card_path, win_card)
    return win_card


def process_niche(item: dict[str, Any], batch_id: str, scraping_profile: str = "fast_v1", decision: str | None = None, reason: str | None = None) -> dict[str, Any]:
    ranking = item.get("ranking") or {}
    metrics = item.get("metrics") or {}
    score = float(item.get("fms_score") or ranking.get("monetization_score") or 0.0)
    sold = int(metrics.get("sold_listings") or 0)
    str_percent = float(metrics.get("sell_through_rate") or 0.0)

    if decision is None or reason is None:
        if score >= 42.0 and str_percent >= 15.0 and sold >= 20:
            decision, reason = "winner", "fms_ok_and_ebay_liquidity_strong"
        elif score >= 42.0:
            decision, reason = "candidate", "fms_ok_but_ebay_liquidity_mixed"
        else:
            decision, reason = "low_fms", "fms_below_min_score"

    validated = register_validated_niche(item=item, batch_id=batch_id, decision=decision, reason=reason)
    result = {
        "status": decision,
        "reason": reason,
        "niche_id": validated.get("niche_id"),
        "validated_path": validated.get("validated_path"),
        "win_card_path": None,
        "sku_task_path": None,
    }
    if decision == "winner":
        win_card = register_winner(item=item, batch_id=batch_id, scraping_profile=scraping_profile)
        result["win_card_path"] = win_card.get("win_card_path")
        result["sku_task_path"] = win_card.get("sku_task_path")
        validated_path = result.get("validated_path")
        if validated_path:
            validated_payload = load_json(Path(validated_path), {})
            validation = validated_payload.get("validation") or {}
            validation["win_card_path"] = result["win_card_path"]
            validation["sku_task_path"] = result["sku_task_path"]
            validated_payload["validation"] = validation
            write_json(Path(validated_path), validated_payload)
    return result
