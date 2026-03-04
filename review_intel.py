from __future__ import annotations

import re
from statistics import mean
from typing import Any

STRUCTURE_TOKENS = ["confusing", "hard to use", "not clear", "too small", "missing", "layout", "format", "organized", "organisation", "structure"]
QUALITY_TOKENS = ["blurry", "low quality", "pixel", "cheap", "poor quality", "bad design"]
POSITIVE_TOKENS = ["easy to use", "helpful", "beautiful", "well organized", "great quality", "love", "useful"]


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def review_intelligence(review_sample: list[dict[str, Any]]) -> dict[str, Any]:
    if not review_sample:
        return {
            "review_opportunity_score": 50.0,
            "complaint_density": 0.0,
            "positive_density": 0.0,
            "structure_issue_density": 0.0,
            "quality_issue_density": 0.0,
            "avg_review_rating": None,
        }

    complaint_hits = 0
    positive_hits = 0
    structure_hits = 0
    quality_hits = 0
    ratings = []

    for review in review_sample:
        text = normalize(review.get("text", ""))
        rating = review.get("rating")
        if isinstance(rating, (int, float)):
            ratings.append(float(rating))
        if any(token in text for token in STRUCTURE_TOKENS + QUALITY_TOKENS):
            complaint_hits += 1
        if any(token in text for token in STRUCTURE_TOKENS):
            structure_hits += 1
        if any(token in text for token in QUALITY_TOKENS):
            quality_hits += 1
        if any(token in text for token in POSITIVE_TOKENS):
            positive_hits += 1

    total = max(len(review_sample), 1)
    complaint_density = complaint_hits / total
    positive_density = positive_hits / total
    structure_issue_density = structure_hits / total
    quality_issue_density = quality_hits / total

    opportunity = 50.0 + (structure_issue_density * 25.0) + (quality_issue_density * 20.0) + (complaint_density * 10.0) - (positive_density * 8.0)
    return {
        "review_opportunity_score": round(max(0.0, min(100.0, opportunity)), 2),
        "complaint_density": round(complaint_density, 3),
        "positive_density": round(positive_density, 3),
        "structure_issue_density": round(structure_issue_density, 3),
        "quality_issue_density": round(quality_issue_density, 3),
        "avg_review_rating": round(mean(ratings), 2) if ratings else None,
    }
