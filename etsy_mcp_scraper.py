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

BASE_DIR = Path("/home/agent/autofinisher-factory")
SELECTORS_PATH = BASE_DIR / "etsy_selectors.json"
SCRAPERAPI_ENDPOINT = "http://api.scraperapi.com"
SCRAPERAPI_KEY = os.getenv("SCRAPERAPI_KEY", "91984a0389f2c1aaaee9876b58098d27").strip()
TIMEOUT = int(os.getenv("ETSY_SCRAPER_TIMEOUT", "30"))
MAX_RETRIES = int(os.getenv("ETSY_SCRAPER_MAX_RETRIES", "2"))
BACKOFFS = [2, 4]
FAST_ORDER = os.getenv("ETSY_FAST_ORDER", "most_relevant").strip() or "most_relevant"


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


def scraperapi_fetch(url: str) -> str:
    params = {"api_key": SCRAPERAPI_KEY, "url": url, "keep_headers": "true"}
    headers = {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"}
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = requests.get(SCRAPERAPI_ENDPOINT, params=params, headers=headers, timeout=TIMEOUT)
            response.raise_for_status()
            return response.text
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.HTTPError) as exc:
            last_exc = exc
            if attempt < MAX_RETRIES:
                time.sleep(BACKOFFS[min(attempt, len(BACKOFFS) - 1)])
                continue
            raise
    if last_exc is not None:
        raise last_exc
    return ""


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
            html = scraperapi_fetch(url)
        except Exception as exc:
            print(f"[etsy_mcp_scraper] scan failed for keyword='{keyword}': {exc}")
            results.append({
                "keyword": keyword,
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
        html = scraperapi_fetch(url)
    except Exception as exc:
        print(f"[etsy_mcp_scraper] inspect failed for url='{url}': {exc}")
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
