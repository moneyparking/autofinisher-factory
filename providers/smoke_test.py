from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from providers.registry import execution_plan_to_dict, fetch, resolve_execution_plan


def build_smoke_report(
    *,
    channel: str,
    url: str,
    mode: str,
    tier: str | None,
    timeout_s: int,
    headers: dict[str, str] | None = None,
    extra_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    plan = resolve_execution_plan(channel=channel, tier=tier, mode=mode)
    report: dict[str, Any] = {
        "channel": channel,
        "url": url,
        "mode": mode,
        "tier": tier,
        "timeout_s": timeout_s,
        "execution_plan": execution_plan_to_dict(plan),
    }
    try:
        html, meta = fetch(
            channel=channel,
            url=url,
            tier=tier,
            mode=mode,
            timeout_s=timeout_s,
            headers=headers,
            extra_params=extra_params,
        )
        report.update(
            {
                "ok": True,
                "html_len": len(html or ""),
                "html_head": (html or "")[:500],
                "meta": meta,
            }
        )
    except Exception as exc:
        report.update(
            {
                "ok": False,
                "error_type": exc.__class__.__name__,
                "error": str(exc),
            }
        )
    return report


def _print_human(report: dict[str, Any]) -> None:
    print(f"channel: {report['channel']}")
    print(f"url: {report['url']}")
    print(f"mode: {report['mode']}")
    print(f"tier: {report.get('tier') or 'auto'}")
    print(f"timeout_s: {report['timeout_s']}")
    print("execution_plan:")
    for step in report["execution_plan"].get("steps", []):
        params = ", ".join(f"{k}={v}" for k, v in step.get("effective_default_params", {}).items()) or "none"
        print(
            f"  - tier={step['tier']} provider={step['provider_name']} adapter={step['provider_adapter']} "
            f"enabled={step['enabled']} key={'yes' if step['api_key_present'] else 'no'} params[{params}]"
        )
    print("result:")
    if report.get("ok"):
        meta = report.get("meta", {})
        print("  ok: True")
        print(f"  provider_name: {meta.get('provider_name')}")
        print(f"  tier: {meta.get('tier')}")
        print(f"  http_status: {meta.get('http_status')}")
        print(f"  response_outcome: {meta.get('attempts', [{}])[-1].get('response_outcome') if meta.get('attempts') else None}")
        print(f"  failover_count: {meta.get('failover_count')}")
        print(f"  html_len: {report.get('html_len')}")
        print(f"  html_head: {report.get('html_head')}")
    else:
        print("  ok: False")
        print(f"  error_type: {report.get('error_type')}")
        print(f"  error: {report.get('error')}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a provider smoke test with execution plan visibility.")
    parser.add_argument("--channel", required=True, help="Registry channel name, e.g. etsy_listing_html")
    parser.add_argument("--url", required=True, help="Target URL to fetch")
    parser.add_argument("--mode", default="cheap", help="Routing mode: cheap | balanced | expensive")
    parser.add_argument("--tier", default=None, help="Optional explicit tier override, e.g. tier_3")
    parser.add_argument("--timeout", dest="timeout_s", type=int, default=20, help="Timeout in seconds")
    parser.add_argument("--json", dest="as_json", action="store_true", help="Print JSON output")
    args = parser.parse_args()

    report = build_smoke_report(
        channel=args.channel,
        url=args.url,
        mode=args.mode,
        tier=args.tier,
        timeout_s=args.timeout_s,
    )
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_human(report)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
