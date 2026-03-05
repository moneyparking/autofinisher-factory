"""Money Niche Hunter — hybrid idea pipeline.

Implements Steps 1–7:
1) collect raw seeds (programmatic expansion)
2) run seeds through existing monetization batch contour
3) hard filter obvious trash + data-broken
4) score + shortlist
5) (optional) LLM sanity check on shortlist
6–7) analytics + feedback recommendations

Run:
    python3 -m money_niche_hunter

Config:
- money_niche_hunter/config/settings.py
- optional .env with OPENAI_API_KEY for step 5
"""

from __future__ import annotations

from pathlib import Path

from money_niche_hunter.config.settings import (
    BATCH_RESULTS_PATH,
    RAW_SEEDS_PATH,
    SHORTLIST_PATH,
    TOP_N,
)
from money_niche_hunter.utils.storage import save_json


def step_1_collect_seeds() -> list[dict]:
    from money_niche_hunter.core.seeds.collector import collect_seeds

    seeds = collect_seeds()
    return seeds


def step_2_run_batch(seeds: list[dict]) -> list[dict]:
    from money_niche_hunter.core.pipeline.runner import run_batch

    return run_batch(seeds)


def step_3_hard_filter(batch_results: list[dict]) -> tuple[list[dict], list[dict]]:
    from money_niche_hunter.core.analysis.filters import apply_hard_filters

    return apply_hard_filters(batch_results)


def step_4_create_shortlist(filtered: list[dict]) -> list[dict]:
    from money_niche_hunter.core.analysis.scorer import create_shortlist

    shortlist = create_shortlist(filtered, TOP_N)
    save_json(shortlist, SHORTLIST_PATH)
    return shortlist


def step_5_llm_sanity_check() -> list[dict]:
    from money_niche_hunter.core.review.llm_sanity import run_sanity_check

    return run_sanity_check()


def step_6_7_analytics() -> dict:
    from money_niche_hunter.core.analysis.analytics import analyze_sources

    return analyze_sources()


def main() -> None:
    Path("money_niche_hunter/data").mkdir(parents=True, exist_ok=True)

    seeds = step_1_collect_seeds()
    save_json(seeds, RAW_SEEDS_PATH)

    batch = step_2_run_batch(seeds)
    save_json(batch, BATCH_RESULTS_PATH)

    filtered, data_bucket = step_3_hard_filter(batch)
    save_json(data_bucket, "money_niche_hunter/data/data_bucket.json")

    shortlist = step_4_create_shortlist(filtered)

    # Optional Step 5 if OPENAI_API_KEY configured
    try:
        reviewed = step_5_llm_sanity_check()
        if reviewed:
            shortlist = reviewed
    except Exception:
        # keep pipeline usable without LLM keys
        pass

    stats = step_6_7_analytics()
    save_json(stats, "money_niche_hunter/data/run_stats.json")

    print("[money_niche_hunter] done")
    print(f"- raw seeds: {RAW_SEEDS_PATH}")
    print(f"- batch results: {BATCH_RESULTS_PATH}")
    print(f"- shortlist: {SHORTLIST_PATH}")


if __name__ == "__main__":
    main()
