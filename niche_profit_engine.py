#!/usr/bin/env python3
import json
import os
import random
import re
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from scrape_clients import ScrapeClient

TARGET_STR_THRESHOLD = 50.0
MIN_ACTIVE_LISTINGS = 10
MAX_ACTIVE_LISTINGS = 5000
DELAY_RANGE = (2.0, 5.0)
REQUEST_TIMEOUT = int(os.getenv("EBAY_SCRAPER_TIMEOUT", "30"))
MAX_RETRIES = int(os.getenv("EBAY_SCRAPER_MAX_RETRIES", "2"))
MAX_ELAPSED_S = float(os.getenv("EBAY_SCRAPER_MAX_ELAPSED_S", "20"))
BACKOFFS = [2, 4]
EBAY_HTML_PROVIDER = os.getenv("EBAY_SCRAPE_PROVIDER", "scrapedo").strip().lower() or "scrapedo"

# scrape.do profile (used when EBAY_SCRAPE_PROVIDER=scrapedo)
EBAY_SCRAPEDO_SUPER = os.getenv("EBAY_SCRAPEDO_SUPER", "true").strip().lower() in {"1", "true", "yes"}
EBAY_SCRAPEDO_GEOCODE = os.getenv("EBAY_SCRAPEDO_GEOCODE", os.getenv("SCRAPEDO_GEOCODE", "us")).strip() or "us"
EBAY_SCRAPEDO_RENDER = os.getenv("EBAY_SCRAPEDO_RENDER", os.getenv("SCRAPEDO_RENDER", "false")).strip().lower() in {"1", "true", "yes"}

EBAY_HTML_CLIENT = ScrapeClient(
    provider=EBAY_HTML_PROVIDER,
    timeout_s=REQUEST_TIMEOUT,
    max_retries=MAX_RETRIES,
    max_elapsed_s=MAX_ELAPSED_S,
)

TEST_SEEDS = [
    "adhd digital planner",
    "fitness tracker spreadsheet",
    "wedding budget google sheets",
]

BASE_DIR = Path("/home/agent/autofinisher-factory")
OUTPUT_DIR = BASE_DIR / "niche_engine" / "accepted"
OUTPUT_PATH = OUTPUT_DIR / "niche_package.json"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def dedupe_keep_order(items):
    seen = set()
    output = []
    for item in items:
        key = re.sub(r"\s+", " ", str(item).strip().lower())
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(re.sub(r"\s+", " ", str(item).strip()))
    return output


def parse_number_fragment(value: str) -> int:
    """Parse numeric fragments defensively.

    eBay count headings sometimes include query text; we must avoid accidentally
    concatenating years (e.g., "2026, 2027, 2028") into huge fake numbers.
    """
    raw = (value or "")
    digits = re.sub(r"[^\d]", "", raw)
    if not digits.isdigit():
        return 0

    # Drop obvious year-only tokens.
    if len(digits) <= 4:
        number = int(digits)
        if 2024 <= number <= 2030:
            return 0
        return number

    # If the raw fragment contains multiple year tokens, treat as noise.
    if re.search(r"\b20(?:2[0-9]|3[0-9])\b", raw) and len(digits) >= 8:
        return 0

    number = int(digits)

    # Hard sanity cap: counts above this are almost certainly parse noise.
    if number > 10_000_000:
        return 0

    return number


