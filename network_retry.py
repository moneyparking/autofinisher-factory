from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable


@dataclass(frozen=True)
class RetryMeta:
    retry_count: int
    first_attempt_success: bool
    latency_ms: float
    final_status: str  # ok|partial|failed
    failure_stage: str | None  # request|parse|normalize
    warnings: list[str]
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "retry_count": int(self.retry_count),
            "first_attempt_success": bool(self.first_attempt_success),
            "latency_ms": round(float(self.latency_ms), 2),
            "final_status": str(self.final_status),
            "failure_stage": self.failure_stage,
            "warnings": list(self.warnings or []),
            "error": self.error,
        }


def _normalize_backoffs(backoffs: Iterable[float] | None, max_retries: int, base_delay: float) -> list[float]:
    if backoffs is None:
        # simple linear backoff by default, bounded
        return [max(0.0, float(base_delay) * (i + 1)) for i in range(max_retries)]
    out: list[float] = []
    for value in backoffs:
        try:
            out.append(max(0.0, float(value)))
        except Exception:
            continue
    if len(out) < max_retries:
        out.extend([max(0.0, float(base_delay) * (i + 1)) for i in range(len(out), max_retries)])
    return out[:max_retries]


def fetch_with_retry(
    request_fn: Callable[[], Any],
    *,
    max_retries: int = 2,
    base_delay: float = 1.0,
    backoffs: Iterable[float] | None = None,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
    stage: str = "request",
    warnings_prefix: str | None = None,
    max_elapsed_s: float | None = None,
) -> tuple[Any | None, dict[str, Any]]:
    """Execute request_fn with limited retries and return (result, meta).

    - Never raises; caller decides how to handle result=None.
    - retry_count counts *retries*, not attempts (i.e. 0 means first attempt success).
    - If max_elapsed_s is set, the function fails fast once wall-clock elapsed exceeds that limit.
      Note: cannot pre-empt a single blocking request_fn call; pair with per-request timeouts.
    """
    started = time.monotonic()
    backoff_schedule = _normalize_backoffs(backoffs, max_retries=max_retries, base_delay=base_delay)

    warnings: list[str] = []
    last_exc: BaseException | None = None
    attempts = 0

    def _elapsed_exceeded() -> bool:
        if max_elapsed_s is None:
            return False
        try:
            return (time.monotonic() - started) > float(max_elapsed_s)
        except Exception:
            return False

    for attempt in range(max_retries + 1):
        if _elapsed_exceeded():
            last_exc = TimeoutError("elapsed_timeout")
            warnings.append("elapsed_timeout")
            break

        attempts += 1
        try:
            result = request_fn()
            latency_ms = (time.monotonic() - started) * 1000.0
            retry_count = max(0, attempts - 1)
            if retry_count > 0:
                warnings.append("retry_success")
            if warnings_prefix:
                warnings = [f"{warnings_prefix}:{w}" for w in warnings]
            meta = RetryMeta(
                retry_count=retry_count,
                first_attempt_success=(retry_count == 0),
                latency_ms=latency_ms,
                final_status="ok",
                failure_stage=None,
                warnings=warnings,
                error=None,
            ).as_dict()
            return result, meta
        except retry_on as exc:  # noqa: BLE001
            last_exc = exc
            if _elapsed_exceeded():
                warnings.append("elapsed_timeout")
                break
            if attempt < max_retries:
                delay = backoff_schedule[min(attempt, len(backoff_schedule) - 1)] if backoff_schedule else 0.0
                if delay > 0:
                    time.sleep(delay)
                continue

    latency_ms = (time.monotonic() - started) * 1000.0
    retry_count = max(0, attempts - 1)
    if "elapsed_timeout" not in warnings:
        warnings.append("retry_exhausted")

    error = "elapsed_timeout" if "elapsed_timeout" in warnings else (str(last_exc) if last_exc is not None else "unknown_error")
    if warnings_prefix:
        warnings = [f"{warnings_prefix}:{w}" for w in warnings]

    meta = RetryMeta(
        retry_count=retry_count,
        first_attempt_success=False,
        latency_ms=latency_ms,
        final_status="failed",
        failure_stage=stage,
        warnings=warnings,
        error=error,
    ).as_dict()
    return None, meta
