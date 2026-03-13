from __future__ import annotations

from .base import AdapterResult, RequestContext
from .shared import request_and_finalize


DEFAULT_APIFY_PROXY_ENDPOINT = "proxy.apify.com:8000"



def _normalize_proxy_endpoint(endpoint: str) -> str:
    normalized = (endpoint or "").strip()
    if normalized.startswith("http://"):
        normalized = normalized[len("http://") :]
    elif normalized.startswith("https://"):
        normalized = normalized[len("https://") :]
    return normalized or DEFAULT_APIFY_PROXY_ENDPOINT



def fetch_with_apify_proxy(ctx: RequestContext) -> AdapterResult:
    merged_params = dict(ctx.default_params or {})
    merged_params.update(ctx.extra_params or {})
    proxy_username = str(merged_params.get("proxy_username") or "auto").strip() or "auto"
    proxy_endpoint = _normalize_proxy_endpoint(ctx.endpoint)
    proxy_auth = f"http://{proxy_username}:{ctx.api_key}@{proxy_endpoint}"
    proxies = {
        "http": proxy_auth,
        "https": proxy_auth,
    }
    return request_and_finalize(
        method="GET",
        url=ctx.url,
        headers=ctx.headers,
        timeout=ctx.timeout_s,
        proxies=proxies,
        verify=False,
    )
