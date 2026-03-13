from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from providers.adapters import (
    fetch_with_apify_proxy,
    fetch_with_brightdata,
    fetch_with_oxylabs,
    fetch_with_scrapedo,
    fetch_with_scraperapi,
    fetch_with_scrapingbee,
    fetch_with_webscrapingapi,
    fetch_with_zenrows,
)
from providers.adapters.base import (
    AdapterResult,
    RequestContext,
    validate_adapter_result,
    validate_request_context,
)

# Load env files early so provider tokens are available for all entrypoints.
# This repo uses .env.scrape.local as the source-of-truth for scraping provider keys.
try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None  # type: ignore


def _load_env_files() -> None:
    if load_dotenv is None:
        return
    root = Path(__file__).resolve().parents[1]
    for name in (".env", ".env.openai.local", ".env.scrape.local"):
        path = root / name
        if path.exists():
            # Do not override already-exported env vars.
            load_dotenv(str(path), override=False)


_load_env_files()


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    type: str
    adapter: str
    transport: str
    enabled: bool
    api_key_env: str
    endpoint: str
    default_params: dict[str, Any]


@dataclass(frozen=True)
class ChannelTierSpec:
    channel: str
    tier: str
    providers: list[ProviderSpec]
    tier_default_params: dict[str, Any]
    provider_param_overrides: dict[str, dict[str, Any]]


@dataclass(frozen=True)
class FetchPlanStep:
    channel: str
    tier: str
    mode: str
    provider_name: str
    provider_type: str
    provider_adapter: str
    provider_transport: str
    enabled: bool
    endpoint: str
    api_key_env: str
    api_key_present: bool
    effective_default_params: dict[str, Any]


@dataclass(frozen=True)
class FetchExecutionPlan:
    channel: str
    mode: str
    tiers_tried: list[str]
    steps: list[FetchPlanStep]


class ProviderConfigError(RuntimeError):
    pass


