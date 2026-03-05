from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path("/home/agent/autofinisher-factory")
VALIDATED_DIR = BASE_DIR / "data" / "validated_niches" / "items"
MONITOR_DIR = BASE_DIR / "data" / "batch_monitoring"
HISTORY_PATH = MONITOR_DIR / "batch_kpi_history.json"
ALERTS_PATH = MONITOR_DIR / "reference_alerts.json"
SUMMARY_PATH = MONITOR_DIR / "reference_batch_summary.json"
ROLLING_WINDOW = 20
STATIC_WARN_YIELD = 0.18
STATIC_WARN_FMS_RATIO = 0.8
STATIC_CRIT_YIELD = 0.1
STATIC_CRIT_FMS_RATIO = 0.6
YIELD_WARN_STD_K = 2.0
YIELD_CRIT_STD_K = 3.0
FMS_WARN_STD_K = 2.0
FMS_CRIT_STD_K = 3.0


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def stddev(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    m = mean(values)
    if m is None:
        return None
    variance = sum((x - m) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(variance)


def dynamic_threshold(history_values: list[float], static_floor: float, warn_k: float, crit_k: float) -> dict[str, float | None]:
    hist_mean = mean(history_values)
    hist_std = stddev(history_values)
    warn = None
    crit = None
    if hist_mean is not None and hist_std is not None:
        warn = max(static_floor, hist_mean - warn_k * hist_std)
        crit = max(static_floor - 0.1, hist_mean - crit_k * hist_std)
    return {
        "mean_hist": hist_mean,
        "std_hist": hist_std,
        "dyn_warn": warn,
        "dyn_crit": crit,
    }


def collect_validated_items(batch_id: str) -> list[dict[str, Any]]:
    VALIDATED_DIR.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, Any]] = []
    for path in sorted(VALIDATED_DIR.glob("*.json")):
        payload = load_json(path, {})
        if not isinstance(payload, dict):
            continue
        if str(payload.get("batch_id") or "") != str(batch_id):
            continue
        items.append(payload)
    return items


def average_ratio(items: list[dict[str, Any]], key: str) -> float | None:
    values: list[float] = []
    for item in items:
        ratio = safe_float((item.get("vs_reference") or {}).get(key))
        if ratio is not None:
            values.append(ratio)
    return mean(values)


def is_reliable_item(item: dict[str, Any]) -> bool:
    decision_type = str(item.get("decision_type") or (item.get("validation") or {}).get("decision_type") or "")
    overall_conf = str((item.get("data_quality") or {}).get("overall_confidence") or "high")
    critical_failed = list((item.get("data_quality") or {}).get("critical_sources_failed") or [])
    return decision_type in {"market_accept", "market_candidate", "market_reject"} and overall_conf == "high" and not critical_failed



def build_breakdown(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key) or (item.get("validation") or {}).get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: (-x[1], x[0])))



def build_confidence_breakdown(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str((item.get("data_quality") or {}).get("overall_confidence") or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: (-x[1], x[0])))



def build_source_failure_breakdown(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        source_quality = item.get("source_quality") or {}
        if not isinstance(source_quality, dict):
            continue
        for source_name, payload in source_quality.items():
            if not isinstance(payload, dict):
                continue
            source_status = str(payload.get("source_status") or payload.get("final_status") or "ok")
            if source_status == "failed":
                key = f"{source_name}_failed"
                counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: (-x[1], x[0])))



def count_decision_types(items: list[dict[str, Any]]) -> dict[str, int]:
    totals = {
        "data_reject_total": 0,
        "data_uncertain_total": 0,
        "market_reject_total": 0,
        "market_candidate_total": 0,
        "market_accept_total": 0,
    }
    for item in items:
        decision_type = str(item.get("decision_type") or (item.get("validation") or {}).get("decision_type") or "")
        if decision_type == "data_reject":
            totals["data_reject_total"] += 1
        elif decision_type == "data_uncertain":
            totals["data_uncertain_total"] += 1
        elif decision_type == "market_reject":
            totals["market_reject_total"] += 1
        elif decision_type == "market_candidate":
            totals["market_candidate_total"] += 1
        elif decision_type == "market_accept":
            totals["market_accept_total"] += 1
    return totals



