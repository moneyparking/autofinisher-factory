from __future__ import annotations

from typing import Any


def compute_fms_components(
    etsy_metrics: dict[str, Any],
    ebay_metrics: dict[str, Any],
    real_performance: dict[str, Any] | None = None,
) -> dict[str, float]:
    total_results = etsy_metrics.get("total_results") or 0
    digital_share = float(etsy_metrics.get("digital_share") or 0.0)
    avg_reviews_top = float(etsy_metrics.get("avg_reviews_top") or 0.0)

    str_percent = float(ebay_metrics.get("str_percent") or 0.0)
    sold_count = int(ebay_metrics.get("sold_count") or 0)
    active_count = int(ebay_metrics.get("active_count") or 0)

    demand_score = min(1.0, (digital_share * 0.6) + (avg_reviews_top / 300.0) * 0.4)
    liquidity_score = min(1.0, (str_percent / 30.0) * 0.7 + (sold_count / 100.0) * 0.3)

    price_power_score = 0.5
    if total_results:
        try:
            total_results_int = int(total_results)
            if 50 <= total_results_int <= 5000:
                price_power_score += 0.1
        except Exception:
            pass
    price_power_score = min(1.0, price_power_score)

    production_ease_score = 0.8
    if active_count > 5000:
        production_ease_score = 0.6

    distribution_fit_score = 0.8 if digital_share >= 0.4 else 0.4

    real_perf_score = 0.0
    if real_performance:
        etsy = real_performance.get("etsy") or {}
        conversion_rate = float(etsy.get("conversion_rate") or 0.0)
        sales_7d = int(etsy.get("sales_7d") or 0)
        real_perf_score = min(1.0, conversion_rate * 10.0 + sales_7d / 20.0)

    return {
        "demand_score": round(demand_score, 4),
        "liquidity_score": round(liquidity_score, 4),
        "price_power_score": round(price_power_score, 4),
        "production_ease_score": round(production_ease_score, 4),
        "distribution_fit_score": round(distribution_fit_score, 4),
        "real_performance_score": round(real_perf_score, 4),
    }


def compute_fms_score(components: dict[str, float]) -> float:
    weights = {
        "demand_score": 0.25,
        "liquidity_score": 0.25,
        "price_power_score": 0.15,
        "production_ease_score": 0.15,
        "distribution_fit_score": 0.15,
        "real_performance_score": 0.05,
    }
    fms = 0.0
    for key, value in components.items():
        fms += weights.get(key, 0.0) * float(value)
    return round(fms * 100.0, 2)