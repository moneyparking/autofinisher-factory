from __future__ import annotations

from .base import AdapterResult, RequestContext
from .shared import request_and_finalize


DEFAULT_OXYLABS_ENDPOINT = "realtime.oxylabs.io:60000"


def _normalize_proxy_endpoint(endpoint: str) -> str:
    normalized = (endpoint or "").strip()
    if normalized.startswith("http://"):
        normalized = normalized[len("http://") :]
    elif normalized.startswith("https://"):
        normalized = normalized[len("https://") :]
    return normalized or DEFAULT_OXYLABS_ENDPOINT


def fetch_with_oxylabs(ctx: RequestContext) -> AdapterResult:
    proxy_endpoint = _normalize_proxy_endpoint(ctx.endpoint)
    proxies = {
        "http": f"http://{ctx.api_key}@{proxy_endpoint}",
        "https": f"http://{ctx.api_key}@{proxy_endpoint}",
    }
    headers = dict(ctx.headers or {})
    if str((ctx.extra_params or {}).get("render", "")).lower() in {"1", "true", "html"}:
        headers["X-Oxylabs-Render"] = "html"
    return request_and_finalize(
        method="GET",
        url=ctx.url,
        headers=headers or None,
        timeout=ctx.timeout_s,
        proxies=proxies,
        verify=False,
    )