def compute_retry_metrics(items: list[dict[str, Any]]) -> dict[str, Any]:
    network_retry_events_total = 0
    network_retry_seeds = 0
    ebay_failed_requests = 0
    etsy_failed_requests = 0
    google_failed_requests = 0

    for item in items:
        source_quality = item.get("source_quality") or {}
        if not isinstance(source_quality, dict):
            continue
        item_had_retry = False
        for source_name, payload in source_quality.items():
            if not isinstance(payload, dict):
                continue
            retry_count = int(payload.get("retry_count") or 0)
            network_retry_events_total += retry_count
            if retry_count > 0:
                item_had_retry = True
            source_status = str(payload.get("source_status") or payload.get("final_status") or "ok")
            if source_status == "failed":
                if source_name == "ebay":
                    ebay_failed_requests += 1
                elif source_name == "etsy":
                    etsy_failed_requests += 1
                elif source_name == "google":
                    google_failed_requests += 1
        if item_had_retry:
            network_retry_seeds += 1

    return {
        "network_retry_events_total": network_retry_events_total,
        "network_retry_seeds": network_retry_seeds,
        "source_failure_counts": {
            "ebay_failed_requests": ebay_failed_requests,
            "etsy_failed_requests": etsy_failed_requests,
            "google_failed_requests": google_failed_requests,
        },
    }



def compute_batch_kpi(batch_id: str, seeds_total: int) -> dict[str, Any]:
    items = collect_validated_items(batch_id)
    reliable_items = [x for x in items if is_reliable_item(x)]
    winners = [x for x in reliable_items if str(x.get("status")) == "winner"]
    candidates = [x for x in reliable_items if str(x.get("status")) == "candidate"]
    reliable_seed_count = len(reliable_items)
    retry_metrics = compute_retry_metrics(items)
    decision_totals = count_decision_types(items)

    winner_yield_raw = (len(winners) / max(1, seeds_total)) if seeds_total >= 0 else 0.0
    winner_yield_reliable = (len(winners) / max(1, reliable_seed_count)) if reliable_seed_count > 0 else 0.0
    kpi = {
        "batch_id": batch_id,
        "generated_at": now_iso(),
        "seeds_total": seeds_total,
        "validated_total": len(items),
        "reliable_validated_total": len(reliable_items),
        "reliable_seed_count": reliable_seed_count,
        "winners_total": len(winners),
        "candidates_total": len(candidates),
        "winner_yield": round(winner_yield_raw, 4),
        "winner_yield_raw": round(winner_yield_raw, 4),
        "winner_yield_reliable": round(winner_yield_reliable, 4),
        "avg_fms_ratio_winners": average_ratio(winners, "fms_ratio"),
        "avg_str_ratio_winners": average_ratio(winners, "str_ratio"),
        "avg_sold_ratio_winners": average_ratio(winners, "sold_ratio"),
        "median_fms_ratio_winners": median([safe_float((x.get("vs_reference") or {}).get("fms_ratio")) for x in winners if safe_float((x.get("vs_reference") or {}).get("fms_ratio")) is not None]),
        "avg_fms_ratio_candidates": average_ratio(candidates, "fms_ratio"),
        "avg_sold_ratio_candidates": average_ratio(candidates, "sold_ratio"),
        "avg_str_ratio_candidates": average_ratio(candidates, "str_ratio"),
        "failure_breakdown": build_breakdown(items, "reason_code"),
        "confidence_breakdown": build_confidence_breakdown(items),
        "source_failure_breakdown": build_source_failure_breakdown(items),
        "network_retry_events_total": retry_metrics["network_retry_events_total"],
        "network_retry_seeds": retry_metrics["network_retry_seeds"],
        "source_failure_counts": retry_metrics["source_failure_counts"],
        **decision_totals,
    }
    return kpi


def append_history(kpi: dict[str, Any]) -> dict[str, Any]:
    MONITOR_DIR.mkdir(parents=True, exist_ok=True)
    history = load_json(HISTORY_PATH, {"items": []})
    items = history.get("items") if isinstance(history, dict) else []
    if not isinstance(items, list):
        items = []
    items = [x for x in items if str(x.get("batch_id")) != str(kpi.get("batch_id"))]
    items.append(kpi)
    items = sorted(items, key=lambda x: str(x.get("generated_at") or x.get("batch_id") or ""))[-ROLLING_WINDOW:]
    payload = {
        "updated_at": now_iso(),
        "window": ROLLING_WINDOW,
        "count": len(items),
        "items": items,
    }
    write_json(HISTORY_PATH, payload)
    return payload