ADAPTER_FETCHERS: dict[str, Any] = {
    "scrapedo": fetch_with_scrapedo,
    "scraperapi": fetch_with_scraperapi,
    "webscrapingapi": fetch_with_webscrapingapi,
    "scrapingbee": fetch_with_scrapingbee,
    "zenrows": fetch_with_zenrows,
    "apify_proxy": fetch_with_apify_proxy,
    "brightdata": fetch_with_brightdata,
    "oxylabs": fetch_with_oxylabs,
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_registry_config(path: str | Path | None = None) -> dict[str, Any]:
    cfg_path = Path(path) if path else (_repo_root() / "providers.yaml")
    if not cfg_path.exists():
        raise ProviderConfigError(f"providers.yaml not found at: {cfg_path}")
    try:
        payload = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ProviderConfigError(f"failed to parse providers.yaml: {exc}") from exc
    if not isinstance(payload, dict):
        raise ProviderConfigError("providers.yaml must be a YAML mapping")
    return payload


def _require_env(var_name: str) -> str:
    value = os.getenv(var_name, "").strip()
    if not value:
        raise ProviderConfigError(
            f"Missing required env var '{var_name}'. "
            "Ensure .env.scrape.local is present and loaded, or export the variable in your shell."
        )
    return value


def _build_provider(name: str, p: dict[str, Any]) -> ProviderSpec:
    p_type = str(p.get("type") or "").strip().lower()
    adapter = str(p.get("adapter") or p_type).strip().lower()
    transport = str(p.get("transport") or "rest_api").strip().lower()
    enabled = bool(p.get("enabled", True))
    api_key_env = str(p.get("api_key_env") or "").strip()
    if not p_type or not adapter or not api_key_env:
        raise ProviderConfigError(f"provider '{name}' must define 'type', 'adapter', and 'api_key_env'")
    if adapter not in ADAPTER_FETCHERS:
        raise ProviderConfigError(f"provider '{name}' references unknown adapter '{adapter}'")

    endpoint_env = str(p.get("endpoint_env") or "").strip()
    endpoint_default = str(p.get("endpoint_default") or "").strip()
    endpoint = ""
    if endpoint_env:
        endpoint = os.getenv(endpoint_env, "").strip()
    if not endpoint:
        endpoint = endpoint_default
    if not endpoint:
        raise ProviderConfigError(f"provider '{name}' has no endpoint (set {endpoint_env} or endpoint_default)")

    default_params = p.get("default_params") or {}
    if not isinstance(default_params, dict):
        raise ProviderConfigError(f"provider '{name}' default_params must be a mapping")

    return ProviderSpec(
        name=name,
        type=p_type,
        adapter=adapter,
        transport=transport,
        enabled=enabled,
        api_key_env=api_key_env,
        endpoint=endpoint,
        default_params={str(k): v for k, v in default_params.items()},
    )


def _resolve_provider_names(tier_cfg: dict[str, Any], *, channel: str, tier: str) -> list[str]:
    provider_name = str(tier_cfg.get("provider") or "").strip()
    providers_list = tier_cfg.get("providers")

    names: list[str] = []
    if provider_name:
        names.append(provider_name)
    if isinstance(providers_list, list):
        names.extend(str(item).strip() for item in providers_list if str(item).strip())

    deduped: list[str] = []
    seen: set[str] = set()
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        deduped.append(name)

    if not deduped:
        raise ProviderConfigError(f"channel '{channel}' tier '{tier}' must specify provider or providers")
    return deduped


def _get_channel_cfg(cfg: dict[str, Any], *, channel: str) -> dict[str, Any]:
    providers_cfg = cfg.get("providers") or {}
    channels_cfg = cfg.get("channels") or {}
    if not isinstance(providers_cfg, dict) or not isinstance(channels_cfg, dict):
        raise ProviderConfigError("providers.yaml must contain 'providers' and 'channels' mappings")

    ch = channels_cfg.get(channel)
    if not isinstance(ch, dict):
        raise ProviderConfigError(f"channel '{channel}' not found in providers.yaml")
    return ch



def _resolve_channel_tier_from_cfg(
    cfg: dict[str, Any],
    *,
    channel: str,
    tier: str,
) -> ChannelTierSpec:
    providers_cfg = cfg.get("providers") or {}
    if not isinstance(providers_cfg, dict):
        raise ProviderConfigError("providers.yaml must contain a 'providers' mapping")

    ch = _get_channel_cfg(cfg, channel=channel)
    tiers = ch.get("tiers")
    if not isinstance(tiers, dict):
        raise ProviderConfigError(f"channel '{channel}' must define tiers")

    tier_cfg = tiers.get(tier)
    if not isinstance(tier_cfg, dict):
        raise ProviderConfigError(f"channel '{channel}' tier '{tier}' not found")

    provider_names = _resolve_provider_names(tier_cfg, channel=channel, tier=tier)

    providers: list[ProviderSpec] = []
    for provider_name in provider_names:
        p_cfg = providers_cfg.get(provider_name)
        if not isinstance(p_cfg, dict):
            raise ProviderConfigError(f"provider '{provider_name}' not found in providers.yaml")
        providers.append(_build_provider(provider_name, p_cfg))

    tier_params = tier_cfg.get("default_params") or {}
    if not isinstance(tier_params, dict):
        raise ProviderConfigError(f"channel '{channel}' tier '{tier}' default_params must be a mapping")

    provider_param_overrides_cfg = tier_cfg.get("provider_param_overrides") or {}
    if not isinstance(provider_param_overrides_cfg, dict):
        raise ProviderConfigError(f"channel '{channel}' tier '{tier}' provider_param_overrides must be a mapping")

    resolved_tier_params = {str(k): v for k, v in tier_params.items()}
    resolved_provider_param_overrides: dict[str, dict[str, Any]] = {}
    for provider_name, override_payload in provider_param_overrides_cfg.items():
        if not isinstance(override_payload, dict):
            raise ProviderConfigError(
                f"channel '{channel}' tier '{tier}' provider override for '{provider_name}' must be a mapping"
            )
        resolved_provider_param_overrides[str(provider_name)] = {
            str(k): v for k, v in override_payload.items()
        }

    return ChannelTierSpec(
        channel=channel,
        tier=tier,
        providers=providers,
        tier_default_params=resolved_tier_params,
        provider_param_overrides=resolved_provider_param_overrides,
    )



def _resolve_tiers_for_fetch(
    cfg: dict[str, Any],
    *,
    channel: str,
    tier: str | None,
    mode: str | None,
) -> list[str]:
    if tier:
        return [tier]

    channel_cfg = _get_channel_cfg(cfg, channel=channel)
    waterfall = channel_cfg.get("waterfall") or {}
    if isinstance(waterfall, dict):
        mode_key = str(mode or os.getenv("SCRAPE_MODE") or "cheap").strip().lower()
        tier_names = waterfall.get(mode_key)
        if isinstance(tier_names, list):
            resolved = [str(item).strip() for item in tier_names if str(item).strip()]
            if resolved:
                return resolved

    fallback_mode = str(mode or os.getenv("SCRAPE_MODE") or "cheap").strip().lower()
    if fallback_mode == "balanced":
        return ["tier_1", "tier_2"]
    if fallback_mode == "expensive":
        return ["tier_1", "tier_2", "tier_3"]
    return ["tier_1"]



def _should_failover_http_status(http_status: int) -> bool:
    if http_status in {401, 403, 408, 409, 423, 425, 429}:
        return True
    if http_status >= 500:
        return True
    return False



def _failure_decision_for_http(http_status: int) -> str:
    return "retryable" if _should_failover_http_status(http_status) else "terminal"



def _detect_response_outcome(*, provider_name: str, http_status: int, text: str) -> str:
    body = (text or "").lower()
    if http_status < 400:
        return "success"
    if http_status == 400:
        if 'unknown field' in body or 'missing required' in body or 'invalid api key' in body:
            return "provider_request_invalid"
        return "bad_request"
    if http_status == 401:
        return "provider_auth_failed"
    if http_status == 403:
        if provider_name in body or 'api key' in body or 'forbidden' in body:
            return "provider_auth_or_policy_block"
        return "target_or_provider_403"
    if http_status == 404:
        if '<html' in body and ('etsy' in body or 'page not found' in body or 'sorry' in body):
            return "target_404"
        if body.strip().startswith('{') or '"errors"' in body or 'not found' in body:
            return "provider_or_target_404"
        return "ambiguous_404"
    if http_status == 408:
        return "request_timeout"
    if http_status == 409:
        return "conflict"
    if http_status == 423:
        return "resource_locked"
    if http_status == 425:
        return "too_early"
    if http_status == 429:
        return "provider_rate_limited"
    if http_status >= 500:
        return "provider_server_error"
    return "http_error"



def _decision_for_http_result(*, provider_name: str, http_status: int, text: str) -> tuple[str, str]:
    outcome = _detect_response_outcome(provider_name=provider_name, http_status=http_status, text=text)
    if http_status < 400:
        return ("success", outcome)
    if http_status == 404 and outcome == "ambiguous_404":
        return ("retryable", outcome)
    return (_failure_decision_for_http(http_status), outcome)



def _failure_decision_for_exception(exc: Exception) -> str:
    name = exc.__class__.__name__.lower()
    retryable_tokens = (
        "timeout",
        "connection",
        "proxy",
        "ssl",
        "chunkedencoding",
        "retry",
    )
    if any(token in name for token in retryable_tokens):
        return "retryable"
    return "terminal"



def _build_attempt_row(*, provider: ProviderSpec, tier: str, mode: str, attempt_index: int) -> dict[str, Any]:
    return {
        "provider_name": provider.name,
        "provider_type": provider.type,
        "provider_adapter": provider.adapter,
        "provider_transport": provider.transport,
        "tier": tier,
        "mode": mode,
        "attempt_index": attempt_index,
        "decision": None,
    }



def _resolve_request_default_params(*, provider: ProviderSpec, tier_spec: ChannelTierSpec) -> dict[str, Any]:
    resolved = dict(provider.default_params)
    resolved.update(tier_spec.tier_default_params)
    resolved.update(tier_spec.provider_param_overrides.get(provider.name, {}))
    return resolved



def _build_request_context(
    *,
    provider: ProviderSpec,
    tier_spec: ChannelTierSpec,
    api_key: str,
    url: str,
    headers: dict[str, str] | None,
    timeout_s: int,
    extra_params: dict[str, Any] | None,
) -> RequestContext:
    ctx = RequestContext(
        provider_name=provider.name,
        provider_type=provider.type,
        endpoint=provider.endpoint,
        api_key=api_key,
        default_params=_resolve_request_default_params(provider=provider, tier_spec=tier_spec),
        headers=headers,
        timeout_s=timeout_s,
        url=url,
        extra_params=extra_params,
    )
    validate_request_context(ctx)
    return ctx



def resolve_execution_plan(
    *,
    channel: str,
    tier: str | None = None,
    mode: str | None = None,
    config_path: str | Path | None = None,
) -> FetchExecutionPlan:
    cfg = load_registry_config(config_path)
    selected_mode = str(mode or os.getenv("SCRAPE_MODE") or "cheap").strip().lower()
    tiers_to_try = _resolve_tiers_for_fetch(cfg, channel=channel, tier=tier, mode=selected_mode)
    steps: list[FetchPlanStep] = []

    for tier_name in tiers_to_try:
        spec = _resolve_channel_tier_from_cfg(cfg, channel=channel, tier=tier_name)
        for provider in spec.providers:
            api_key_present = bool(os.getenv(provider.api_key_env, "").strip())
            steps.append(
                FetchPlanStep(
                    channel=channel,
                    tier=spec.tier,
                    mode=selected_mode,
                    provider_name=provider.name,
                    provider_type=provider.type,
                    provider_adapter=provider.adapter,
                    provider_transport=provider.transport,
                    enabled=provider.enabled,
                    endpoint=provider.endpoint,
                    api_key_env=provider.api_key_env,
                    api_key_present=api_key_present,
                    effective_default_params=_resolve_request_default_params(provider=provider, tier_spec=spec),
                )
            )

    return FetchExecutionPlan(
        channel=channel,
        mode=selected_mode,
        tiers_tried=tiers_to_try,
        steps=steps,
    )



def execution_plan_to_dict(plan: FetchExecutionPlan) -> dict[str, Any]:
    return {
        "channel": plan.channel,
        "mode": plan.mode,
        "tiers_tried": list(plan.tiers_tried),
        "steps": [
            {
                "channel": step.channel,
                "tier": step.tier,
                "mode": step.mode,
                "provider_name": step.provider_name,
                "provider_type": step.provider_type,
                "provider_adapter": step.provider_adapter,
                "provider_transport": step.provider_transport,
                "enabled": step.enabled,
                "endpoint": step.endpoint,
                "api_key_env": step.api_key_env,
                "api_key_present": step.api_key_present,
                "effective_default_params": dict(step.effective_default_params),
            }
            for step in plan.steps
        ],
    }



def resolve_channel_tier(
    *,
    channel: str,
    tier: str = "tier_1",
    config_path: str | Path | None = None,
) -> ChannelTierSpec:
    cfg = load_registry_config(config_path)
    return _resolve_channel_tier_from_cfg(cfg, channel=channel, tier=tier)


def fetch(
    *,
    channel: str,
    url: str,
    tier: str | None = None,
    mode: str | None = None,
    headers: dict[str, str] | None = None,
    extra_params: dict[str, Any] | None = None,
    timeout_s: int = 40,
    config_path: str | Path | None = None,
) -> tuple[str, dict[str, Any]]:
    """Fetch HTML for a given channel.

    Phase 2:
    - ordered provider fallback within a tier
    - ordered tier traversal by mode
    - returns (html, meta)

    Meta includes attempts/failover context for downstream telemetry.
    """

    plan = resolve_execution_plan(channel=channel, tier=tier, mode=mode, config_path=config_path)
    selected_mode = plan.mode
    tiers_to_try = plan.tiers_tried
    cfg = load_registry_config(config_path)
    attempts: list[dict[str, Any]] = []

    for tier_name in tiers_to_try:
        spec = _resolve_channel_tier_from_cfg(cfg, channel=channel, tier=tier_name)

        for idx, provider in enumerate(spec.providers):
            attempt = _build_attempt_row(
                provider=provider,
                tier=spec.tier,
                mode=selected_mode,
                attempt_index=idx,
            )

            if not provider.enabled:
                attempt.update({
                    "final_status": "skipped",
                    "failure_stage": "config",
                    "error": "provider disabled",
                    "decision": "skip",
                })
                attempts.append(attempt)
                continue

            fetcher = ADAPTER_FETCHERS.get(provider.adapter)
            if fetcher is None:
                attempt.update({
                    "final_status": "failed",
                    "failure_stage": "config",
                    "error": f"no fetcher registered for adapter '{provider.adapter}'",
                    "decision": "retryable",
                })
                attempts.append(attempt)
                continue

            try:
                api_key = _require_env(provider.api_key_env)
            except Exception as exc:
                attempt.update({
                    "final_status": "failed",
                    "failure_stage": "config",
                    "error": str(exc),
                    "decision": "retryable",
                })
                attempts.append(attempt)
                continue

            try:
                result: AdapterResult = fetcher(
                    _build_request_context(
                        provider=provider,
                        tier_spec=spec,
                        api_key=api_key,
                        url=url,
                        headers=headers,
                        timeout_s=timeout_s,
                        extra_params=extra_params,
                    )
                )
                validate_adapter_result(result)
            except Exception as exc:
                attempt.update({
                    "final_status": "failed",
                    "failure_stage": "request",
                    "error": str(exc),
                    "decision": _failure_decision_for_exception(exc),
                })
                attempts.append(attempt)
                if attempt["decision"] == "terminal":
                    raise RuntimeError(
                        f"terminal provider exception from {provider.name} for channel '{channel}' tier '{spec.tier}': {exc}"
                    )
                continue

            decision, response_outcome = _decision_for_http_result(
                provider_name=provider.name,
                http_status=result.http_status,
                text=result.text,
            )
            attempt.update({
                "latency_ms": result.latency_ms,
                "http_status": result.http_status,
                "final_status": result.final_status,
                "failure_stage": result.failure_stage,
                "response_outcome": response_outcome,
                "decision": decision,
            })
            attempts.append(attempt)

            if result.http_status < 400:
                meta: dict[str, Any] = {
                    "provider_name": provider.name,
                    "provider_type": provider.type,
                    "provider_adapter": provider.adapter,
                    "provider_transport": provider.transport,
                    "tier": spec.tier,
                    "mode": selected_mode,
                    "tiers_tried": tiers_to_try,
                    "latency_ms": result.latency_ms,
                    "http_status": result.http_status,
                    "final_status": result.final_status,
                    "failure_stage": result.failure_stage,
                    "attempts": attempts,
                    "execution_plan": execution_plan_to_dict(plan),
                    "failover_count": max(0, len([a for a in attempts if a.get('decision') in {'retryable', 'skip'}])),
                }
                return result.text, meta

            if attempt["decision"] == "terminal":
                body = (result.text or "").replace("\n", " ")[:800]
                raise RuntimeError(
                    f"terminal response from {provider.name} for channel '{channel}' tier '{spec.tier}'"
                    f" [{attempt['response_outcome']}]: HTTP {result.http_status}: {body}"
                )

    summary = "; ".join(
        f"{a['provider_name']}:{a.get('http_status', a.get('error', a.get('final_status')))}" for a in attempts
    )
    raise RuntimeError(
        f"all providers failed for channel '{channel}' mode '{selected_mode}'"
        f" across tiers {tiers_to_try}: {summary}"
    )
