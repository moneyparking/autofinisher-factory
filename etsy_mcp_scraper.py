#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from statistics import mean, median
from typing import Any
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from network_retry import fetch_with_retry
from scrape_clients import ScrapeClient


def _redact_secrets(text: str) -> str:
    """Prevent accidental leakage of provider keys in exception strings."""
    if not text:
        return ""
    redactions = [
        ("apikey=", "apikey=REDACTED"),
        ("api_key=", "api_key=REDACTED"),
        ("token=", "token=REDACTED"),
    ]
    out = text
    for needle, repl in redactions:
        if needle in out:
            # replace value until next & or end
            parts = out.split(needle)
            rebuilt = [parts[0]]
            for seg in parts[1:]:
                if "&" in seg:
                    _val, rest = seg.split("&", 1)
                    rebuilt.append(repl + "&" + rest)
                else:
                    rebuilt.append(repl)
            out = "".join(rebuilt)
    return out

BASE_DIR = Path("/home/agent/autofinisher-factory")
SELECTORS_PATH = BASE_DIR / "etsy_selectors.json"
TIMEOUT = int(os.getenv("ETSY_SCRAPER_TIMEOUT", "10"))
MAX_RETRIES = int(os.getenv("ETSY_SCRAPER_MAX_RETRIES", "1"))
MAX_ELAPSED_S = float(os.getenv("ETSY_SCRAPER_MAX_ELAPSED_S", "15"))
BACKOFFS = [2, 4]
FAST_ORDER = os.getenv("ETSY_FAST_ORDER", "most_relevant").strip() or "most_relevant"
ETSY_HTML_PROVIDER = os.getenv("ETSY_SCRAPE_PROVIDER", "scrapedo").strip().lower() or "scrapedo"
ETSY_SCRAPEDO_SUPER = os.getenv("ETSY_SCRAPEDO_SUPER", "true").strip().lower() in {"1", "true", "yes"}
ETSY_SCRAPEDO_GEOCODE = os.getenv("ETSY_SCRAPEDO_GEOCODE", "us").strip() or "us"
ETSY_SCRAPEDO_RENDER = os.getenv("ETSY_SCRAPEDO_RENDER", "false").strip().lower() in {"1", "true", "yes"}

# ZenRows profile (API params)
ETSY_ZENROWS_PREMIUM_PROXY = os.getenv("ZENROWS_ETSY_PREMIUM_PROXY", "true").strip().lower() in {"1", "true", "yes"}
ETSY_ZENROWS_JS_RENDER = os.getenv("ZENROWS_ETSY_JS_RENDER", "false").strip().lower() in {"1", "true", "yes"}
ETSY_ZENROWS_PROXY_COUNTRY = os.getenv("ZENROWS_PROXY_COUNTRY", "us").strip() or "us"

ETSY_HTML_CLIENT = ScrapeClient(
    provider=ETSY_HTML_PROVIDER,
    timeout_s=TIMEOUT,
    max_retries=MAX_RETRIES,
    max_elapsed_s=MAX_ELAPSED_S,
)


def load_selectors() -> dict[str, Any]:
    return json.loads(SELECTORS_PATH.read_text(encoding="utf-8"))


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip())


def parse_price(text: str) -> float | None:
    m = re.search(r"(\d+[\d,.]*)", text or "")
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except Exception:
        return None


def parse_int(text: str) -> int | None:
    m = re.search(r"(\d[\d,]*)", text or "")
    if not m:
        return None
    try:
        return int(m.group(1).replace(",", ""))
    except Exception:
        return None


def parse_rating(text: str) -> float | None:
    m = re.search(r"(\d(?:\.\d)?)", text or "")
    if not m:
        return None
    try:
        return float(m.group(1))
    except Exception:
        return None


