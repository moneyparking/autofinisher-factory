from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Any


def competitor_profile(listings: list[dict[str, Any]]) -> dict[str, Any]:
    if not listings:
        return {
            "competition_profile_score": 50.0,
            "unique_shops": 0,
            "shop_concentration": 0.0,
            "dominant_shop_share": 0.0,
            "avg_reviews_top": None,
        }

    shops = [str(x.get("shop_name") or "").strip().lower() for x in listings if str(x.get("shop_name") or "").strip()]
    counts = Counter(shops)
    unique_shops = len(counts)
    total_shop_refs = sum(counts.values())
    dominant_shop_share = (max(counts.values()) / total_shop_refs) if counts and total_shop_refs else 0.0
    shop_concentration = sum((count / total_shop_refs) ** 2 for count in counts.values()) if total_shop_refs else 0.0
    reviews = [int(x.get("reviews_count")) for x in listings if isinstance(x.get("reviews_count"), int)]
    avg_reviews_top = round(mean(reviews), 2) if reviews else None

    # Lower concentration is better; very review-heavy incumbents increase competition.
    base = 60.0
    base -= dominant_shop_share * 25.0
    base -= shop_concentration * 20.0
    if avg_reviews_top is not None:
        if avg_reviews_top > 500:
            base -= 12.0
        elif avg_reviews_top > 200:
            base -= 8.0
        elif avg_reviews_top < 50:
            base += 6.0

    return {
        "competition_profile_score": round(max(0.0, min(100.0, base)), 2),
        "unique_shops": unique_shops,
        "shop_concentration": round(shop_concentration, 3),
        "dominant_shop_share": round(dominant_shop_share, 3),
        "avg_reviews_top": avg_reviews_top,
    }
