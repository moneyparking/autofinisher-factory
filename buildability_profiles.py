from __future__ import annotations

from typing import Any


def _contains_any(text: str, tokens: set[str]) -> bool:
    return any(token in text for token in tokens)


def infer_buildability_profile(item: dict[str, Any]) -> dict[str, Any]:
    niche = str(item.get("niche") or "").lower()
    bucket = str(item.get("bucket") or "").lower()

    heavy_design_tokens = {
        "wedding", "wall art", "invitation", "clipart", "coloring", "art print", "sticker", "pattern"
    }
    heavy_content_tokens = {
        "course", "ebook", "journal", "guidebook", "workbook", "curriculum", "therapy"
    }
    fast_utility_tokens = {
        "tracker", "spreadsheet", "dashboard", "calculator", "template", "checklist", "inventory", "bookkeeping", "crm", "pipeline", "profit", "pricing", "cash flow", "content tracker"
    }

    formula_complexity = 40.0
    design_complexity = 40.0
    copy_complexity = 40.0
    support_burden = 35.0
    time_to_v1_hours = 8.0
    profile_id = "general_buildability"
    rationale = []

    if _contains_any(niche, fast_utility_tokens) or _contains_any(bucket, fast_utility_tokens):
        profile_id = "fast_utility_template"
        formula_complexity = 55.0
        design_complexity = 20.0
        copy_complexity = 25.0
        support_burden = 25.0
        time_to_v1_hours = 3.5
        rationale.append("utility_format_detected")

    if _contains_any(niche, heavy_design_tokens):
        profile_id = "design_heavy_template"
        design_complexity = max(design_complexity, 75.0)
        copy_complexity = max(copy_complexity, 45.0)
        support_burden = max(support_burden, 45.0)
        time_to_v1_hours = max(time_to_v1_hours, 12.0)
        rationale.append("design_heavy_detected")

    if _contains_any(niche, heavy_content_tokens):
        profile_id = "content_heavy_template"
        copy_complexity = max(copy_complexity, 75.0)
        support_burden = max(support_burden, 55.0)
        time_to_v1_hours = max(time_to_v1_hours, 14.0)
        rationale.append("content_heavy_detected")

    score = 100.0
    score -= (formula_complexity * 0.15)
    score -= (design_complexity * 0.30)
    score -= (copy_complexity * 0.20)
    score -= (support_burden * 0.15)
    score -= min(25.0, max(0.0, time_to_v1_hours - 2.0) * 2.0)
    score = round(max(0.0, min(100.0, score)), 2)

    speed_band = "fast"
    if time_to_v1_hours > 10:
        speed_band = "slow"
    elif time_to_v1_hours > 5:
        speed_band = "moderate"

    return {
        "profile_id": profile_id,
        "buildability_score": score,
        "speed_band": speed_band,
        "time_to_v1_hours": time_to_v1_hours,
        "formula_complexity": round(formula_complexity, 2),
        "design_complexity": round(design_complexity, 2),
        "copy_complexity": round(copy_complexity, 2),
        "support_burden": round(support_burden, 2),
        "rationale": rationale,
    }



def compute_opportunity_score(
    *,
    overall_fms_score: float,
    buildability_score: float,
    channel_validation_profile: dict[str, Any] | None,
) -> dict[str, Any]:
    profile = channel_validation_profile or {}
    primary_channels = profile.get("primary_channels") or []
    channel_fit_bonus = 4.0 if primary_channels else 0.0
    market_component = float(overall_fms_score or 0.0) * 0.7
    buildability_component = float(buildability_score or 0.0) * 0.3
    total = round(min(100.0, market_component + buildability_component + channel_fit_bonus), 2)
    return {
        "overall_opportunity_score": total,
        "market_component": round(market_component, 2),
        "buildability_component": round(buildability_component, 2),
        "channel_fit_bonus": channel_fit_bonus,
    }
