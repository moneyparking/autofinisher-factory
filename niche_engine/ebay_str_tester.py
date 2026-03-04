#!/usr/bin/env python3
from __future__ import annotations

import base64
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import requests
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT_DIR / ".env"
DEFAULT_QUERY = "digital planner"
OAUTH_URL = "https://api.ebay.com/identity/v1/oauth2/token"
BROWSE_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
MARKETPLACE_ID = "EBAY_US"
MAX_PAGE_SIZE = 200
MAX_PAGES = 5
REQUEST_TIMEOUT = 20


class EbayConfigError(RuntimeError):
    pass


@dataclass
class RadarReport:
    niche: str
    active_listings: int
    sold_listings: int
    sell_through_rate: float
    sampled_items: int
    sold_signal_items: int
    notes: List[str]


def load_config() -> tuple[str, str, str]:
    load_dotenv(dotenv_path=ENV_PATH)
    app_id = os.getenv("EBAY_APP_ID", "").strip()
    cert_id = os.getenv("EBAY_CERT_ID", "").strip()
    dev_id = os.getenv("EBAY_DEV_ID", "").strip()

    placeholders = {"", "INSERT_APP_ID_HERE", "INSERT_CERT_ID_HERE"}
    if app_id in placeholders or cert_id in placeholders:
        raise EbayConfigError(
            "eBay credentials are not configured. Update EBAY_APP_ID and EBAY_CERT_ID in .env before running."
        )
    return app_id, cert_id, dev_id


def get_application_token(app_id: str, cert_id: str) -> str:
    credentials = f"{app_id}:{cert_id}".encode("utf-8")
    auth_header = base64.b64encode(credentials).decode("ascii")
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "grant_type": "client_credentials",
        "scope": "https://api.ebay.com/oauth/api_scope",
    }
    response = requests.post(OAUTH_URL, headers=headers, data=data, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    token = payload.get("access_token")
    if not token:
        raise RuntimeError(f"OAuth token missing in response: {payload}")
    return token


def browse_search(token: str, query: str, limit: int = 1, offset: int = 0) -> Dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": MARKETPLACE_ID,
        "Accept": "application/json",
    }
    params = {
        "q": query,
        "limit": str(limit),
        "offset": str(offset),
        "filter": "buyingOptions:{FIXED_PRICE}",
    }
    response = requests.get(BROWSE_URL, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


def fetch_active_listings(token: str, query: str) -> int:
    payload = browse_search(token, query, limit=1, offset=0)
    total = payload.get("total")
    if isinstance(total, int):
        return total
    return int(total or 0)


def item_has_sold_signal(item: Dict[str, Any]) -> bool:
    availability = item.get("availability") or {}
    estimated_sold = availability.get("estimatedSoldQuantity")
    if isinstance(estimated_sold, int) and estimated_sold > 0:
        return True
    if isinstance(estimated_sold, str) and estimated_sold.isdigit() and int(estimated_sold) > 0:
        return True
    title = str(item.get("title") or "").lower()
    return "sold" in title


def fetch_sold_proxy(token: str, query: str) -> tuple[int, int, List[str]]:
    notes: List[str] = []
    sampled_items = 0
    sold_signal_items = 0
    seen_item_ids = set()

    for page in range(MAX_PAGES):
        offset = page * MAX_PAGE_SIZE
        payload = browse_search(token, query, limit=MAX_PAGE_SIZE, offset=offset)
        items = payload.get("itemSummaries") or []
        if not items:
            break

        for item in items:
            item_id = item.get("itemId")
            if item_id in seen_item_ids:
                continue
            seen_item_ids.add(item_id)
            sampled_items += 1
            if item_has_sold_signal(item):
                sold_signal_items += 1

        if len(items) < MAX_PAGE_SIZE:
            break

    notes.append(
        "Sold metric is proxy-based from Browse item summaries (estimatedSoldQuantity / sold signal), not a completed-listings ledger."
    )
    return sampled_items, sold_signal_items, notes


def build_report(query: str) -> RadarReport:
    app_id, cert_id, _dev_id = load_config()
    token = get_application_token(app_id, cert_id)
    active = fetch_active_listings(token, query)
    sampled_items, sold_signal_items, notes = fetch_sold_proxy(token, query)

    if active <= 0:
        sold_estimate = 0
        str_percent = 0.0
        notes.append("Active listings returned zero results.")
    else:
        sold_ratio = (sold_signal_items / sampled_items) if sampled_items else 0.0
        sold_estimate = round(active * sold_ratio)
        str_percent = (sold_estimate / active) * 100 if active else 0.0

    return RadarReport(
        niche=query,
        active_listings=active,
        sold_listings=sold_estimate,
        sell_through_rate=str_percent,
        sampled_items=sampled_items,
        sold_signal_items=sold_signal_items,
        notes=notes,
    )


def render_report(report: RadarReport) -> str:
    lines = [
        "=" * 58,
        "EBAY SELL-THROUGH RADAR",
        "=" * 58,
        f"Niche:            {report.niche}",
        f"Active Listings:  {report.active_listings}",
        f"Sold Listings:    {report.sold_listings}",
        f"STR (%):          {report.sell_through_rate:.2f}%",
        "-" * 58,
        f"Sampled Items:    {report.sampled_items}",
        f"Sold Signals:     {report.sold_signal_items}",
    ]
    if report.notes:
        lines.append("-" * 58)
        lines.append("Notes:")
        lines.extend(f"- {note}" for note in report.notes)
    lines.append("=" * 58)
    return "\n".join(lines)


def main() -> int:
    query = " ".join(sys.argv[1:]).strip() or DEFAULT_QUERY
    try:
        report = build_report(query)
    except EbayConfigError as exc:
        print(f"CONFIG ERROR: {exc}")
        return 2
    except requests.HTTPError as exc:
        response_text = exc.response.text[:1200] if exc.response is not None else str(exc)
        print("HTTP ERROR while querying eBay API:")
        print(response_text)
        return 3
    except Exception as exc:
        print(f"UNEXPECTED ERROR: {exc}")
        return 4

    print(render_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
