"""money_niche_hunter configuration.

This module defines thresholds and weights for the hybrid idea pipeline:
- Hard filters (data-quality and obvious market-dead rules)
- Composite scoring
- Shortlist size

All thresholds are intentionally conservative defaults; tune after a few runs.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Thresholds:
    # Data-quality
    min_confidence: str = "high"  # only treat high as market-truth

    # Market dead / weak signals
    min_sold_count: int = 1
    min_str_percent: float = 0.3  # percent, not ratio

    # Competition heuristics (optional)
    max_active_count: int = 800

    # Etsy signal hygiene
    min_digital_share: float = 0.25


@dataclass(frozen=True)
class Weights:
    # composite_score = w1*fms_score_norm + w2*str_norm + w3*sold_norm + w4*digital_share
    fms_score: float = 0.45
    sold_count: float = 0.25
    str_percent: float = 0.20
    digital_share: float = 0.10


THRESHOLDS = Thresholds()
WEIGHTS = Weights()

# Shortlist size
TOP_N = 30

# Default output paths (relative to repo root)
RAW_SEEDS_PATH = "money_niche_hunter/data/raw_seeds.json"
BATCH_RESULTS_PATH = "money_niche_hunter/data/batch_results.json"
SHORTLIST_PATH = "money_niche_hunter/data/shortlist_candidates.json"
SANITY_OUTPUT_PATH = "money_niche_hunter/data/shortlist_candidates.json"  # in-place update
ANALYTICS_PATH = "money_niche_hunter/data/source_analytics.json"
SEEDS_COLLECTION_STATS_PATH = "money_niche_hunter/data/seeds_collection_stats.json"
