from __future__ import annotations

from typing import Any, Optional


REFERENCE_WINNER_ADHD_CLEANING: dict[str, Any] = {
    "niche_id": "REFERENCE_WINNER_ADHD_CLEANING",
    "niche_keyword": "adhd cleaning checklist",
    "fms_score": 63.16,
    "etsy": {
        "digital_share": 0.458,
    },
    "ebay": {
        "str_percent": 34.66,
        "active_count": 176,
        "sold_count": 61,
    },
}


def compute_reference_ratios(
    fms_score: float,
    ebay_metrics: dict[str, Any],
    reference: dict[str, Any] = REFERENCE_WINNER_ADHD_CLEANING,
) -> dict[str, Optional[float]]:
    """
    Возвращает отношение текущей ниши к эталону по:
      - fms_ratio
      - str_ratio
      - sold_ratio
    Если в эталоне нет нужного значения или оно == 0, возвращает None для соответствующего поля.
    """
    ref_fms = float(reference.get("fms_score") or 0.0)

    ref_ebay = reference.get("ebay") or {}
    ref_str = float(ref_ebay.get("str_percent") or 0.0)
    ref_sold = float(ref_ebay.get("sold_count") or 0.0)

    cur_str = float(ebay_metrics.get("str_percent") or 0.0)
    cur_sold = float(ebay_metrics.get("sold_count") or 0.0)

    return {
        "fms_ratio": (float(fms_score) / ref_fms) if ref_fms > 0 else None,
        "str_ratio": (cur_str / ref_str) if ref_str > 0 else None,
        "sold_ratio": (cur_sold / ref_sold) if ref_sold > 0 else None,
    }


def etsy_quality_band_for(
    digital_share: Optional[float],
    hard_low: float = 0.4,
    weak_low: float = 0.4,
    weak_high: float = 0.5,
) -> str:
    """
    Возвращает Etsy quality band по digital_share:
      - "low"    : digital_share < hard_low
      - "weak"   : weak_low <= digital_share < weak_high
      - "healthy": digital_share >= weak_high

    По умолчанию:
      hard_low = 0.4
      weak band = [0.4, 0.5)
      healthy  = >= 0.5
    """
    if digital_share is None:
        return "unknown"

    ds = float(digital_share)

    if ds < hard_low:
        return "low"
    if weak_low <= ds < weak_high:
        return "weak"
    return "healthy"
