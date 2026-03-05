"""Seed collector (Step 1).

Goal: programmatically assemble a wide pool of seed phrases (100-500+), with metadata:
- source: manual_seed | google_related | google_related_level2 | ...
- cluster: coarse cluster label (planner/template/checklist/journal/other)

This is intentionally pluggable: later you can add Etsy suggestions, eBay related, curated lists, etc.

NOTE: This module makes outbound HTTP requests (Google suggest endpoint). It is designed to run
in a networked environment (your server). Timeouts are short and failures degrade gracefully.
"""

from __future__ import annotations

import random
import time
from typing import Any
from urllib.parse import quote

import requests

from money_niche_hunter.utils.storage import save_json
from money_niche_hunter.config.settings import (
    RAW_SEEDS_PATH,
    SEEDS_COLLECTION_STATS_PATH,
)


SEED_EXPANSION_DEPTH = int(2)  # levels of related expansion
MAX_RELATED_PER_SEED = int(8)
MIN_QUERY_LENGTH = int(4)

BASE_SEEDS: list[str] = [
    "planner",
    "digital planner",
    "checklist",
    "template",
    "tracker",
    "budget template",
    "wedding planner",
    "habit tracker",
    "gratitude journal",
    "daily planner",
    "monthly planner",
    "notion template",
    "printable planner",
    "goal tracker",
    "meal planner",
    "fitness planner",
    "business planner",
]

CLUSTERS: dict[str, list[str]] = {
    "planner": ["planner", "schedule", "calendar", "organizer"],
    "template": ["template", "notion", "canva", "editable"],
    "checklist": ["checklist", "tracker", "list", "log"],
    "journal": ["journal", "notebook", "prompts", "reflection"],
}


def _detect_cluster(seed: str) -> str:
    seed_lower = seed.lower()
    for cluster_name, keywords in CLUSTERS.items():
        if any(kw in seed_lower for kw in keywords):
            return cluster_name
    return "other"


def _google_autocomplete(query: str) -> list[str]:
    """Google Suggest (autocomplete) via suggestqueries.google.com.

    Returns up to MAX_RELATED_PER_SEED suggestions.
    """
    url = f"https://suggestqueries.google.com/complete/search?client=firefox&q={quote(query)}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        suggestions = [str(item) for item in (data[1] or [])]
        out = [s for s in suggestions if len(s) >= MIN_QUERY_LENGTH]
        return out[:MAX_RELATED_PER_SEED]
    except Exception:
        return []


def _etsy_style_suggestions(query: str) -> list[str]:
    """Etsy-like suggestion expansion (via Google suggest on query variants)."""
    variations = [
        query,
        f"{query} etsy",
        f"{query} printable",
        f"{query} digital download",
        f"{query} template",
    ]
    results: list[str] = []
    for v in variations:
        results.extend(_google_autocomplete(v))
        time.sleep(0.25)

    # preserve order, unique
    uniq: list[str] = []
    seen: set[str] = set()
    for r in results:
        key = r.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        uniq.append(r.strip())
    return uniq[:MAX_RELATED_PER_SEED]


def expand_seeds(base_seeds: list[str] | None = None, depth: int = SEED_EXPANSION_DEPTH) -> list[dict[str, Any]]:
    base = base_seeds or BASE_SEEDS
    all_ideas: list[dict[str, Any]] = []
    seen: set[str] = set()

    for seed in base:
        s = seed.strip()
        if not s:
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)

        all_ideas.append(
            {
                "seed": s,
                "source": "manual_seed",
                "cluster": _detect_cluster(s),
                "level": 0,
            }
        )

        related1: list[str] = []
        if depth >= 1:
            related1 = _etsy_style_suggestions(s)
            for r in related1:
                rk = r.lower()
                if rk in seen or len(r) < 8:
                    continue
                seen.add(rk)
                all_ideas.append(
                    {
                        "seed": r,
                        "source": "google_related",
                        "cluster": _detect_cluster(r),
                        "level": 1,
                        "parent": s,
                    }
                )

        if depth >= 2 and related1:
            for r1 in related1[:4]:
                related2 = _etsy_style_suggestions(r1)
                for r2 in related2:
                    r2k = r2.lower()
                    if r2k in seen or len(r2) < 8:
                        continue
                    seen.add(r2k)
                    all_ideas.append(
                        {
                            "seed": r2,
                            "source": "google_related_level2",
                            "cluster": _detect_cluster(r2),
                            "level": 2,
                            "parent": r1,
                        }
                    )
                time.sleep(random.uniform(0.35, 0.75))

        time.sleep(random.uniform(0.5, 1.0))

    return all_ideas


def collect_seeds() -> list[dict[str, Any]]:
    """Main entrypoint for Step 1."""
    seeds = expand_seeds(BASE_SEEDS, depth=SEED_EXPANSION_DEPTH)

    # Stats
    by_source: dict[str, int] = {}
    by_cluster: dict[str, int] = {}
    for x in seeds:
        by_source[x["source"]] = by_source.get(x["source"], 0) + 1
        by_cluster[x["cluster"]] = by_cluster.get(x["cluster"], 0) + 1

    save_json(seeds, RAW_SEEDS_PATH)
    save_json(
        {
            "total": len(seeds),
            "by_source": dict(sorted(by_source.items(), key=lambda kv: (-kv[1], kv[0]))),
            "by_cluster": dict(sorted(by_cluster.items(), key=lambda kv: (-kv[1], kv[0]))),
            "collected_at": time.strftime("%Y-%m-%d %H:%M"),
        },
        SEEDS_COLLECTION_STATS_PATH,
    )
    return seeds
