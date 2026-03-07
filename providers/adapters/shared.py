from __future__ import annotations

import time
from typing import Any

import requests

from .base import AdapterResult


def merge_params(
    base: dict[str, Any],
    default_params: dict[str, Any] | None,
    extra_params: dict[str, Any] | None,
) -> dict[str, Any]:
    params = dict(base)
    for source in (default_params or {}, extra_params or {}):
        for key, value in source.items():
            if value is None:
                continue
            params[str(key)] = value
    return params


def request_and_finalize(**kwargs: Any) -> AdapterResult:
    started = time.monotonic()
    response = requests.request(**kwargs)
    latency_ms = (time.monotonic() - started) * 1000.0
    return AdapterResult(
        text=str(response.text),
        http_status=int(response.status_code),
        latency_ms=round(latency_ms, 2),
        final_status="ok" if response.status_code < 400 else "failed",
        failure_stage=None if response.status_code < 400 else "request",
    )


def finalize_response(response: requests.Response) -> AdapterResult:
    raise RuntimeError("finalize_response is deprecated; use request_and_finalize().")
