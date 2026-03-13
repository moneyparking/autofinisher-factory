from __future__ import annotations

from typing import Any


def _to_score_from_band(value: str | None, *, low: float = 4.0, medium: float = 7.0, high: float = 10.0) -> float:
    normalized = str(value or "").strip().lower()
    if normalized == "high":
        return high
    if normalized == "medium":
        return medium
    if normalized == "low":
        return low
    return medium


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def calculate_bundle_power(wedge: dict[str, Any]) -> float:
    artifact_stack = wedge.get("artifact_stack") or []
    artifact_diversity_hint = wedge.get("artifact_diversity_hint")
    if artifact_diversity_hint is not None:
        artifact_diversity = max(0.0, min(10.0, _safe_float(artifact_diversity_hint, 0.0)))
    else:
        artifact_diversity = max(0.0, min(10.0, len({str(a).strip().lower() for a in artifact_stack if str(a).strip()}) * 2.0))

    expected_bundle_tiers = wedge.get("expected_bundle_tiers") or []
    avg_price_hint = _safe_float(wedge.get("avg_price_hint"), 0.0)
    max_tier = 0.0
    for tier in expected_bundle_tiers:
        max_tier = max(max_tier, _safe_float(tier, 0.0))
    price_anchor = max(avg_price_hint, max_tier)
    if price_anchor >= 79:
        price_potential = 10.0
    elif price_anchor >= 49:
        price_potential = 8.0
    elif price_anchor >= 29:
        price_potential = 6.0
    else:
        price_potential = 3.0

    expansion_products = wedge.get("expansion_products") or []
    expansion_count = len([item for item in expansion_products if str(item).strip()])
    if expansion_count >= 2:
        upsell_path = 10.0
    elif expansion_count == 1:
        upsell_path = 7.0
    else:
        upsell_path = 4.0

    gumroad_fit = _to_score_from_band(wedge.get("gumroad_fit_hint"), low=4.0, medium=7.0, high=10.0)
    bundle_cohesion = _to_score_from_band(wedge.get("bundle_cohesion_hint"), low=3.0, medium=6.0, high=9.0)

    bundle_power = round(
        (0.25 * artifact_diversity)
        + (0.25 * price_potential)
        + (0.20 * upsell_path)
        + (0.15 * gumroad_fit)
        + (0.15 * bundle_cohesion),
        1,
    )
    return max(0.0, min(10.0, bundle_power))


def bundle_keep_status(bundle_power: float, *, keep_threshold: float = 7.5) -> str:
    return "keep" if bundle_power >= keep_threshold else "kill"
