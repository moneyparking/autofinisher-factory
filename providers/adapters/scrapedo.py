from __future__ import annotations

import time
from typing import Any

import requests

from .base import AdapterResult, RequestContext


def fetch_with_scrapedo(ctx: RequestContext) -> AdapterResult:
    params: dict[str, Any] = {
        "token": ctx.api_key,
        "url": ctx.url,
    }
    params.update(ctx.default_params)
    if ctx.extra_params:
        for key, value in ctx.extra_params.items():
            if value is None:
                continue
            params[str(key)] = value

    started = time.monotonic()
    response = requests.get(
        ctx.endpoint,
        params=params,
        headers=ctx.headers,
        timeout=ctx.timeout_s,
    )
    latency_ms = (time.monotonic() - started) * 1000.0

    return AdapterResult(
        text=str(response.text),
        http_status=int(response.status_code),
        latency_ms=round(latency_ms, 2),
        final_status="ok" if response.status_code < 400 else "failed",
        failure_stage=None if response.status_code < 400 else "request",
    )
