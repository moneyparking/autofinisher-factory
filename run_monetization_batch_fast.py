#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from monetization_pipeline_fast import main as run_monetization_pipeline_fast
from premium_sku_factory import build_all
from batch_reference_monitor import update_batch_monitoring

BASE_DIR = Path("/home/agent/autofinisher-factory")
OUTPUT_PATH = BASE_DIR / "niche_engine" / "accepted" / "niche_package.json"
SUMMARY_PATH = BASE_DIR / "publish_packets" / "summary.json"
REFERENCE_ALERTS_PATH = BASE_DIR / "data" / "batch_monitoring" / "reference_alerts.json"
REFERENCE_SUMMARY_PATH = BASE_DIR / "data" / "batch_monitoring" / "reference_batch_summary.json"


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def enrich_publish_summary_with_monitoring(summary_path: Path) -> dict[str, Any]:
    summary = load_json(summary_path, {})
    reference_summary = load_json(REFERENCE_SUMMARY_PATH, {})
    reference_alerts = load_json(REFERENCE_ALERTS_PATH, {})
    alerts = reference_alerts.get("alerts") or []
    alert_levels = sorted({str(x.get("level")) for x in alerts if x.get("level")})
    kpi = (reference_summary.get("kpi") or {}) if isinstance(reference_summary, dict) else {}
    monitoring = {
        "reference_summary_path": str(REFERENCE_SUMMARY_PATH.resolve()),
        "reference_alerts_path": str(REFERENCE_ALERTS_PATH.resolve()),
        "winner_yield": kpi.get("winner_yield"),
        "avg_fms_ratio_winners": kpi.get("avg_fms_ratio_winners"),
        "avg_sold_ratio_winners": kpi.get("avg_sold_ratio_winners"),
        "alerts_count": len(alerts),
        "alerts_levels": alert_levels,
    }
    if isinstance(summary, dict):
        summary["monitoring"] = monitoring
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return monitoring


def main() -> None:
    print("[run_monetization_batch_fast] phase 1/2: collecting and validating niches")
    run_monetization_pipeline_fast()
    if not OUTPUT_PATH.exists():
        raise SystemExit("[run_monetization_batch_fast] niche_package.json not created")

    payload = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    approved = len(payload.get("items", []))
    print(f"[run_monetization_batch_fast] approved niches: {approved}")

    batch_stats = payload.get("batch_stats") or {}
    monitor = update_batch_monitoring(
        batch_id=str(payload.get("batch_id") or batch_stats.get("batch_id") or "manual"),
        seeds_total=int(batch_stats.get("total_seeds") or 0),
    )
    alert_count = len((monitor.get("alerts") or {}).get("alerts", []))
    print(f"[run_monetization_batch_fast] reference alerts: {alert_count}")

    print("[run_monetization_batch_fast] phase 2/2: building premium sku packets")
    summary = build_all(limit=15)
    monitoring = enrich_publish_summary_with_monitoring(SUMMARY_PATH)
    print(f"[run_monetization_batch_fast] built_count: {summary['built_count']}")
    print(
        f"[run_monetization_batch_fast] monitoring: winner_yield={monitoring.get('winner_yield')} | "
        f"avg_fms_ratio_winners={monitoring.get('avg_fms_ratio_winners')} | alerts={monitoring.get('alerts_count')}"
    )
    print(f"[run_monetization_batch_fast] summary written to: {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
