#!/usr/bin/env python3
from __future__ import annotations

import json
import traceback
from pathlib import Path
from typing import Any

from monetization_pipeline_fast import main as run_monetization_pipeline_fast
from premium_sku_factory import build_all
from batch_reference_monitor import update_batch_monitoring

BASE_DIR = Path("/home/agent/autofinisher-factory")
ACCEPTED_DIR = BASE_DIR / "niche_engine" / "accepted"
OUTPUT_PATH = ACCEPTED_DIR / "niche_package.json"
SEED_STATUS_PATH = ACCEPTED_DIR / "seed_statuses.json"
BATCH_PROGRESS_PATH = ACCEPTED_DIR / "batch_progress.json"
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


def update_batch_progress_status(batch_status: str) -> dict[str, Any]:
    progress = load_json(BATCH_PROGRESS_PATH, {})
    if not isinstance(progress, dict):
        progress = {}
    progress["batch_status"] = str(batch_status)
    progress["updated_at"] = progress.get("updated_at") or None
    BATCH_PROGRESS_PATH.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")

    seed_statuses = load_json(SEED_STATUS_PATH, {})
    if isinstance(seed_statuses, dict):
        seed_statuses["batch_status"] = str(batch_status)
        SEED_STATUS_PATH.write_text(json.dumps(seed_statuses, ensure_ascii=False, indent=2), encoding="utf-8")

    payload = load_json(OUTPUT_PATH, {})
    if isinstance(payload, dict):
        payload["batch_status"] = str(batch_status)
        payload.setdefault("processed_seeds", progress.get("processed_seeds"))
        payload.setdefault("total_seeds", progress.get("total_seeds"))
        OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return progress



def run_batch_reference_monitor() -> dict[str, Any]:
    progress = load_json(BATCH_PROGRESS_PATH, {})
    seed_statuses = load_json(SEED_STATUS_PATH, {})
    batch_id = str(
        progress.get("batch_id")
        or seed_statuses.get("batch_id")
        or (load_json(OUTPUT_PATH, {}) or {}).get("batch_id")
        or "manual"
    )
    batch_status = str(progress.get("batch_status") or seed_statuses.get("batch_status") or "unknown")
    processed_seeds = int(progress.get("processed_seeds") or seed_statuses.get("processed_seeds") or seed_statuses.get("seed_count") or 0)
    total_seeds = int(progress.get("total_seeds") or seed_statuses.get("total_seeds") or (seed_statuses.get("batch_stats") or {}).get("total_seeds_planned") or (seed_statuses.get("batch_stats") or {}).get("total_seeds") or processed_seeds)

    return update_batch_monitoring(
        batch_id=batch_id,
        total_seeds=total_seeds,
        processed_seeds=processed_seeds,
        batch_status=batch_status,
    )



