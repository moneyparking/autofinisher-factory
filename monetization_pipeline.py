from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from monetization_scorer import ranking_payload
from niche_profit_engine import get_ebay_metrics, get_google_suggests

BASE_DIR = Path("/home/agent/autofinisher-factory")
VERTICALS_PATH = BASE_DIR / "vertical_families.json"
ACCEPTED_DIR = BASE_DIR / "niche_engine" / "accepted"
OUTPUT_PATH = ACCEPTED_DIR / "niche_package.json"
TARGET_COUNT = 50
MIN_MONETIZATION_SCORE = 45.0
MIN_ACTIVE = 10
MAX_ACTIVE = 5000


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


def load_verticals() -> list[dict[str, Any]]:
    if not VERTICALS_PATH.exists():
        return []
    payload = json.loads(VERTICALS_PATH.read_text(encoding="utf-8"))
    families = payload.get("vertical_families", [])
    return [f for f in families if isinstance(f, dict)]


def candidate_seeds(verticals: list[dict[str, Any]]) -> list[tuple[str, str]]:
    seeds: list[tuple[str, str]] = []
    for vertical in verticals:
        vname = str(vertical.get("name", "general"))
        for seed in vertical.get("seed_keywords", []):
            seeds.append((vname, str(seed)))
    return seeds


def collect_candidates() -> list[dict[str, Any]]:
    seen = set()
    approved = []

    for vertical, seed in candidate_seeds(load_verticals()):
        print(f"[monetization_pipeline] seed: {seed} ({vertical})")
        suggestions = [seed]
        try:
            suggestions.extend(get_google_suggests(seed))
        except Exception as exc:
            print(f"[monetization_pipeline] Google suggest failed for {seed}: {exc}")

        for suggestion in suggestions:
            niche = normalize(suggestion)
            if not niche or niche in seen:
                continue
            seen.add(niche)

            try:
                metrics = get_ebay_metrics(niche)
            except Exception as exc:
                print(f"[monetization_pipeline] eBay metrics failed for {niche}: {exc}")
                continue

            active = int(metrics.get("active", 0) or 0)
            sold = int(metrics.get("sold", 0) or 0)
            str_value = round((sold / active) * 100, 2) if active > 0 else 0.0
            item = {
                "niche": niche,
                "vertical": vertical,
                "metrics": {
                    "active_listings": active,
                    "sold_listings": sold,
                    "sell_through_rate": str_value,
                },
            }
            rank = ranking_payload(item)
            item["ranking"] = rank
            item["suggested_price"] = rank["suggested_price"]

            if active < MIN_ACTIVE or active > MAX_ACTIVE:
                continue
            if rank["monetization_score"] < MIN_MONETIZATION_SCORE:
                continue
            if sold <= 0:
                continue

            approved.append(item)
            print(
                f"[monetization_pipeline] approved: {niche} | score={rank['monetization_score']} | "
                f"STR={str_value}% | active={active} sold={sold}"
            )

    approved.sort(
        key=lambda item: (
            -float(item["ranking"]["monetization_score"]),
            -float(item["metrics"]["sell_through_rate"]),
            -float(item["ranking"]["etsy_fit"]),
            item["niche"],
        )
    )
    return approved[:TARGET_COUNT]


def write_output(items: list[dict[str, Any]]) -> dict[str, Any]:
    ACCEPTED_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "2.0",
        "generated_at": now_iso(),
        "strategy": "monetization_pipeline_v1",
        "accepted_count": len(items),
        "items": items,
        "niches": items,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    items = collect_candidates()
    payload = write_output(items)
    print(f"[monetization_pipeline] wrote {payload['accepted_count']} niches to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
