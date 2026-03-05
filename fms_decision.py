from __future__ import annotations

from typing import Any

CRITICAL_SOURCES = {"ebay", "etsy"}
HIGH_CONFIDENCE = "high"
MEDIUM_CONFIDENCE = "medium"
LOW_CONFIDENCE = "low"
FAILED_CONFIDENCE = "failed"
FULL_COMPLETENESS = "full"
PARTIAL_COMPLETENESS = "partial"
EMPTY_COMPLETENESS = "empty"


def _normalized_warning_list(warnings: Any) -> list[str]:
    if not isinstance(warnings, list):
        return []
    out: list[str] = []
    seen = set()
    for warning in warnings:
        value = str(warning or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def source_quality_template(
    *,
    confidence: str = HIGH_CONFIDENCE,
    completeness: str = FULL_COMPLETENESS,
    warnings: list[str] | None = None,
    retry_count: int = 0,
    latency_ms: float | int | None = None,
    source_status: str = "ok",
    first_attempt_success: bool = True,
    final_status: str = "ok",
    failure_stage: str | None = None,
) -> dict[str, Any]:
    return {
        "confidence": confidence,
        "completeness": completeness,
        "warnings": _normalized_warning_list(warnings or []),
        "retry_count": max(0, int(retry_count or 0)),
        "latency_ms": round(float(latency_ms), 2) if latency_ms is not None else None,
        "source_status": str(source_status or "ok"),
        "first_attempt_success": bool(first_attempt_success),
        "final_status": str(final_status or "ok"),
        "failure_stage": failure_stage,
    }


def infer_source_quality(
    *,
    source_name: str,
    source_status: str,
    warnings: list[str] | None = None,
    retry_count: int = 0,
    latency_ms: float | int | None = None,
    completeness: str | None = None,
    failure_stage: str | None = None,
) -> dict[str, Any]:
    normalized_status = str(source_status or "ok").strip().lower() or "ok"
    warning_list = _normalized_warning_list(warnings or [])
    retry_count = max(0, int(retry_count or 0))
    if completeness is None:
        if normalized_status == "failed":
            completeness = EMPTY_COMPLETENESS
        elif normalized_status == "partial":
            completeness = PARTIAL_COMPLETENESS
        else:
            completeness = FULL_COMPLETENESS

    confidence = HIGH_CONFIDENCE
    if normalized_status == "failed":
        confidence = FAILED_CONFIDENCE
    elif completeness == PARTIAL_COMPLETENESS:
        confidence = LOW_CONFIDENCE
    elif completeness == EMPTY_COMPLETENESS:
        confidence = LOW_CONFIDENCE

    if retry_count > 0 and confidence == HIGH_CONFIDENCE:
        confidence = MEDIUM_CONFIDENCE
        if "retry_success" not in warning_list and normalized_status != "failed":
            warning_list.append("retry_success")

    if normalized_status == "partial" and confidence == HIGH_CONFIDENCE:
        confidence = MEDIUM_CONFIDENCE
    if failure_stage == "parse" and normalized_status != "failed":
        confidence = LOW_CONFIDENCE if completeness != FULL_COMPLETENESS else MEDIUM_CONFIDENCE
    if normalized_status == "failed" and failure_stage is None:
        failure_stage = "request"

    first_attempt_success = retry_count == 0 and normalized_status != "failed"
    return source_quality_template(
        confidence=confidence,
        completeness=completeness,
        warnings=warning_list,
        retry_count=retry_count,
        latency_ms=latency_ms,
        source_status=normalized_status,
        first_attempt_success=first_attempt_success,
        final_status=normalized_status,
        failure_stage=failure_stage,
    )


def aggregate_data_quality(source_quality: dict[str, Any] | None) -> dict[str, Any]:
    source_quality = source_quality or {}
    warnings: list[str] = []
    critical_sources_failed: list[str] = []
    degraded_sources: list[str] = []
    confidence_values_all: list[str] = []
    completeness_values_all: list[str] = []
    critical_confidence_values: list[str] = []
    critical_completeness_values: list[str] = []

    for source_name, payload in source_quality.items():
        if not isinstance(payload, dict):
            continue
        confidence = str(payload.get("confidence") or HIGH_CONFIDENCE)
        completeness = str(payload.get("completeness") or FULL_COMPLETENESS)
        confidence_values_all.append(confidence)
        completeness_values_all.append(completeness)
        if source_name in CRITICAL_SOURCES:
            critical_confidence_values.append(confidence)
            critical_completeness_values.append(completeness)
        for warning in _normalized_warning_list(payload.get("warnings") or []):
            if warning not in warnings:
                warnings.append(warning)
        if source_name in CRITICAL_SOURCES and confidence == FAILED_CONFIDENCE:
            critical_sources_failed.append(source_name)
        elif confidence in {MEDIUM_CONFIDENCE, LOW_CONFIDENCE} or completeness != FULL_COMPLETENESS:
            degraded_sources.append(source_name)

    # Canonical decision confidence is based on critical market sources only.
    # Non-critical sources (e.g. google) remain visible via warnings/degraded_sources,
    # but do not block market verdicts when eBay + Etsy are reliable.
    overall_confidence = HIGH_CONFIDENCE
    if critical_sources_failed:
        overall_confidence = FAILED_CONFIDENCE
    elif LOW_CONFIDENCE in critical_confidence_values:
        overall_confidence = LOW_CONFIDENCE
    elif MEDIUM_CONFIDENCE in critical_confidence_values:
        overall_confidence = MEDIUM_CONFIDENCE
    elif FAILED_CONFIDENCE in critical_confidence_values:
        overall_confidence = LOW_CONFIDENCE

    overall_confidence_all_sources = HIGH_CONFIDENCE
    if FAILED_CONFIDENCE in confidence_values_all:
        overall_confidence_all_sources = FAILED_CONFIDENCE if critical_sources_failed else LOW_CONFIDENCE
    elif LOW_CONFIDENCE in confidence_values_all:
        overall_confidence_all_sources = LOW_CONFIDENCE
    elif MEDIUM_CONFIDENCE in confidence_values_all:
        overall_confidence_all_sources = MEDIUM_CONFIDENCE

    overall_completeness = FULL_COMPLETENESS
    if EMPTY_COMPLETENESS in critical_completeness_values:
        overall_completeness = EMPTY_COMPLETENESS
    elif PARTIAL_COMPLETENESS in critical_completeness_values:
        overall_completeness = PARTIAL_COMPLETENESS

    overall_completeness_all_sources = FULL_COMPLETENESS
    if EMPTY_COMPLETENESS in completeness_values_all:
        overall_completeness_all_sources = EMPTY_COMPLETENESS
    elif PARTIAL_COMPLETENESS in completeness_values_all:
        overall_completeness_all_sources = PARTIAL_COMPLETENESS

    return {
        "overall_confidence": overall_confidence,
        "overall_confidence_all_sources": overall_confidence_all_sources,
        "overall_completeness": overall_completeness,
        "overall_completeness_all_sources": overall_completeness_all_sources,
        "warnings": warnings,
        "critical_sources_failed": critical_sources_failed,
        "degraded_sources": degraded_sources,
    }


def _market_reason_code(
    *,
    score: float,
    active: int,
    sold: int,
    str_value: float,
    digital_share: float | None,
    total_results: Any,
    min_monetization_score: float,
    min_str_for_accept: float,
    min_sold_for_accept: int,
    min_active: int,
    max_active: int,
) -> tuple[str, str, str]:
    if digital_share is not None and float(digital_share) < 0.4:
        return "rejected", "market_reject", "market_reject_weak_etsy"
    if total_results is not None:
        try:
            total_results_int = int(total_results)
            if total_results_int < 50:
                return "rejected", "market_reject", "market_reject_weak_etsy"
            if total_results_int > 5000:
                return "rejected", "market_reject", "market_reject_weak_etsy"
        except Exception:
            pass
    if active < min_active:
        return "rejected", "market_reject", "market_reject_low_active"
    if active > max_active:
        return "rejected", "market_reject", "market_reject_high_active"
    if sold < min_sold_for_accept:
        return "rejected", "market_reject", "market_reject_low_sold"
    if str_value < min_str_for_accept:
        return "rejected", "market_reject", "market_reject_low_str"
    if score < min_monetization_score:
        return "rejected", "market_reject", "market_reject_low_fms"
    return "winner", "market_accept", "market_accept_winner_gate"


def decide_for_item(
    item: dict[str, Any],
    *,
    min_monetization_score: float,
    min_str_for_accept: float,
    min_sold_for_accept: int,
    min_active: int,
    max_active: int,
) -> dict[str, Any]:
    ranking = item.get("ranking") or {}
    metrics = item.get("metrics") or {}
    intel = item.get("intel") or {}
    etsy_search = intel.get("etsy_search") or {}
    aggregates = etsy_search.get("aggregates") or {}
    search_metadata = etsy_search.get("search_metadata") or {}

    score = float(item.get("fms_score") or ranking.get("monetization_score") or 0.0)
    active = int(metrics.get("active_listings") or 0)
    sold = int(metrics.get("sold_listings") or 0)
    str_value = float(metrics.get("sell_through_rate") or 0.0)
    digital_share_raw = aggregates.get("digital_share", search_metadata.get("digital_share"))
    digital_share = float(digital_share_raw) if digital_share_raw is not None else None
    total_results = search_metadata.get("total_results")

    source_quality = item.get("source_quality") or {}
    data_quality = item.get("data_quality") or aggregate_data_quality(source_quality)
    critical_sources_failed = set(data_quality.get("critical_sources_failed") or [])
    overall_confidence = str(data_quality.get("overall_confidence") or HIGH_CONFIDENCE)

    if "ebay" in critical_sources_failed:
        return {
            "status": "uncertain",
            "decision_type": "data_reject",
            "reason_code": "data_reject_ebay_failed",
            "reason_detail": "critical_source_failed",
            "fms_score": None,
            "source_quality": source_quality,
            "data_quality": data_quality,
        }
    if "etsy" in critical_sources_failed:
        return {
            "status": "uncertain",
            "decision_type": "data_reject",
            "reason_code": "data_reject_etsy_failed",
            "reason_detail": "critical_source_failed",
            "fms_score": None,
            "source_quality": source_quality,
            "data_quality": data_quality,
        }

    if overall_confidence in {MEDIUM_CONFIDENCE, LOW_CONFIDENCE}:
        degraded_sources = data_quality.get("degraded_sources") or []
        detail = f"overall_confidence={overall_confidence};degraded_sources={','.join(sorted(str(x) for x in degraded_sources))}"
        return {
            "status": "candidate",
            "decision_type": "data_uncertain",
            "reason_code": "data_uncertain_multi_source_partial",
            "reason_detail": detail,
            "fms_score": score,
            "source_quality": source_quality,
            "data_quality": data_quality,
        }

    status, decision_type, reason_code = _market_reason_code(
        score=score,
        active=active,
        sold=sold,
        str_value=str_value,
        digital_share=digital_share,
        total_results=total_results,
        min_monetization_score=min_monetization_score,
        min_str_for_accept=min_str_for_accept,
        min_sold_for_accept=min_sold_for_accept,
        min_active=min_active,
        max_active=max_active,
    )
    reason_detail = f"score={score};str={str_value};sold={sold};active={active}"
    if status == "rejected" and score >= min_monetization_score:
        decision_type = "market_candidate"
        reason_code = reason_code.replace("market_reject_", "market_candidate_")
        status = "candidate"
    return {
        "status": status,
        "decision_type": decision_type,
        "reason_code": reason_code,
        "reason_detail": reason_detail,
        "fms_score": score,
        "source_quality": source_quality,
        "data_quality": data_quality,
    }
