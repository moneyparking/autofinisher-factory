from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from providers.registry import (
    _repo_root,
    execution_plan_to_dict,
    load_registry_config,
    resolve_execution_plan,
)


VALID_PROVIDER_FIELDS = (
    "type",
    "adapter",
    "transport",
    "enabled",
    "api_key_env",
    "endpoint_env",
    "endpoint_default",
    "default_params",
)


def _env_value(name: str) -> str:
    import os

    return os.getenv(name, "").strip()


def _provider_status(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    provider_type = str(payload.get("type") or "").strip() or None
    adapter = str(payload.get("adapter") or provider_type or "").strip() or None
    transport = str(payload.get("transport") or "rest_api").strip() or None
    enabled = bool(payload.get("enabled", True))
    api_key_env = str(payload.get("api_key_env") or "").strip() or None
    endpoint_env = str(payload.get("endpoint_env") or "").strip() or None
    endpoint_default = str(payload.get("endpoint_default") or "").strip() or None

    problems: list[str] = []
    if not provider_type:
        problems.append("missing provider type")
    if not adapter:
        problems.append("missing adapter")
    if not transport:
        problems.append("missing transport")
    if not api_key_env:
        problems.append("missing api_key_env")

    api_key_status = "OK" if api_key_env and _env_value(api_key_env) else "MISSING"

    endpoint_value = ""
    endpoint_source = None
    if endpoint_env and _env_value(endpoint_env):
        endpoint_value = _env_value(endpoint_env)
        endpoint_source = endpoint_env
    elif endpoint_default:
        endpoint_value = endpoint_default
        endpoint_source = "endpoint_default"
    elif transport != "http_proxy":
        problems.append("missing endpoint")

    endpoint_status = "OK" if endpoint_value else ("MISSING" if transport != "http_proxy" else "OK")

    status = "OK"
    if not enabled:
        status = "DISABLED"
    elif problems:
        status = "INVALID"
    elif api_key_status != "OK" or endpoint_status != "OK":
        status = "MISSING"

    return {
        "provider": name,
        "type": provider_type,
        "adapter": adapter,
        "transport": transport,
        "enabled": enabled,
        "status": status,
        "api_key_env": api_key_env,
        "api_key_status": api_key_status,
        "endpoint": endpoint_value or None,
        "endpoint_status": endpoint_status,
        "endpoint_source": endpoint_source,
        "source_of_truth": ".env.scrape.local",
        "problems": problems,
    }


def _channel_status(name: str, payload: dict[str, Any], known_providers: set[str]) -> dict[str, Any]:
    tiers = payload.get("tiers")
    waterfall = payload.get("waterfall") or {}
    tier_rows: list[dict[str, Any]] = []
    waterfall_rows: list[dict[str, Any]] = []
    problems: list[str] = []
    if not isinstance(tiers, dict):
        return {
            "channel": name,
            "status": "INVALID",
            "tiers": [],
            "waterfall": [],
            "problems": ["missing tiers mapping"],
        }

    for tier_name, tier_payload in tiers.items():
        if not isinstance(tier_payload, dict):
            tier_rows.append(
                {
                    "tier": tier_name,
                    "providers": [],
                    "status": "INVALID",
                    "problems": ["tier payload must be a mapping"],
                }
            )
            problems.append(f"tier '{tier_name}' payload must be a mapping")
            continue

        provider_name = str(tier_payload.get("provider") or "").strip()
        providers_list = tier_payload.get("providers")
        resolved: list[str] = []
        if provider_name:
            resolved.append(provider_name)
        if isinstance(providers_list, list):
            resolved.extend(str(item).strip() for item in providers_list if str(item).strip())

        deduped: list[str] = []
        seen: set[str] = set()
        for item in resolved:
            if item in seen:
                continue
            seen.add(item)
            deduped.append(item)

        row_problems: list[str] = []
        status = "OK"
        if not deduped:
            row_problems.append("missing provider/providers")
            status = "INVALID"
        else:
            for provider in deduped:
                if provider not in known_providers:
                    row_problems.append(f"provider '{provider}' not defined")
                    status = "INVALID"

        tier_rows.append(
            {
                "tier": tier_name,
                "providers": deduped,
                "status": status,
                "problems": row_problems,
            }
        )
        problems.extend(row_problems)

    known_tiers = set(tiers.keys())
    if waterfall and not isinstance(waterfall, dict):
        problems.append("waterfall must be a mapping")
    elif isinstance(waterfall, dict):
        for mode_name, mode_tiers in waterfall.items():
            row_problems: list[str] = []
            resolved_tiers: list[str] = []
            if not isinstance(mode_tiers, list):
                row_problems.append("waterfall mode must be a list")
            else:
                for item in mode_tiers:
                    tier_name = str(item).strip()
                    if not tier_name:
                        continue
                    resolved_tiers.append(tier_name)
                    if tier_name not in known_tiers:
                        row_problems.append(f"tier '{tier_name}' not defined")
            waterfall_rows.append(
                {
                    "mode": str(mode_name),
                    "tiers": resolved_tiers,
                    "status": "OK" if not row_problems else "INVALID",
                    "problems": row_problems,
                }
            )
            problems.extend(row_problems)

    execution_plans: list[dict[str, Any]] = []
    if not problems:
        for mode_name in ("cheap", "balanced", "expensive"):
            try:
                execution_plans.append(execution_plan_to_dict(resolve_execution_plan(channel=name, mode=mode_name)))
            except Exception as exc:
                execution_plans.append({
                    "channel": name,
                    "mode": mode_name,
                    "error": str(exc),
                })

    return {
        "channel": name,
        "status": "OK" if not problems else "INVALID",
        "tiers": tier_rows,
        "waterfall": waterfall_rows,
        "execution_plans": execution_plans,
        "problems": problems,
    }


def build_report(config_path: str | None = None) -> dict[str, Any]:
    cfg = load_registry_config(config_path)
    providers = cfg.get("providers") or {}
    channels = cfg.get("channels") or {}
    if not isinstance(providers, dict) or not isinstance(channels, dict):
        raise RuntimeError("providers.yaml must contain 'providers' and 'channels' mappings")

    provider_reports = [_provider_status(name, payload) for name, payload in providers.items() if isinstance(payload, dict)]
    known_providers = {row["provider"] for row in provider_reports}
    channel_reports = [_channel_status(name, payload, known_providers) for name, payload in channels.items() if isinstance(payload, dict)]

    return {
        "config_path": str(Path(config_path) if config_path else (_repo_root() / "providers.yaml")),
        "source_of_truth": ".env.scrape.local",
        "providers": provider_reports,
        "channels": channel_reports,
    }


def _print_human(report: dict[str, Any]) -> None:
    print(f"Config: {report['config_path']}")
    print(f"Credentials source-of-truth: {report['source_of_truth']}")
    print("")
    print("Providers:")
    for row in report["providers"]:
        print(f"- {row['provider']}: {row['status']}")
        print(f"  type: {row['type'] or 'UNKNOWN'}")
        print(f"  adapter: {row['adapter'] or 'UNKNOWN'}")
        print(f"  transport: {row['transport'] or 'UNKNOWN'}")
        print(f"  enabled: {row['enabled']}")
        print(f"  api_key_env: {row['api_key_env'] or 'MISSING'} -> {row['api_key_status']}")
        print(f"  endpoint: {row['endpoint'] or 'MISSING'} -> {row['endpoint_status']}")
        if row["endpoint_source"]:
            print(f"  endpoint_source: {row['endpoint_source']}")
        if row["api_key_status"] != "OK" and row["api_key_env"]:
            print(f"  action: put {row['api_key_env']} into .env.scrape.local")
        for problem in row["problems"]:
            print(f"  problem: {problem}")
    print("")
    print("Channels:")
    for row in report["channels"]:
        print(f"- {row['channel']}: {row['status']}")
        for tier in row["tiers"]:
            providers = ", ".join(tier['providers']) if tier['providers'] else 'MISSING'
            print(f"  {tier['tier']} -> [{providers}] -> {tier['status']}")
            for problem in tier["problems"]:
                print(f"    problem: {problem}")
        for wf in row.get("waterfall", []):
            tiers = ", ".join(wf['tiers']) if wf['tiers'] else 'MISSING'
            print(f"  mode {wf['mode']} -> [{tiers}] -> {wf['status']}")
            for problem in wf["problems"]:
                print(f"    problem: {problem}")
        for plan in row.get("execution_plans", []):
            if plan.get("error"):
                print(f"  plan {plan['mode']} -> ERROR: {plan['error']}")
                continue
            print(f"  plan {plan['mode']} -> tiers {plan['tiers_tried']}")
            for step in plan.get("steps", []):
                params = ", ".join(f"{k}={v}" for k, v in step.get("effective_default_params", {}).items()) or "none"
                print(
                    f"    {step['tier']} :: {step['provider_name']} "
                    f"(enabled={step['enabled']}, key={'yes' if step['api_key_present'] else 'no'}) "
                    f"params[{params}]"
                )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate providers.yaml and env presence without printing secrets.")
    parser.add_argument("--config", dest="config_path", default=None, help="Optional path to providers.yaml")
    parser.add_argument("--json", dest="as_json", action="store_true", help="Print JSON report")
    args = parser.parse_args()

    report = build_report(args.config_path)
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_human(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
