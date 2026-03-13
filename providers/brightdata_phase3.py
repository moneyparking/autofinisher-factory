from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from providers.smoke_test import build_smoke_report

DEFAULT_URL = "https://www.etsy.com/listing/1682665810/digital-planner"
DEFAULT_CHANNEL = "etsy_listing_html"
DEFAULT_MODE = "expensive"
DEFAULT_TIER = "tier_3"
DEFAULT_TIMEOUT_S = 25
DEFAULT_LEDGER_PATH = ROOT / "data" / "provider_verification" / "brightdata_phase3_latest.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _split_auth(auth_value: str) -> tuple[str, str]:
    cleaned = (auth_value or "").strip()
    if not cleaned:
        raise RuntimeError("BRIGHT_DATA_AUTH is missing")
    if ":" not in cleaned:
        raise RuntimeError("BRIGHT_DATA_AUTH must be in '<username>:<password>' format")
    username, password = cleaned.rsplit(":", 1)
    if not username or not password:
        raise RuntimeError("BRIGHT_DATA_AUTH must contain non-empty username and password")
    return username, password


def _compose_auth(base_auth: str, *, country: str | None = None, state: str | None = None, asn: str | None = None, ip: str | None = None) -> str:
    username, password = _split_auth(base_auth)
    suffixes: list[str] = []
    if country:
        suffixes.extend(["country", str(country).strip().lower()])
    if state:
        suffixes.extend(["state", str(state).strip().lower()])
    if asn:
        suffixes.extend(["asn", str(asn).strip()])
    if ip:
        suffixes.extend(["ip", str(ip).strip()])
    if suffixes:
        username = f"{username}-{'-'.join(suffixes)}"
    return f"{username}:{password}"


def _variant_name(*, country: str | None = None, state: str | None = None, asn: str | None = None, ip: str | None = None) -> str:
    parts = ["base"]
    if country:
        parts.append(f"country_{str(country).lower()}")
    if state:
        parts.append(f"state_{str(state).lower()}")
    if asn:
        parts.append(f"asn_{asn}")
    if ip:
        parts.append(f"ip_{ip.replace('.', '_')}")
    return "__".join(parts)


def _http_status_from_error(error_text: str | None) -> int | None:
    cleaned = str(error_text or "")
    match = re.search(r"brightdata:(\d{3})", cleaned)
    if match:
        return int(match.group(1))
    return None



def _summarize_report(report: dict[str, Any]) -> dict[str, Any]:
    meta = report.get("meta") or {}
    attempts = meta.get("attempts") or []
    error_text = report.get("error")
    return {
        "ok": bool(report.get("ok")),
        "error_type": report.get("error_type"),
        "error": error_text,
        "provider_name": meta.get("provider_name") or "brightdata",
        "tier": meta.get("tier") or report.get("tier"),
        "http_status": meta.get("http_status") or _http_status_from_error(error_text),
        "response_outcome": attempts[-1].get("response_outcome") if attempts else None,
        "failover_count": meta.get("failover_count"),
        "html_len": report.get("html_len"),
        "html_head": report.get("html_head"),
    }


