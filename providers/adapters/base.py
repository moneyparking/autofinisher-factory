from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RequestContext:
    """Fully resolved request contract for exactly one provider adapter.

    Contract rules:
    - provider_name/provider_type/endpoint/api_key identify the concrete provider.
    - default_params already contains provider-level + tier-level defaults.
    - extra_params contains only per-call overrides.
    - adapters must only use fields from this dataclass and must not inspect registry config.
    """

    provider_name: str
    provider_type: str
    endpoint: str
    api_key: str
    default_params: dict[str, Any]
    headers: dict[str, str] | None
    timeout_s: int
    url: str
    extra_params: dict[str, Any] | None


@dataclass(frozen=True)
class AdapterResult:
    """Normalized adapter result returned back to the registry layer."""

    text: str
    http_status: int
    latency_ms: float
    final_status: str
    failure_stage: str | None



def validate_request_context(ctx: RequestContext) -> None:
    if not ctx.provider_name.strip():
        raise ValueError("RequestContext.provider_name must be non-empty")
    if not ctx.provider_type.strip():
        raise ValueError("RequestContext.provider_type must be non-empty")
    if not ctx.endpoint.strip():
        raise ValueError("RequestContext.endpoint must be non-empty")
    if not ctx.api_key.strip():
        raise ValueError("RequestContext.api_key must be non-empty")
    if not ctx.url.strip():
        raise ValueError("RequestContext.url must be non-empty")
    if ctx.timeout_s <= 0:
        raise ValueError("RequestContext.timeout_s must be positive")
    if not isinstance(ctx.default_params, dict):
        raise ValueError("RequestContext.default_params must be a mapping")
    if ctx.extra_params is not None and not isinstance(ctx.extra_params, dict):
        raise ValueError("RequestContext.extra_params must be a mapping or None")
    if ctx.headers is not None and not isinstance(ctx.headers, dict):
        raise ValueError("RequestContext.headers must be a mapping or None")



def validate_adapter_result(result: AdapterResult) -> None:
    if not isinstance(result.text, str):
        raise ValueError("AdapterResult.text must be a string")
    if result.http_status < 100:
        raise ValueError("AdapterResult.http_status must be a valid HTTP status code")
    if result.latency_ms < 0:
        raise ValueError("AdapterResult.latency_ms must be non-negative")
    if not result.final_status.strip():
        raise ValueError("AdapterResult.final_status must be non-empty")