def scraperapi_fetch_with_meta(url: str) -> tuple[str, dict[str, Any]]:
    headers = {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"}
    extra_params: dict[str, Any] | None = None
    send_headers = True

    if ETSY_HTML_PROVIDER == "scrapedo":
        extra_params = {
            "super": "true" if ETSY_SCRAPEDO_SUPER else "false",
            "geoCode": ETSY_SCRAPEDO_GEOCODE,
            "render": "true" if ETSY_SCRAPEDO_RENDER else "false",
            "customHeaders": "false",
        }
        # Let scrape.do handle browser headers.
        send_headers = False

    elif ETSY_HTML_PROVIDER == "zenrows":
        # ZenRows: send only enabled params. Some accounts reject unsupported options even when set to false.
        params: dict[str, Any] = {}
        if ETSY_ZENROWS_PREMIUM_PROXY:
            params["premium_proxy"] = "true"
            # proxy_country only makes sense with premium proxies
            if ETSY_ZENROWS_PROXY_COUNTRY:
                params["proxy_country"] = ETSY_ZENROWS_PROXY_COUNTRY
        if ETSY_ZENROWS_JS_RENDER:
            params["js_render"] = "true"
        extra_params = params or None
        # ZenRows works fine with our basic headers.
        send_headers = True

    html, meta = ETSY_HTML_CLIENT.fetch_html_with_meta(url=url, headers=headers, extra_params=extra_params, send_headers=send_headers)
    return str(html), meta


def scraperapi_fetch(url: str) -> str:
    html, _meta = scraperapi_fetch_with_meta(url)
    return html


def text_by_selector(node, selector: str) -> str:
    tag = node.select_one(selector)
    return normalize(tag.get_text(" ", strip=True)) if tag else ""


def href_by_selector(node, selector: str) -> str | None:
    tag = node.select_one(selector)
    if not tag:
        return None
    href = tag.get("href")
    return normalize(href) if href else None


def detect_digital(text: str, markers: list[str]) -> bool:
    low = normalize(text).lower()
    return any(marker.lower() in low for marker in markers)


def aggregate_listings(listings: list[dict[str, Any]]) -> dict[str, Any]:
    prices = [x["price"] for x in listings if isinstance(x.get("price"), (int, float))]
    ratings = [x["rating"] for x in listings if isinstance(x.get("rating"), (int, float))]
    reviews = [x["reviews_count"] for x in listings if isinstance(x.get("reviews_count"), int)]
    digital_count = sum(1 for x in listings if x.get("is_digital"))
    return {
        "avg_price": round(mean(prices), 2) if prices else None,
        "median_price": round(median(prices), 2) if prices else None,
        "avg_rating": round(mean(ratings), 2) if ratings else None,
        "avg_reviews_top": round(mean(reviews), 2) if reviews else None,
        "digital_share": round(digital_count / len(listings), 3) if listings else 0.0,
        "listing_count": len(listings),
    }


def scan_keywords(keywords: list[str], max_listings_per_keyword: int = 24) -> dict[str, Any]:
    selectors = load_selectors()["etsy_search"]
    results = []

    for keyword in keywords:
        url = f"https://www.etsy.com/search?q={quote_plus(keyword)}&order={quote_plus(FAST_ORDER)}"
        try:
            html, req_meta = scraperapi_fetch_with_meta(url)
        except Exception as exc:
            msg = _redact_secrets(str(exc))
            print(f"[etsy_mcp_scraper] scan failed for keyword='{keyword}': {msg}")
            results.append({
                "keyword": keyword,
                "request_meta": {"final_status": "failed", "error": msg},
                "search_metadata": {
                    "total_results": None,
                    "scanned_results": 0,
                    "digital_share": 0.0,
                },
                "listings": [],
                "aggregates": {
                    "avg_price": None,
                    "median_price": None,
                    "avg_rating": None,
                    "avg_reviews_top": None,
                    "digital_share": 0.0,
                    "listing_count": 0,
                },
            })
            continue
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(selectors["listing_card"])[:max_listings_per_keyword]
        results_text = text_by_selector(soup, selectors["results_text"])
        total_results = parse_int(results_text)
        listings = []

        for card in cards:
            title = text_by_selector(card, selectors["title"])
            price_text = text_by_selector(card, selectors["price"])
            shop_name = text_by_selector(card, selectors["shop"])
            rating_text = text_by_selector(card, selectors["rating"])
            reviews_text = text_by_selector(card, selectors["reviews"])
            href = href_by_selector(card, selectors["link"])
            blob_text = normalize(card.get_text(" ", strip=True))
            listings.append({
                "listing_id": None,
                "title": title,
                "url": href,
                "shop_name": shop_name or None,
                "price": parse_price(price_text),
                "currency": "USD" if "$" in price_text else None,
                "rating": parse_rating(rating_text),
                "reviews_count": parse_int(reviews_text),
                "is_digital": detect_digital(blob_text, ["digital", "download", "printable", "template"]),
                "last_review_snippet": None,
            })

        aggregates = aggregate_listings(listings)
        results.append({
            "keyword": keyword,
            "request_meta": req_meta,
            "search_metadata": {
                "total_results": total_results,
                "scanned_results": len(listings),
                "digital_share": aggregates["digital_share"],
            },
            "listings": listings,
            "aggregates": aggregates,
        })

    return {"results": results}


def inspect_listing(url: str, max_reviews: int = 5) -> dict[str, Any]:
    selectors = load_selectors()["etsy_listing"]
    try:
        html, req_meta = scraperapi_fetch_with_meta(url)
    except Exception as exc:
        msg = _redact_secrets(str(exc))
        print(f"[etsy_mcp_scraper] inspect failed for url='{url}': {msg}")
        return {
            "listing_id": None,
            "title": "",
            "price": None,
            "currency": "USD",
            "is_digital": False,
            "digital_markers": [],
            "rating": None,
            "reviews_count": None,
            "tags": [],
            "category_path": [],
            "shop": {"name": None, "url": None},
            "reviews": {"sample": []},
        }
    soup = BeautifulSoup(html, "html.parser")
    page_text = normalize(soup.get_text(" ", strip=True))

    # Etsy listing pages often contain a "X sales" badge. Optional but useful.
    sales_count = None
    try:
        matches = re.findall(r"(\d[\d,]*)\s+sales", page_text.lower())
        if matches:
            sales_count = max(int(x.replace(",", "")) for x in matches)
    except Exception:
        sales_count = None

    review_items = soup.select(selectors["review_item"])[:max_reviews]
    reviews = []

    for item in review_items:
        reviews.append({
            "rating": parse_rating(text_by_selector(item, selectors["review_rating"])),
            "date": text_by_selector(item, selectors["review_date"]) or None,
            "text": text_by_selector(item, selectors["review_text"]),
            "author": None,
        })

    return {
        "listing_id": None,
        "title": text_by_selector(soup, selectors["title"]),
        "price": parse_price(text_by_selector(soup, selectors["price"])),
        "currency": "USD",
        "is_digital": detect_digital(page_text, selectors["digital_markers"]),
        "digital_markers": [m for m in selectors["digital_markers"] if m.lower() in page_text.lower()],
        "rating": parse_rating(text_by_selector(soup, selectors["rating"])),
        "reviews_count": parse_int(text_by_selector(soup, selectors["reviews_count"])),
        "sales_count": sales_count,
        "tags": [normalize(x.get_text(" ", strip=True)) for x in soup.select(selectors["tags"])[:20]],
        "category_path": [],
        "shop": {
            "name": None,
            "url": href_by_selector(soup, selectors["shop_link"]),
        },
        "reviews": {
            "sample": reviews,
        },
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Etsy scraper MVP")
    sub = parser.add_subparsers(dest="cmd", required=True)

    scan = sub.add_parser("scan")
    scan.add_argument("keywords", nargs="+")
    scan.add_argument("--max-listings", type=int, default=24)

    inspect_cmd = sub.add_parser("inspect")
    inspect_cmd.add_argument("url")
    inspect_cmd.add_argument("--max-reviews", type=int, default=5)

    args = parser.parse_args()
    if args.cmd == "scan":
        print(json.dumps(scan_keywords(args.keywords, args.max_listings), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(inspect_listing(args.url, args.max_reviews), ensure_ascii=False, indent=2))
