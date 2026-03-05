#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import requests

from network_retry import fetch_with_retry
from scrape_clients import ScrapeClient, build_google_url

BASE_DIR = Path("/home/agent/autofinisher-factory")
DEFAULT_ENGINE = os.getenv("GOOGLE_SERP_ENGINE", "searchapi").strip().lower()
GOOGLE_SERP_API_KEY = os.getenv("GOOGLE_SERP_API_KEY", "").strip()
TIMEOUT = int(os.getenv("GOOGLE_SCRAPER_TIMEOUT", "10"))
MAX_RETRIES = int(os.getenv("GOOGLE_SCRAPER_MAX_RETRIES", "1"))
MAX_ELAPSED_S = float(os.getenv("GOOGLE_SCRAPER_MAX_ELAPSED_S", "15"))
BACKOFFS = [2, 4]
GOOGLE_HTML_PROVIDER = os.getenv("GOOGLE_SCRAPE_PROVIDER", "scrapingbee").strip().lower() or "scrapingbee"
SCRAPINGBEE_GOOGLE_ENDPOINT = os.getenv("SCRAPINGBEE_GOOGLE_ENDPOINT", "https://app.scrapingbee.com/api/v1/google").strip() or "https://app.scrapingbee.com/api/v1/google"
GOOGLE_HTML_CLIENT = ScrapeClient(
    provider=GOOGLE_HTML_PROVIDER,
    timeout_s=TIMEOUT,
    max_retries=MAX_RETRIES,
    max_elapsed_s=MAX_ELAPSED_S,
)
USE_PAA = os.getenv("GOOGLE_FAST_USE_PAA", "0").strip().lower() in {"1", "true", "yes"}
DIGITAL_TOKENS = ["planner", "printable", "template", "notion", "spreadsheet", "checklist", "binder", "tracker", "journal"]


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip())


