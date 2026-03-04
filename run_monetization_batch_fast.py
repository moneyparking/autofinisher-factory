#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from monetization_pipeline_fast import main as run_monetization_pipeline_fast
from premium_sku_factory import build_all

BASE_DIR = Path("/home/agent/autofinisher-factory")
OUTPUT_PATH = BASE_DIR / "niche_engine" / "accepted" / "niche_package.json"
SUMMARY_PATH = BASE_DIR / "publish_packets" / "summary.json"


def main() -> None:
    print("[run_monetization_batch_fast] phase 1/2: collecting and validating niches")
    run_monetization_pipeline_fast()
    if not OUTPUT_PATH.exists():
        raise SystemExit("[run_monetization_batch_fast] niche_package.json not created")

    payload = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    approved = len(payload.get("items", []))
    print(f"[run_monetization_batch_fast] approved niches: {approved}")

    print("[run_monetization_batch_fast] phase 2/2: building premium sku packets")
    summary = build_all(limit=15)
    print(f"[run_monetization_batch_fast] built_count: {summary['built_count']}")
    print(f"[run_monetization_batch_fast] summary written to: {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
