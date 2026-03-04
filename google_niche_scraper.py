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

BASE_DIR = Path("/home/agent/autofinisher-factory")
DEFAULT_ENGINE = os.getenv("GOOGLE_SERP_ENGINE", "searchapi").strip().lower()
GOOGLE_SERP_API_KEY = os.getenv("GOOGLE_SERP_API_KEY", "").strip()
SCRAPERAPI_KEY = os.getenv("SCRAPERAPI_KEY", "91984a0389f2c1aaaee9876b58098d27").strip()
TIMEOUT = int(os.getenv("GOOGLE_SCRAPER_TIMEOUT", "30"))
MAX_RETRIES = int(os.getenv("GOOGLE_SCRAPER_MAX_RETRIES", "2"))
BACKOFFS = [2, 4]
USE_PAA = os.getenv("GOOGLE_FAST_USE_PAA", "0").strip().lower() in {"1", "true", "yes"}
DIGITAL_TOKENS = ["planner", "printable", "template", "notion", "spreadsheet", "checklist", "binder", "tracker", "journal"]


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip())


def fetch_serp(query: str, country: str = "US", language: str = "en", page: int = 1) -> dict[str, Any]:
    headers = {"User-Agent": "Mozilla/5.0", "Accept-Language": f"{language}-{country},{language};q=0.9"}
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
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
                    resp = requests.get("https://serpapi.com/search.json", params=params, timeout=TIMEOUT)
                    resp.raise_for_status()
                    return resp.json()

                params = {
                    "engine": "google",
                    "q": query,
                    "api_key": GOOGLE_SERP_API_KEY,
                    "gl": country,
                    "hl": language,
                    "start": (page - 1) * 10,
                }
                resp = requests.get("https://www.searchapi.io/api/v1/search", params=params, timeout=TIMEOUT)
                resp.raise_for_status()
                return resp.json()

            params = {
                "api_key": SCRAPERAPI_KEY,
                "url": f"https://www.google.com/search?q={quote_plus(query)}&hl={language}&gl={country}",
                "keep_headers": "true",
            }
            resp = requests.get("http://api.scraperapi.com", params=params, headers=headers, timeout=TIMEOUT)
            resp.raise_for_status()
            html = resp.text
            titles = re.findall(r"<h3[^>]*>(.*?)</h3>", html, flags=re.I | re.S)
            cleaned_titles = [re.sub(r"<[^>]+>", "", t).strip() for t in titles if t.strip()]
            organic = []
            for idx, title in enumerate(cleaned_titles[:10], start=1):
                organic.append({"title": title, "link": None, "snippet": ""})
            return {"organic_results": organic, "related_searches": [], "people_also_ask": []}
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.HTTPError) as exc:
            last_exc = exc
            if attempt < MAX_RETRIES:
                time.sleep(BACKOFFS[min(attempt, len(BACKOFFS) - 1)])
                continue
            raise
    if last_exc is not None:
        raise last_exc
    return {"organic_results": [], "related_searches": [], "people_also_ask": []}


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
        }
        for page in range(1, max_pages + 1):
            try:
                serp_json = fetch_serp(q, country=country, language=language, page=page)
            except Exception as exc:
                print(f"[google_niche_scraper] fetch failed for query='{q}' page={page}: {exc}")
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