def fetch_serp(query: str, country: str = "US", language: str = "en", page: int = 1) -> tuple[dict[str, Any], dict[str, Any]]:
    headers = {"User-Agent": "Mozilla/5.0", "Accept-Language": f"{language}-{country},{language};q=0.9"}

    if GOOGLE_SERP_API_KEY:
        if DEFAULT_ENGINE == "serpapi":
            params = {
                "engine": "google",
                "q": query,
                "api_key": GOOGLE_SERP_API_KEY,
                "gl": country,
                "hl": language,
                "start": (page - 1) * 10,
            }

            def _do() -> dict[str, Any]:
                resp = requests.get("https://serpapi.com/search.json", params=params, timeout=TIMEOUT)
                resp.raise_for_status()
                return resp.json()

            data, meta = fetch_with_retry(
                _do,
                max_retries=MAX_RETRIES,
                backoffs=BACKOFFS,
                retry_on=(requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.HTTPError),
                stage="request",
                warnings_prefix="google",
                max_elapsed_s=MAX_ELAPSED_S,
            )
            if data is None:
                raise RuntimeError(meta.get("error") or "google_serp_failed")
            return data, meta

        params = {
            "engine": "google",
            "q": query,
            "api_key": GOOGLE_SERP_API_KEY,
            "gl": country,
            "hl": language,
            "start": (page - 1) * 10,
        }

        def _do2() -> dict[str, Any]:
            resp = requests.get("https://www.searchapi.io/api/v1/search", params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp.json()

        data2, meta2 = fetch_with_retry(
            _do2,
            max_retries=MAX_RETRIES,
            backoffs=BACKOFFS,
            retry_on=(requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.HTTPError),
            stage="request",
            warnings_prefix="google",
            max_elapsed_s=MAX_ELAPSED_S,
        )
        if data2 is None:
            raise RuntimeError(meta2.get("error") or "google_serp_failed")
        return data2, meta2

    if GOOGLE_HTML_PROVIDER == "scrapingbee":
        api_key = os.getenv("SCRAPINGBEE_API_KEY", "").strip()
        params = {
            "api_key": api_key,
            "search": query,
            "language": language,
        }

        def _do_scrapingbee_google() -> dict[str, Any]:
            resp = requests.get(SCRAPINGBEE_GOOGLE_ENDPOINT, params=params, headers=headers, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp.json()

        data3, meta3 = fetch_with_retry(
            _do_scrapingbee_google,
            max_retries=MAX_RETRIES,
            backoffs=BACKOFFS,
            retry_on=(requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.HTTPError),
            stage="request",
            warnings_prefix="google",
            max_elapsed_s=MAX_ELAPSED_S,
        )
        if data3 is None:
            raise RuntimeError(meta3.get("error") or "google_scrapingbee_failed")

        organic_results = data3.get("organic_results") or data3.get("results") or []
        related_searches = data3.get("related_searches") or []
        people_also_ask = data3.get("people_also_ask") or data3.get("paa") or []
        return {
            "organic_results": organic_results,
            "related_searches": related_searches,
            "people_also_ask": people_also_ask,
        }, meta3

    google_url = build_google_url(query, country=country, language=language)
    html, meta3 = GOOGLE_HTML_CLIENT.fetch_html_with_meta(url=google_url, headers=headers)

    titles = re.findall(r"<h3[^>]*>(.*?)</h3>", html, flags=re.I | re.S)
    cleaned_titles = [re.sub(r"<[^>]+>", "", t).strip() for t in titles if t.strip()]
    organic = []
    for idx, title in enumerate(cleaned_titles[:10], start=1):
        organic.append({"title": title, "link": None, "snippet": ""})
    return {"organic_results": organic, "related_searches": [], "people_also_ask": []}, meta3


def has_digital_pattern(text: str) -> bool:
    low = normalize(text).lower()
    return any(token in low for token in DIGITAL_TOKENS)


def parse_serp_to_niches(serp_json: dict[str, Any]) -> dict[str, Any]:
    organic_out = []
    related = []
    paa = []
    niche_candidates: set[str] = set()
    total_etsy_results = 0
    etsy_domains: set[str] = set()

    for i, item in enumerate(serp_json.get("organic_results", []), start=1):
        url = item.get("link") or item.get("url") or ""
        title = normalize(item.get("title", ""))
        snippet = normalize(item.get("snippet", ""))
        is_etsy = bool(url and "etsy.com" in url.lower())
        is_guide = bool(re.search(r"niches|ideas|best|top|2025|2026|digital products|printables|templates", title.lower()))
        if is_etsy:
            total_etsy_results += 1
            if url.startswith("http"):
                domain = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
                etsy_domains.add(domain)
        organic_out.append({
            "position": i,
            "title": title,
            "url": url or None,
            "snippet": snippet,
            "is_etsy": is_etsy,
            "is_guide": is_guide,
        })
        if has_digital_pattern(title):
            niche_candidates.add(title.lower())
        if has_digital_pattern(snippet):
            niche_candidates.add(snippet.lower())

    for rel in serp_json.get("related_searches", []):
        q = normalize(rel.get("query") or rel.get("keyword") or rel if isinstance(rel, str) else "")
        if q:
            related.append(q)
            if has_digital_pattern(q):
                niche_candidates.add(q.lower())

    if USE_PAA:
        for item in serp_json.get("people_also_ask", []):
            question = normalize(item.get("question", ""))
            answer = normalize(item.get("answer", item.get("snippet", "")))
            if question:
                paa.append({"question": question, "short_answer": answer[:300]})
                if has_digital_pattern(question):
                    niche_candidates.add(question.lower())

    return {
        "organic": organic_out,
        "related_searches": related,
        "people_also_ask": paa,
        "niche_candidates": sorted(niche_candidates),
        "serp_metadata": {
            "total_etsy_results": total_etsy_results,
            "unique_etsy_domains": sorted(etsy_domains),
        },
    }


def scan_google_niches(queries: list[str], country: str = "US", language: str = "en", max_pages: int = 1) -> dict[str, Any]:
    out = {"results": []}
    for q in queries:
        aggregated = {
            "organic": [],
            "related_searches": [],
            "people_also_ask": [],
            "niche_candidates": set(),
            "total_etsy_results": 0,
            "unique_etsy_domains": set(),
            "pages_scanned": 0,
            "request_meta": [],
        }
        for page in range(1, max_pages + 1):
            try:
                serp_json, req_meta = fetch_serp(q, country=country, language=language, page=page)
                aggregated["request_meta"].append({"page": page, "meta": req_meta})
            except Exception as exc:
                print(f"[google_niche_scraper] fetch failed for query='{q}' page={page}: {exc}")
                aggregated["request_meta"].append({"page": page, "meta": {"final_status": "failed", "error": str(exc)}})
                break
            parsed = parse_serp_to_niches(serp_json)
            aggregated["organic"].extend(parsed["organic"])
            aggregated["related_searches"].extend(parsed["related_searches"])
            aggregated["people_also_ask"].extend(parsed["people_also_ask"])
            aggregated["niche_candidates"].update(parsed["niche_candidates"])
            aggregated["total_etsy_results"] += parsed["serp_metadata"]["total_etsy_results"]
            aggregated["unique_etsy_domains"].update(parsed["serp_metadata"]["unique_etsy_domains"])
            aggregated["pages_scanned"] += 1
        out["results"].append({
            "query": q,
            "serp_metadata": {
                "pages_scanned": aggregated["pages_scanned"],
                "total_etsy_results": aggregated["total_etsy_results"],
                "unique_etsy_domains": sorted(aggregated["unique_etsy_domains"]),
            },
            "request_meta": aggregated["request_meta"],
            "organic": aggregated["organic"],
            "related_searches": aggregated["related_searches"],
            "people_also_ask": aggregated["people_also_ask"],
            "niche_candidates": sorted(aggregated["niche_candidates"]),
        })
    return out


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Google niche scraper")
    parser.add_argument("queries", nargs="+")
    parser.add_argument("--country", default="US")
    parser.add_argument("--language", default="en")
    parser.add_argument("--max-pages", type=int, default=1)
    args = parser.parse_args()
    print(json.dumps(scan_google_niches(args.queries, args.country, args.language, args.max_pages), ensure_ascii=False, indent=2))