def get_google_suggests(seed_keyword: str) -> list[str]:
    print(f"[Google] Ищем подсказки для: {seed_keyword}")
    url = "https://suggestqueries.google.com/complete/search"
    params = {"client": "chrome", "q": seed_keyword}
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json,text/plain,*/*",
    }

    suggestions = [seed_keyword]
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list) and len(payload) > 1 and isinstance(payload[1], list):
            suggestions.extend(payload[1])
    except Exception as e:
        print(f"[!] Ошибка Google Suggest для '{seed_keyword}': {e}")

    return dedupe_keep_order(suggestions)


EBAY_QUERY_MAX_TOKENS = int(os.getenv("EBAY_QUERY_MAX_TOKENS", "6"))
EBAY_QUERY_MIN_TOKENS = int(os.getenv("EBAY_QUERY_MIN_TOKENS", "4"))


def normalize_ebay_query(text: str) -> str:
    """Normalize raw niche text into a stable eBay query.

    Goals:
    - remove obvious platform words (etsy/ebay/google sheets, etc.)
    - strip year tokens and noisy numbers ("2026 2027", "75 day")
    - keep 4–6 meaningful tokens (configurable)

    This reduces false parse matches where the heading includes the query/title.
    """
    raw = re.sub(r"\s+", " ", str(text or "").strip())
    if not raw:
        return ""

    # Drop punctuation that creates token splits.
    cleaned = re.sub(r"[^\w\s]", " ", raw, flags=re.UNICODE)
    tokens = [t for t in cleaned.lower().split() if t]

    drop_words = {
        "etsy",
        "ebay",
        "amazon",
        "shopify",
        "gumroad",
        "pinterest",
        "tiktok",
        "youtube",
        "google",
        "goodnotes",
        "notability",
        "ipad",
        "pdf",
        "svg",
        "canva",
        "notion",
        "sheet",
        "sheets",
        "spreadsheet",
        "template",
        "printable",
        "digital",
        "download",
        "bundle",
    }

    filtered: list[str] = []
    for tok in tokens:
        if tok in drop_words:
            continue
        # strip pure years / dates / day counts
        if tok.isdigit():
            n = int(tok)
            if 1900 <= n <= 2100:
                continue
            if n <= 366:
                continue
            continue
        # drop year-ish tokens like 2026-2027
        if re.fullmatch(r"20\d{2}", tok):
            continue
        filtered.append(tok)

    if not filtered:
        # fallback to raw tokens w/out platform words (preserve at least something)
        filtered = [t for t in tokens if t not in drop_words]

    max_toks = max(1, EBAY_QUERY_MAX_TOKENS)
    min_toks = max(1, EBAY_QUERY_MIN_TOKENS)

    out = filtered[:max_toks]
    if len(out) < min_toks and len(filtered) > len(out):
        out = filtered[:min_toks]

    return " ".join(out).strip()


def build_ebay_search_url(keyword: str, sold: bool = False) -> str:
    quoted_kw = urllib.parse.quote(keyword)
    base = f"https://www.ebay.com/sch/i.html?_nkw={quoted_kw}"
    if sold:
        return f"{base}&LH_Sold=1&LH_Complete=1"
    return base


def fetch_ebay_html(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "en-US,en;q=0.9",
    }

    extra_params = None
    send_headers = True
    if EBAY_HTML_PROVIDER == "scrapedo":
        extra_params = {
            "super": "true" if EBAY_SCRAPEDO_SUPER else "false",
            "geoCode": EBAY_SCRAPEDO_GEOCODE,
            "render": "true" if EBAY_SCRAPEDO_RENDER else "false",
            "customHeaders": "false",
        }
        # Let scrape.do handle browser headers.
        send_headers = False

    html, _meta = EBAY_HTML_CLIENT.fetch_html_with_meta(url=url, headers=headers, extra_params=extra_params, send_headers=send_headers)
    return html


def extract_count_from_ebay(html: str) -> int:
    soup = BeautifulSoup(html, "html.parser")

    selectors = [
        "h1.srp-controls__count-heading span.BOLD",
        "h1.srp-controls__count-heading .BOLD",
        "h1.srp-controls__count-heading span",
        "h1.srp-controls__count-heading",
        ".srp-controls__count-heading span.BOLD",
        ".srp-controls__count-heading .BOLD",
        ".srp-controls__count-heading span",
        ".srp-controls__count-heading",
        ".srp-controls__count-heading__count",
        ".srp-controls__count-heading__title",
        ".srp-controls__count-heading-results",
        ".srp-controls__count-heading-results-no-prefix",
        ".srp-controls__count",
        ".srp-controls__count-heading .LIGHT_HIGHLIGHT",
    ]

    for selector in selectors:
        for tag in soup.select(selector):
            text = tag.get_text(" ", strip=True)
            if not text:
                continue

            # NOTE: Do NOT include a catch-all "any number" pattern here.
            # These heading elements often contain query/title text with years
            # or challenge numbers (e.g., "2026 2027 2028", "75 day challenge").
            # We only accept numbers when they are explicitly tied to result/count tokens.
            direct_patterns = [
                r"\bshowing\s+[\d][\d,\.\s]*\s*-\s*[\d][\d,\.\s]*\s+of\s+([\d][\d,\.\s]*)\b",
                # eBay often renders counts as "1,000 + results for ..."
                r"\b([\d][\d,\.\s]*)\s*(?:\+)?\s+results?\s+for\b",
                r"\b([\d][\d,\.\s]*)\s*(?:\+)?\s+results?\s+found\b",
                r"\b([\d][\d,\.\s]*)\s*(?:\+)?\s+results?\b",
                r"\b([\d][\d,\.\s]*)\s*(?:\+)?\s+items?\b",
            ]
            for pattern in direct_patterns:
                match = re.search(pattern, text, flags=re.IGNORECASE)
                if match:
                    count = parse_number_fragment(match.group(1))
                    if count > 0:
                        return count

    text_candidates = []
    body = soup.body if soup.body else soup
    for chunk in body.stripped_strings:
        cleaned = re.sub(r"\s+", " ", chunk).strip()
        if cleaned:
            text_candidates.append(cleaned)

    upper_text = " ".join(text_candidates[:300])

    patterns = [
        r"([\d][\d,\.\s]*)\s*(?:\+)?\s+results?\s+for\b",
        r"([\d][\d,\.\s]*)\s*(?:\+)?\s+results?\s+found\b",
        r"([\d][\d,\.\s]*)\s*(?:\+)?\s+results?\b",
        r"\bshowing\s+[\d][\d,\.\s]*\s*-\s*[\d][\d,\.\s]*\s+of\s+([\d][\d,\.\s]*)\s*(?:\+)?\s+results?\b",
        r"\bof\s+([\d][\d,\.\s]*)\s*(?:\+)?\s+results?\b",
        r"([\d][\d,\.\s]*)\s*(?:\+)?\s+items?\b",
        r"([\d][\d,\.\s]*)\s+matches\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, upper_text, flags=re.IGNORECASE)
        if match:
            count = parse_number_fragment(match.group(1))
            if count > 0:
                return count

    for chunk in text_candidates[:100]:
        lower = chunk.lower()
        if any(token in lower for token in ("result", "found", "items", "matches")):
            match = re.search(r"\b([\d][\d,\.\s]*)\b", chunk)
            if match:
                count = parse_number_fragment(match.group(1))
                if count > 0:
                    return count

    return 0


def get_ebay_metrics(keyword: str) -> dict:
    normalized_query = normalize_ebay_query(keyword)
    query_for_urls = normalized_query or keyword
    active_url = build_ebay_search_url(query_for_urls, sold=False)
    sold_url = build_ebay_search_url(query_for_urls, sold=True)

    metrics = {
        "active": 0,
        "sold": 0,
        "active_url": active_url,
        "sold_url": sold_url,
        "active_parser_error": False,
        "sold_parser_error": False,
    }

    try:
        active_html = fetch_ebay_html(active_url)
        metrics["active"] = extract_count_from_ebay(active_html)
        metrics["active_parser_error"] = "parser error" in active_html.lower()
    except Exception as e:
        print(f"[!] Ошибка запроса active eBay для '{keyword}': {e}")

    try:
        sold_html = fetch_ebay_html(sold_url)
        metrics["sold"] = extract_count_from_ebay(sold_html)
        metrics["sold_parser_error"] = "parser error" in sold_html.lower()
    except Exception as e:
        print(f"[!] Ошибка запроса sold eBay для '{keyword}': {e}")

    return metrics


def evaluate_niche_profitability(metrics: dict) -> float:
    active = metrics.get("active", 0)
    sold = metrics.get("sold", 0)

    if active <= 0:
        return 0.0

    return round((sold / active) * 100, 2)


def save_output(seeds: list[str], processed_count: int, profitable_niches: list[dict]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_data = {
        "schema_version": "1.1",
        "seeds": seeds,
        "generated_at": utc_now_iso(),
        "acceptance_rule": f"STR >= {TARGET_STR_THRESHOLD:.1f}%",
        "processed_count": processed_count,
        "accepted_count": len(profitable_niches),
        "items": profitable_niches,
        "niches": profitable_niches,
    }
    OUTPUT_PATH.write_text(json.dumps(output_data, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    base_keywords = TEST_SEEDS[:]
    profitable_niches = []
    processed_count = 0

    print(f"🚀 Запуск Niche Profit Engine. Сидов: {len(base_keywords)}\n")

    for seed in base_keywords:
        suggestions = get_google_suggests(seed)

        for niche in suggestions:
            processed_count += 1
            print(f"🔎 Анализ ниши: '{niche}'")

            metrics = get_ebay_metrics(niche)
            active = metrics["active"]
            sold = metrics["sold"]

            if metrics.get("active_parser_error"):
                print(f"  [!] Active page содержит Parser Error для '{niche}'")
            if metrics.get("sold_parser_error"):
                print(f"  [!] Sold page содержит Parser Error для '{niche}'")

            if active == 0:
                print(f"  [!] Не удалось извлечь active count для '{niche}'. Пропускаем кандидата без падения.")
                sleep_time = random.uniform(*DELAY_RANGE)
                time.sleep(sleep_time)
                continue

            if sold == 0:
                print(f"  [!] Sold count вернулся 0 для '{niche}'. Soft-fail: продолжаем работу, считаем STR с sold=0.")

            str_percent = evaluate_niche_profitability(metrics)
            print(f"  -> Активных: {active} | Проданных: {sold} | STR: {str_percent}%")

            if str_percent >= TARGET_STR_THRESHOLD and MIN_ACTIVE_LISTINGS <= active <= MAX_ACTIVE_LISTINGS:
                print("  ✅ НИША ОДОБРЕНА! Добавляем в пакет.")
                profitable_niches.append(
                    {
                        "niche": niche,
                        "metrics": {
                            "active_listings": active,
                            "sold_listings": sold,
                            "sell_through_rate": str_percent,
                        },
                    }
                )
            else:
                print("  ❌ Не прошла по критериям.")

            sleep_time = random.uniform(*DELAY_RANGE)
            time.sleep(sleep_time)

    save_output(base_keywords, processed_count, profitable_niches)
    print(f"\n🎉 Поиск завершен. Обработано ниш: {processed_count}. Найдено прибыльных ниш: {len(profitable_niches)}.")
    print(f"📦 Результат сохранен в: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
