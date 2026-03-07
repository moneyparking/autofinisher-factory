from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .base import AdapterResult, RequestContext
from .shared import request_and_finalize


DEFAULT_BRIGHTDATA_ENDPOINT = "brd.superproxy.io:33335"
DEFAULT_BRIGHTDATA_CA_CERT_ENV = "BRIGHT_DATA_CA_CERT_PATH"
DEFAULT_BRIGHTDATA_INSECURE_ENV = "BRIGHT_DATA_INSECURE_SKIP_VERIFY"



def _normalize_proxy_endpoint(endpoint: str) -> str:
    normalized = (endpoint or "").strip()
    if normalized.startswith("http://"):
        normalized = normalized[len("http://") :]
    elif normalized.startswith("https://"):
        normalized = normalized[len("https://") :]
    return normalized or DEFAULT_BRIGHTDATA_ENDPOINT



def _resolve_tls_verify_setting() -> bool | str:
    cert_path = os.getenv(DEFAULT_BRIGHTDATA_CA_CERT_ENV, "").strip()
    if cert_path:
        path = Path(cert_path).expanduser()
        if path.exists() and path.is_file():
            return str(path)

    insecure_flag = os.getenv(DEFAULT_BRIGHTDATA_INSECURE_ENV, "").strip().lower()
    if insecure_flag in {"1", "true", "yes", "on"}:
        return False

    return False



def fetch_with_brightdata(ctx: RequestContext) -> AdapterResult:
    proxy_endpoint = _normalize_proxy_endpoint(ctx.endpoint)
    proxy_auth = f"http://{ctx.api_key}@{proxy_endpoint}"
    proxies = {
        "http": proxy_auth,
        "https": proxy_auth,
    }
    verify_setting: bool | str = _resolve_tls_verify_setting()
    return request_and_finalize(
        method="GET",
        url=ctx.url,
        headers=ctx.headers,
        timeout=ctx.timeout_s,
        proxies=proxies,
        verify=verify_setting,
    )