def build_alerts(kpi: dict[str, Any], history_payload: dict[str, Any]) -> dict[str, Any]:
    history_items = history_payload.get("items") or []
    previous = [x for x in history_items if str(x.get("batch_id")) != str(kpi.get("batch_id"))]

    yield_hist = [float(x["winner_yield"]) for x in previous if safe_float(x.get("winner_yield")) is not None]
    fms_hist = [float(x["avg_fms_ratio_winners"]) for x in previous if safe_float(x.get("avg_fms_ratio_winners")) is not None]

    yield_thresholds = dynamic_threshold(yield_hist, STATIC_WARN_YIELD, YIELD_WARN_STD_K, YIELD_CRIT_STD_K)
    fms_thresholds = dynamic_threshold(fms_hist, STATIC_WARN_FMS_RATIO, FMS_WARN_STD_K, FMS_CRIT_STD_K)

    winner_yield = float(kpi.get("winner_yield") or 0.0)
    avg_fms_ratio_winners = safe_float(kpi.get("avg_fms_ratio_winners"))
    avg_sold_ratio_winners = safe_float(kpi.get("avg_sold_ratio_winners"))
    avg_fms_ratio_candidates = safe_float(kpi.get("avg_fms_ratio_candidates"))
    avg_sold_ratio_candidates = safe_float(kpi.get("avg_sold_ratio_candidates"))

    yield_warn = yield_thresholds.get("dyn_warn") if yield_thresholds.get("dyn_warn") is not None else STATIC_WARN_YIELD
    yield_crit = yield_thresholds.get("dyn_crit") if yield_thresholds.get("dyn_crit") is not None else STATIC_CRIT_YIELD
    fms_warn = fms_thresholds.get("dyn_warn") if fms_thresholds.get("dyn_warn") is not None else STATIC_WARN_FMS_RATIO
    fms_crit = fms_thresholds.get("dyn_crit") if fms_thresholds.get("dyn_crit") is not None else STATIC_CRIT_FMS_RATIO

    alerts: list[dict[str, Any]] = []

    if avg_fms_ratio_winners is not None:
        if winner_yield < yield_crit and avg_fms_ratio_winners < fms_crit:
            alerts.append({
                "level": "critical",
                "code": "LOW_YIELD_LOW_REFERENCE",
                "message": f"winner_yield={winner_yield:.4f} (<{yield_crit:.4f}) and avg_fms_ratio_winners={avg_fms_ratio_winners:.4f} (<{fms_crit:.4f})",
            })
        elif winner_yield < yield_warn and avg_fms_ratio_winners >= fms_warn:
            alerts.append({
                "level": "warning",
                "code": "LOW_YIELD_GOOD_REFERENCE",
                "message": f"winner_yield={winner_yield:.4f} (<{yield_warn:.4f}), avg_fms_ratio_winners={avg_fms_ratio_winners:.4f} (>={fms_warn:.4f})",
            })
        elif winner_yield >= yield_warn and avg_fms_ratio_winners < fms_warn:
            level = "critical" if avg_fms_ratio_winners < fms_crit else "warning"
            alerts.append({
                "level": level,
                "code": "NORMAL_YIELD_LOW_REFERENCE",
                "message": f"winner_yield={winner_yield:.4f} (>={yield_warn:.4f}), avg_fms_ratio_winners={avg_fms_ratio_winners:.4f} (<{fms_warn:.4f})",
            })

    if avg_sold_ratio_candidates is not None and avg_sold_ratio_winners is not None:
        delta_sold_ratio = avg_sold_ratio_candidates - avg_sold_ratio_winners
        if delta_sold_ratio < -0.4:
            alerts.append({
                "level": "critical",
                "code": "CANDIDATES_SOLD_RATIO_WEAK",
                "message": f"delta_sold_ratio={delta_sold_ratio:.4f} (< -0.4)",
            })
        elif delta_sold_ratio < -0.2:
            alerts.append({
                "level": "warning",
                "code": "CANDIDATES_SOLD_RATIO_WEAK",
                "message": f"delta_sold_ratio={delta_sold_ratio:.4f} (< -0.2)",
            })

    payload = {
        "batch_id": kpi.get("batch_id"),
        "generated_at": now_iso(),
        "batch_status": kpi.get("batch_status"),
        "processed_seeds": kpi.get("processed_seeds"),
        "total_seeds": kpi.get("seeds_total"),
        "kpi": {
            "winner_yield": winner_yield,
            "winner_yield_raw": safe_float(kpi.get("winner_yield_raw")),
            "winner_yield_reliable": safe_float(kpi.get("winner_yield_reliable")),
            "reliable_seed_count": kpi.get("reliable_seed_count"),
            "network_retry_events_total": kpi.get("network_retry_events_total"),
            "network_retry_seeds": kpi.get("network_retry_seeds"),
            "data_reject_total": kpi.get("data_reject_total"),
            "data_uncertain_total": kpi.get("data_uncertain_total"),
            "market_reject_total": kpi.get("market_reject_total"),
            "market_candidate_total": kpi.get("market_candidate_total"),
            "market_accept_total": kpi.get("market_accept_total"),
            "avg_fms_ratio_winners": avg_fms_ratio_winners,
            "avg_sold_ratio_winners": avg_sold_ratio_winners,
            "avg_fms_ratio_candidates": avg_fms_ratio_candidates,
            "avg_sold_ratio_candidates": avg_sold_ratio_candidates,
        },
        "thresholds": {
            "winner_yield_dyn_warn": yield_warn,
            "winner_yield_dyn_crit": yield_crit,
            "avg_fms_ratio_winners_dyn_warn": fms_warn,
            "avg_fms_ratio_winners_dyn_crit": fms_crit,
            "yield_history_mean": yield_thresholds.get("mean_hist"),
            "yield_history_std": yield_thresholds.get("std_hist"),
            "fms_history_mean": fms_thresholds.get("mean_hist"),
            "fms_history_std": fms_thresholds.get("std_hist"),
        },
        "failure_breakdown": kpi.get("failure_breakdown") or {},
        "confidence_breakdown": kpi.get("confidence_breakdown") or {},
        "source_failure_breakdown": kpi.get("source_failure_breakdown") or {},
        "source_failure_counts": kpi.get("source_failure_counts") or {},
        "alerts": alerts,
    }
    return payload


