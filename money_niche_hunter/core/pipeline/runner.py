"""Batch runner (Step 2).

This runner intentionally reuses the existing project batch contour:
- It generates a temporary vertical_families JSON (compatible with monetization_pipeline_fast)
- It invokes run_monetization_batch_fast.py with VERTICALS_PATH pointing to that file
- It parses niche_engine/accepted/seed_statuses.json (the checkpointed source of truth)
- It produces a flat list of rows: one row per input seed (idea)

Why this design:
- No duplication of the monetization pipeline
- Keeps source-of-truth in existing accepted artifacts
- Deterministic and replayable (raw_seeds.json → vertical_families → seed_statuses)
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from money_niche_hunter.config.settings import BATCH_RESULTS_PATH
from money_niche_hunter.utils.storage import load_json, save_json


REPO_ROOT = Path("/home/agent/autofinisher-factory")
RUNNER = REPO_ROOT / "run_monetization_batch_fast.py"
ACCEPTED_SEED_STATUSES = REPO_ROOT / "niche_engine" / "accepted" / "seed_statuses.json"


def _make_vertical_families_payload(seeds: list[dict[str, Any]], *, name: str = "money_niche_hunter") -> dict[str, Any]:
    seed_keywords: list[dict[str, Any]] = []
    for s in seeds:
        seed_keywords.append({"seed": s.get("seed"), "bucket": s.get("cluster")})

    return {
        "vertical_families": [
            {
                "name": name,
                "seed_keywords": seed_keywords,
            }
        ]
    }


def _pick_primary_decision(seed: str, niche_decisions: list[dict[str, Any]]) -> dict[str, Any] | None:
    seed_norm = str(seed or "").strip().lower()
    for d in niche_decisions:
        if str(d.get("niche") or "").strip().lower() == seed_norm:
            return d
    return niche_decisions[0] if niche_decisions else None


def run_batch(seeds: list[dict[str, Any]], *, vertical_name: str = "money_niche_hunter") -> list[dict[str, Any]]:
    """Run Step 2. Returns a list of batch result rows (one per seed)."""

    REPO_ROOT.mkdir(parents=True, exist_ok=True)

    tmp_verticals_path = REPO_ROOT / "money_niche_hunter" / "data" / "vertical_families_raw.json"
    payload = _make_vertical_families_payload(seeds, name=vertical_name)
    save_json(payload, tmp_verticals_path)

    env = os.environ.copy()
    env["VERTICALS_PATH"] = str(tmp_verticals_path)

    # Respect existing .env.scrape.local if present (runner already loads via shell in normal usage);
    # here we rely on the environment having the right config in the invoking context.
    cmd = ["python3", str(RUNNER)]
    subprocess.check_call(cmd, cwd=str(REPO_ROOT), env=env)

    statuses = load_json(ACCEPTED_SEED_STATUSES, default={})
    items = statuses.get("items") or []

    # Map seed -> record (first match)
    seed_to_item: dict[str, dict[str, Any]] = {}
    for it in items:
        key = str(it.get("seed") or "").strip().lower()
        if key and key not in seed_to_item:
            seed_to_item[key] = it

    rows: list[dict[str, Any]] = []
    for s in seeds:
        seed = str(s.get("seed") or "").strip()
        key = seed.lower()
        it = seed_to_item.get(key)
        if not it:
            rows.append(
                {
                    "seed": seed,
                    "source": s.get("source", "unknown"),
                    "cluster": s.get("cluster", "unknown"),
                    "batch_id": statuses.get("batch_id"),
                    "status": "missing",
                    "decision_type": "data_reject",
                    "reason_code": "missing_seed_result",
                    "reason_detail": "seed not present in seed_statuses.json",
                }
            )
            continue

        decisions = it.get("niche_decisions") or []
        primary = _pick_primary_decision(seed, decisions)
        dq = (primary or {}).get("data_quality") or {}

        rows.append(
            {
                "seed": seed,
                "source": s.get("source", it.get("source") or "unknown"),
                "cluster": s.get("cluster", it.get("bucket") or "unknown"),
                "batch_id": statuses.get("batch_id"),
                "seed_status": it.get("status"),
                "google_status": it.get("google_status"),
                "etsy_status": it.get("etsy_status"),
                "status": (primary or {}).get("status"),
                "decision_type": (primary or {}).get("decision_type"),
                "reason_code": (primary or {}).get("reason_code"),
                "reason_detail": (primary or {}).get("reason_detail"),
                "fms_score": (primary or {}).get("fms_score"),
                "str_percent": (primary or {}).get("str_percent"),
                "active_count": (primary or {}).get("active_count"),
                "sold_count": (primary or {}).get("sold_count"),
                "etsy_digital_share": (primary or {}).get("etsy_digital_share"),
                "etsy_total_results": (primary or {}).get("etsy_total_results"),
                "avg_reviews_top": (primary or {}).get("avg_reviews_top"),
                "overall_confidence": dq.get("overall_confidence"),
                "overall_completeness": dq.get("overall_completeness"),
                "degraded_sources": dq.get("degraded_sources") or [],
                "warnings": dq.get("warnings") or [],
                # placeholders for future ratio-calcs (hook into fms_reference later)
                "fms_ratio": None,
                "str_ratio": None,
                "sold_ratio": None,
            }
        )

    save_json(rows, BATCH_RESULTS_PATH)
    return rows
