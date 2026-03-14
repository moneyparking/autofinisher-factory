from __future__ import annotations

from typing import Any

YOUTUBE_BUCKET_REGISTRY: dict[str, dict[str, Any]] = {
    "etsy_listing_level_ad_decision_system": {
        "canonical_hypothesis_id": "etsy_listing_level_ad_decision_system",
        "canonical_title": "Etsy Listing-Level Ad Decision System",
        "youtube_signal_score": 72.0,
        "source_system": "youtube_etsy_ads_clusters",
        "source_clusters": ["etsy_ads_cluster_v1", "etsy_ads_cluster_v2"],
        "evidence_summary": {
            "video_count": 22,
            "v1_pass_ratio": 0.9,
            "decision_wedge_video_ratio": 0.6,
            "avg_bundle_spec_count_per_video": 3.2,
            "avg_distinct_sub_wedge_count_per_video": 3.2,
        },
        "artifact_stack": ["decision dashboard", "testing sheet", "checklist", "bundle"],
        "offer_formats": ["Checklist Kit", "Bundle", "KPI Dashboard", "Mini Course"],
        "primary_channel": "etsy",
        "secondary_channel": "gumroad",
    },
    "etsy_ads_profitability_system": {
        "canonical_hypothesis_id": "etsy_ads_profitability_system",
        "canonical_title": "Etsy Ads Profitability System",
        "youtube_signal_score": 59.0,
        "source_system": "youtube_etsy_ads_clusters",
        "source_clusters": ["etsy_ads_cluster_v1", "etsy_ads_cluster_v2"],
        "evidence_summary": {
            "video_count": 22,
            "v1_pass_ratio": 0.9,
            "decision_wedge_video_ratio": 0.6,
            "avg_bundle_spec_count_per_video": 3.2,
            "avg_distinct_sub_wedge_count_per_video": 3.2,
        },
        "artifact_stack": ["dashboard", "calculator", "testing sheet", "mini-course", "bundle"],
        "offer_formats": ["Mini Course", "KPI Dashboard", "Calculator", "Checklist Kit"],
        "primary_channel": "etsy",
        "secondary_channel": "gumroad",
    },
    "etsy_break_even_roas_calculator": {
        "canonical_hypothesis_id": "etsy_break_even_roas_calculator",
        "canonical_title": "Etsy Break-Even ROAS Calculator",
        "youtube_signal_score": 56.0,
        "source_system": "youtube_etsy_ads_clusters",
        "source_clusters": ["etsy_ads_cluster_v1", "etsy_ads_cluster_v2"],
        "evidence_summary": {
            "video_count": 22,
            "v1_pass_ratio": 0.9,
            "decision_wedge_video_ratio": 0.6,
            "avg_bundle_spec_count_per_video": 3.2,
            "avg_distinct_sub_wedge_count_per_video": 3.2,
        },
        "artifact_stack": ["calculator", "dashboard", "checklist", "bundle"],
        "offer_formats": ["Bundle", "Calculator", "Checklist Kit", "KPI Dashboard"],
        "primary_channel": "etsy",
        "secondary_channel": "gumroad",
    },
}

CHANNEL_VALIDATION_PROFILES: dict[str, dict[str, Any]] = {
    "general_digital_template": {
        "profile_id": "general_digital_template",
        "description": "General digital template validation profile with balanced marketplace weighting.",
        "primary_channels": ["etsy", "gumroad"],
        "secondary_channels": ["ebay", "google"],
        "ebay_signal_policy": "normal",
        "market_fms_weight": 1.0,
        "youtube_fms_weight": 0.0,
        "max_youtube_uplift": 0.0,
    },
    "etsy_seller_b2b_tool": {
        "profile_id": "etsy_seller_b2b_tool",
        "description": "Seller/B2B Etsy utility profile where Etsy + YouTube evidence matter more than eBay liquidity.",
        "primary_channels": ["etsy"],
        "secondary_channels": ["gumroad", "google"],
        "ebay_signal_policy": "soft_signal",
        "market_fms_weight": 1.0,
        "youtube_fms_weight": 0.25,
        "max_youtube_uplift": 8.0,
    },
}

BUCKET_ALIASES = {
    "etsy listing-level ad decision system": "etsy_listing_level_ad_decision_system",
    "etsy ads profitability system": "etsy_ads_profitability_system",
    "etsy break-even roas calculator": "etsy_break_even_roas_calculator",
    "etsy break even roas calculator": "etsy_break_even_roas_calculator",
}


def normalize_bucket(value: str | None) -> str:
    key = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return BUCKET_ALIASES.get(str(value or "").strip().lower(), key)



def infer_channel_validation_profile(item: dict[str, Any]) -> dict[str, Any]:
    bucket = normalize_bucket(item.get("bucket"))
    niche = str(item.get("niche") or "").lower()
    utility_tokens = {"tracker", "spreadsheet", "dashboard", "calculator", "roas", "profit", "optimization", "ads"}
    if bucket in YOUTUBE_BUCKET_REGISTRY or ("etsy" in niche and any(tok in niche for tok in utility_tokens)):
        return CHANNEL_VALIDATION_PROFILES["etsy_seller_b2b_tool"].copy()
    return CHANNEL_VALIDATION_PROFILES["general_digital_template"].copy()



def derive_youtube_hypothesis_intel(item: dict[str, Any]) -> dict[str, Any] | None:
    bucket = normalize_bucket(item.get("bucket"))
    if bucket in YOUTUBE_BUCKET_REGISTRY:
        data = YOUTUBE_BUCKET_REGISTRY[bucket].copy()
        data["bucket"] = bucket
        data["score_available"] = True
        return data
    return None



def compute_overall_fms_sync(
    market_fms_score: float,
    channel_validation_profile: dict[str, Any],
    youtube_hypothesis_intel: dict[str, Any] | None,
) -> dict[str, Any]:
    market_score = round(float(market_fms_score or 0.0), 2)
    if not youtube_hypothesis_intel or not youtube_hypothesis_intel.get("score_available"):
        return {
            "market_fms_score": market_score,
            "youtube_hypothesis_score": None,
            "overall_fms_score": market_score,
            "youtube_uplift": 0.0,
            "sync_mode": "market_only",
        }

    youtube_score = round(float(youtube_hypothesis_intel.get("youtube_signal_score") or 0.0), 2)
    uplift_weight = float(channel_validation_profile.get("youtube_fms_weight") or 0.0)
    max_uplift = float(channel_validation_profile.get("max_youtube_uplift") or 0.0)
    uplift = min(max_uplift, max(0.0, youtube_score - market_score) * uplift_weight)
    overall = round(market_score + uplift, 2)
    return {
        "market_fms_score": market_score,
        "youtube_hypothesis_score": youtube_score,
        "overall_fms_score": overall,
        "youtube_uplift": round(uplift, 2),
        "sync_mode": "market_plus_youtube_hypothesis",
    }