def update_batch_monitoring(
    batch_id: str,
    *,
    total_seeds: int,
    processed_seeds: int,
    batch_status: str,
) -> dict[str, Any]:
    kpi = compute_batch_kpi(batch_id=batch_id, seeds_total=total_seeds)
    kpi["batch_status"] = str(batch_status)
    kpi["processed_seeds"] = int(processed_seeds)

    history = append_history(kpi)
    alerts = build_alerts(kpi, history)
    summary = {
        "generated_at": now_iso(),
        "batch_id": batch_id,
        "batch_status": str(batch_status),
        "processed_seeds": int(processed_seeds),
        "total_seeds": int(total_seeds),
        "kpi": kpi,
        "failure_breakdown": kpi.get("failure_breakdown") or {},
        "confidence_breakdown": kpi.get("confidence_breakdown") or {},
        "source_failure_breakdown": kpi.get("source_failure_breakdown") or {},
        "source_failure_counts": kpi.get("source_failure_counts") or {},
        "history_path": str(HISTORY_PATH.resolve()),
        "alerts_path": str(ALERTS_PATH.resolve()),
    }
    write_json(ALERTS_PATH, alerts)
    write_json(SUMMARY_PATH, summary)
    return {
        "kpi": kpi,
        "alerts": alerts,
        "history": history,
        "summary": summary,
    }


if __name__ == "__main__":
    payload = load_json(BASE_DIR / "niche_engine" / "accepted" / "seed_statuses.json", {})
    batch_id = str(payload.get("batch_id") or "manual")
    batch_status = str(payload.get("batch_status") or payload.get("batch_stats", {}).get("batch_status") or "unknown")
    processed_seeds = int(payload.get("processed_seeds") or payload.get("seed_count") or 0)
    total_seeds = int(payload.get("total_seeds") or payload.get("batch_stats", {}).get("total_seeds_planned") or payload.get("batch_stats", {}).get("total_seeds") or processed_seeds)

    result = update_batch_monitoring(
        batch_id=batch_id,
        total_seeds=total_seeds,
        processed_seeds=processed_seeds,
        batch_status=batch_status,
    )
    print(json.dumps({"batch_id": batch_id, "batch_status": batch_status, "alerts": len(result["alerts"].get("alerts", []))}, ensure_ascii=False))
