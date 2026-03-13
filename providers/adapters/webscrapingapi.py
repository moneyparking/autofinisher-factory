from __future__ import annotations

from typing import Any

from .base import AdapterResult, RequestContext
from .shared import merge_params, request_and_finalize


def fetch_with_webscrapingapi(ctx: RequestContext) -> AdapterResult:
    params: dict[str, Any] = {"api_key": ctx.api_key, "url": ctx.url}
    params = merge_params(params, ctx.default_params, ctx.extra_params)
    return request_and_finalize(
        method="GET",
        url=ctx.endpoint,
        params=params,
        headers=ctx.headers,
        timeout=ctx.timeout_s,
    )
