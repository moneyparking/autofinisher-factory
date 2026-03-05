from __future__ import annotations

from typing import Any

from money_niche_hunter.config.settings import WEIGHTS


def _norm_fms_score(value: float | int | None) -> float:
    v = float(value or 0.0)
    return max(0.0, min(1.0, v / 100.0))


def _norm_sold_count(value: int | float | None) -> float:
    v = float(value or 0.0)
    return max(0.0, min(1.0, v / 20.0))


def _norm_str_percent(value: float | int | None) -> float:
    v = float(value or 0.0)
    return max(0.0, min(1.0, v / 20.0))


def calculate_composite_score(item: dict[str, Any]) -> float:
    fms = _norm_fms_score(item.get("fms_score"))
    sold = _norm_sold_count(item.get("sold_count"))
    str_norm = _norm_str_percent(item.get("str_percent"))
    digital = max(0.0, min(1.0, float(item.get("etsy_digital_share") or 0.0)))
    score = (
        WEIGHTS.fms_score * fms
        + WEIGHTS.sold_count * sold
        + WEIGHTS.str_percent * str_norm
        + WEIGHTS.digital_share * digital
    )
    return round(score, 6)


def create_shortlist(filtered_results: list[dict[str, Any]], top_n: int = 30) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for item in filtered_results:
        row = dict(item)
        row["composite_score"] = calculate_composite_score(row)
        enriched.append(row)
    enriched.sort(key=lambda x: (-float(x.get("composite_score") or 0.0), -float(x.get("fms_score") or 0.0), -float(x.get("str_percent") or 0.0), -float(x.get("sold_count") or 0.0), str(x.get("seed") or "")))
    return enriched[:top_n]
