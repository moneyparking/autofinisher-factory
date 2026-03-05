from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from money_niche_hunter.config.settings import ANALYTICS_PATH, BATCH_RESULTS_PATH, SHORTLIST_PATH
from money_niche_hunter.utils.storage import load_json, save_json


def analyze_sources(
    batch_results_path: str = BATCH_RESULTS_PATH,
    sanity_path: str = SHORTLIST_PATH,
) -> dict[str, Any]:
    batch: list[dict[str, Any]] = load_json(batch_results_path, default=[])
    sanity_list: list[dict[str, Any]] = load_json(sanity_path, default=[])

    seed_to_verdict = {str(item.get("seed")): item.get("sanity_verdict", "not_reviewed") for item in sanity_list}

    stats: dict[str, Any] = {
        "by_source": defaultdict(lambda: {"total": 0, "go": 0, "maybe": 0, "reject": 0, "candidates": 0}),
        "by_cluster": defaultdict(lambda: {"total": 0, "go": 0, "maybe": 0, "reject": 0, "candidates": 0}),
        "timestamp": datetime.now().isoformat(),
    }

    for item in batch:
        source = item.get("source", "unknown")
        cluster = item.get("cluster", "unknown")
        seed = item.get("seed")
        verdict = seed_to_verdict.get(seed, "not_reviewed")

        stats["by_source"][source]["total"] += 1
        stats["by_cluster"][cluster]["total"] += 1

        if verdict == "go":
            stats["by_source"][source]["go"] += 1
            stats["by_cluster"][cluster]["go"] += 1
        elif verdict == "maybe":
            stats["by_source"][source]["maybe"] += 1
            stats["by_cluster"][cluster]["maybe"] += 1
        elif verdict == "reject":
            stats["by_source"][source]["reject"] += 1
            stats["by_cluster"][cluster]["reject"] += 1
        else:
            # If not reviewed, count as candidate if it has a positive composite_score
            if float(item.get("composite_score") or 0.0) > 0.0:
                stats["by_source"][source]["candidates"] += 1
                stats["by_cluster"][cluster]["candidates"] += 1

    # Convert defaultdict
    stats["by_source"] = dict(stats["by_source"])
    stats["by_cluster"] = dict(stats["by_cluster"])

    for group in ("by_source", "by_cluster"):
        for key, data in stats[group].items():
            total = int(data.get("total") or 0)
            if total <= 0:
                continue
            go = int(data.get("go") or 0)
            maybe = int(data.get("maybe") or 0)
            data["go_rate"] = round(go / total * 100.0, 1)
            data["success_rate"] = round((go + maybe) / total * 100.0, 1)

    save_json(stats, ANALYTICS_PATH)
    return stats


def get_recommendations(stats: dict[str, Any]) -> list[str]:
    recs: list[str] = []
    by_source = stats.get("by_source") or {}
    for source, data in by_source.items():
        total = int(data.get("total") or 0)
        go_rate = float(data.get("go_rate") or 0.0)
        if total >= 10 and go_rate < 5.0:
            recs.append(f"deprioritize:{source}")
        if go_rate >= 25.0:
            recs.append(f"boost:{source}")
    return recs