def run_matrix(
    *,
    channel: str,
    url: str,
    mode: str,
    tier: str,
    timeout_s: int,
    base_auth: str,
    endpoint: str | None,
    variants: list[dict[str, str | None]],
) -> dict[str, Any]:
    original_auth = os.getenv("BRIGHT_DATA_AUTH", "")
    original_endpoint = os.getenv("BRIGHT_DATA_ENDPOINT", "")

    results: list[dict[str, Any]] = []
    try:
        for variant in variants:
            composed_auth = _compose_auth(
                base_auth,
                country=variant.get("country"),
                state=variant.get("state"),
                asn=variant.get("asn"),
                ip=variant.get("ip"),
            )
            os.environ["BRIGHT_DATA_AUTH"] = composed_auth
            if endpoint:
                os.environ["BRIGHT_DATA_ENDPOINT"] = endpoint

            report = build_smoke_report(
                channel=channel,
                url=url,
                mode=mode,
                tier=tier,
                timeout_s=timeout_s,
            )
            results.append(
                {
                    "variant": _variant_name(
                        country=variant.get("country"),
                        state=variant.get("state"),
                        asn=variant.get("asn"),
                        ip=variant.get("ip"),
                    ),
                    "auth_flags": {
                        "country": variant.get("country"),
                        "state": variant.get("state"),
                        "asn": variant.get("asn"),
                        "ip": variant.get("ip"),
                    },
                    "report": report,
                    "summary": _summarize_report(report),
                }
            )
    finally:
        if original_auth:
            os.environ["BRIGHT_DATA_AUTH"] = original_auth
        else:
            os.environ.pop("BRIGHT_DATA_AUTH", None)
        if endpoint:
            if original_endpoint:
                os.environ["BRIGHT_DATA_ENDPOINT"] = original_endpoint
            else:
                os.environ.pop("BRIGHT_DATA_ENDPOINT", None)

    activation_decision = "experimental"
    if any(item["summary"].get("ok") for item in results):
        activation_decision = "candidate_for_promotion"

    return {
        "generated_at": _utc_now_iso(),
        "provider": "brightdata",
        "channel": channel,
        "url": url,
        "mode": mode,
        "tier": tier,
        "timeout_s": timeout_s,
        "endpoint": endpoint or os.getenv("BRIGHT_DATA_ENDPOINT") or None,
        "activation_decision": activation_decision,
        "results": results,
    }


def _default_variants(args: argparse.Namespace) -> list[dict[str, str | None]]:
    variants: list[dict[str, str | None]] = [{"country": None, "state": None, "asn": None, "ip": None}]
    if args.country:
        variants.append({"country": args.country, "state": None, "asn": None, "ip": None})
    if args.country and args.state:
        variants.append({"country": args.country, "state": args.state, "asn": None, "ip": None})
    if args.asn:
        variants.append({"country": None, "state": None, "asn": args.asn, "ip": None})
    if args.ip:
        variants.append({"country": None, "state": None, "asn": None, "ip": args.ip})
    return variants


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Bright Data Phase 3 verification matrix and write a ledger report.")
    parser.add_argument("--channel", default=DEFAULT_CHANNEL)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--mode", default=DEFAULT_MODE)
    parser.add_argument("--tier", default=DEFAULT_TIER)
    parser.add_argument("--timeout", dest="timeout_s", type=int, default=DEFAULT_TIMEOUT_S)
    parser.add_argument("--country", default="us", help="Optional Bright Data country flag for a second test variant")
    parser.add_argument("--state", default=None, help="Optional Bright Data state flag; requires country for the most useful variant")
    parser.add_argument("--asn", default=None, help="Optional Bright Data ASN flag test")
    parser.add_argument("--ip", default=None, help="Optional Bright Data dedicated IP flag test")
    parser.add_argument("--endpoint", default=None, help="Optional endpoint override for BRIGHT_DATA_ENDPOINT")
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER_PATH), help="Where to write the verification ledger JSON")
    parser.add_argument("--json", dest="as_json", action="store_true", help="Print JSON to stdout")
    args = parser.parse_args()

    base_auth = os.getenv("BRIGHT_DATA_AUTH", "").strip()
    if not base_auth:
        raise SystemExit("BRIGHT_DATA_AUTH is missing")

    matrix = run_matrix(
        channel=args.channel,
        url=args.url,
        mode=args.mode,
        tier=args.tier,
        timeout_s=args.timeout_s,
        base_auth=base_auth,
        endpoint=args.endpoint,
        variants=_default_variants(args),
    )

    ledger_path = Path(args.ledger)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(json.dumps(matrix, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.as_json:
        print(json.dumps(matrix, ensure_ascii=False, indent=2))
    else:
        print(f"ledger_path: {ledger_path}")
        print(f"activation_decision: {matrix['activation_decision']}")
        for item in matrix["results"]:
            summary = item["summary"]
            print(
                f"- {item['variant']}: ok={summary.get('ok')} "
                f"http_status={summary.get('http_status')} "
                f"response_outcome={summary.get('response_outcome')} "
                f"error_type={summary.get('error_type')}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