def enrich_publish_summary_with_monitoring(summary_path: Path, *, batch_status: str | None = None) -> dict[str, Any]:
    summary = load_json(summary_path, {})
    reference_summary = load_json(REFERENCE_SUMMARY_PATH, {})
    reference_alerts = load_json(REFERENCE_ALERTS_PATH, {})
    progress = load_json(BATCH_PROGRESS_PATH, {})
    alerts = reference_alerts.get("alerts") or []
    alert_levels = sorted({str(x.get("level")) for x in alerts if x.get("level")})
    kpi = (reference_summary.get("kpi") or {}) if isinstance(reference_summary, dict) else {}
    monitoring = {
        "reference_summary_path": str(REFERENCE_SUMMARY_PATH.resolve()),
        "reference_alerts_path": str(REFERENCE_ALERTS_PATH.resolve()),
        "batch_status": batch_status or reference_summary.get("batch_status") or progress.get("batch_status"),
        "processed_seeds": reference_summary.get("processed_seeds") or progress.get("processed_seeds"),
        "total_seeds": reference_summary.get("total_seeds") or progress.get("total_seeds"),
        "winner_yield": kpi.get("winner_yield"),
        "winner_yield_raw": kpi.get("winner_yield_raw"),
        "winner_yield_reliable": kpi.get("winner_yield_reliable"),
        "reliable_seed_count": kpi.get("reliable_seed_count"),
        "network_retry_events_total": kpi.get("network_retry_events_total"),
        "network_retry_seeds": kpi.get("network_retry_seeds"),
        "data_reject_total": kpi.get("data_reject_total"),
        "data_uncertain_total": kpi.get("data_uncertain_total"),
        "market_reject_total": kpi.get("market_reject_total"),
        "market_candidate_total": kpi.get("market_candidate_total"),
        "market_accept_total": kpi.get("market_accept_total"),
        "source_failure_counts": kpi.get("source_failure_counts") or {},
        "confidence_breakdown": reference_summary.get("confidence_breakdown") or {},
        "source_failure_breakdown": reference_summary.get("source_failure_breakdown") or {},
        "avg_fms_ratio_winners": kpi.get("avg_fms_ratio_winners"),
        "avg_sold_ratio_winners": kpi.get("avg_sold_ratio_winners"),
        "alerts_count": len(alerts),
        "alerts_levels": alert_levels,
    }
    if isinstance(summary, dict):
        summary["batch_status"] = monitoring.get("batch_status")
        summary["processed_seeds"] = monitoring.get("processed_seeds")
        summary["total_seeds"] = monitoring.get("total_seeds")
        summary["monitoring"] = monitoring
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return monitoring


def main() -> None:
    batch_status = "running"
    summary: dict[str, Any] = {}

    try:
        print("[run_monetization_batch_fast] phase 1/2: collecting and validating niches")
        run_monetization_pipeline_fast()
        if not OUTPUT_PATH.exists():
            raise SystemExit("[run_monetization_batch_fast] niche_package.json not created")

        payload = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        approved = len(payload.get("items", []))
        print(f"[run_monetization_batch_fast] approved niches: {approved}")

        batch_status = str(payload.get("batch_status") or "completed")
        if batch_status == "running":
            batch_status = "completed"
        update_batch_progress_status(batch_status)

        print("[run_monetization_batch_fast] phase 2/2: building premium sku packets")
        summary = build_all(limit=15)

    except KeyboardInterrupt:
        print("\n[run_monetization_batch_fast] interrupted by user (Ctrl+C)")
        batch_status = "partial"

    except Exception as exc:
        print(f"\n[run_monetization_batch_fast] critical pipeline error: {exc}")
        traceback.print_exc()
        batch_status = "partial"

    finally:
        print(f"[run_monetization_batch_fast] finalizing batch with status: {batch_status}")
        progress = update_batch_progress_status(batch_status)
        monitor = run_batch_reference_monitor()
        alert_count = len((monitor.get("alerts") or {}).get("alerts", []))
        print(f"[run_monetization_batch_fast] reference alerts: {alert_count}")

        if not SUMMARY_PATH.exists():
            try:
                summary = build_all(limit=15)
            except Exception as exc:
                print(f"[run_monetization_batch_fast] build_all failed during finalization: {exc}")
                summary = {"built_count": 0}

        monitoring = enrich_publish_summary_with_monitoring(SUMMARY_PATH, batch_status=batch_status)
        print(f"[run_monetization_batch_fast] built_count: {summary.get('built_count', 0)}")
        print(
            f"[run_monetization_batch_fast] monitoring: batch_status={monitoring.get('batch_status')} | "
            f"processed={monitoring.get('processed_seeds')}/{monitoring.get('total_seeds')} | "
            f"winner_yield_raw={monitoring.get('winner_yield_raw')} | "
            f"winner_yield_reliable={monitoring.get('winner_yield_reliable')} | "
            f"data_reject_total={monitoring.get('data_reject_total')} | alerts={monitoring.get('alerts_count')}"
        )
        print(f"[run_monetization_batch_fast] summary written to: {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
