"""Hard filters (Step 3).

Rules:
1) Remove data-broken rows from market truth:
   - decision_type in {data_reject, data_uncertain}
   - overall_confidence != high
2) Remove clearly dead markets:
   - active_count == 0 and sold_count == 0
   - sold_count < min_sold_count and str_percent < min_str_percent
3) Optionally remove overheated / weak-digital niches
"""

from __future__ import annotations

from typing import Any

from money_niche_hunter.config.settings import THRESHOLDS


def apply_hard_filters(batch_results: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    filtered: list[dict[str, Any]] = []
    data_bucket: list[dict[str, Any]] = []

    for item in batch_results:
        decision_type = str(item.get("decision_type") or "")
        confidence = str(item.get("overall_confidence") or "")

        # Data-broken bucket
        if decision_type in {"data_reject", "data_uncertain"} or confidence != THRESHOLDS.min_confidence:
            data_bucket.append(item)
            continue

        active = int(item.get("active_count") or 0)
        sold = int(item.get("sold_count") or 0)
        str_percent = float(item.get("str_percent") or 0.0)
        digital_share = float(item.get("etsy_digital_share") or 0.0)

        # Clearly dead markets
        if active == 0 and sold == 0:
            continue

        # Weak demand + weak conversion
        if sold < THRESHOLDS.min_sold_count and str_percent < THRESHOLDS.min_str_percent:
            continue

        # Overheated (optional heuristic)
        if active > THRESHOLDS.max_active_count:
            continue

        # Weak digital fit
        if digital_share < THRESHOLDS.min_digital_share:
            continue

        filtered.append(item)

    return filtered, data_bucket
