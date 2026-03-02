#!/usr/bin/env python3
import argparse
import os
import string
import time
from typing import Iterable, List, Set
from urllib.parse import quote_plus

import requests

WORKSPACE = os.path.expanduser("~/autofinisher-factory")
OUTPUT_FILE = os.path.join(WORKSPACE, "keywords.txt")
HISTORY_FILE = os.path.join(WORKSPACE, "published_history.txt")

STOP_WORDS = {
    "free", "app", "apps", "kostenlos", "android", "windows", "software", "best",
    "builder", "cheap", "reddit", "amazon", "youtube", "canva", "crack", "torrent"
}
BUYER_INTENT_TRIGGERS = {
    "for", "template", "adhd", "student", "tracker", "budget", "kids", "wedding",
    "fitness", "meal", "printable", "bundle", "planner", "checklist", "journal",
    "worksheet", "organizer", "notion", "goodnotes", "editable", "pdf"
}
MODIFIERS = [
    "for", "template", "printable", "adhd", "pdf", "goodnotes", "notion", "tracker",
    "kids", "student", "bundle", "editable", "checklist", "journal", "organizer",
    "for women", "for men", "for moms", "for teachers", "for entrepreneurs"
]
SUFFIXES = [
    "pdf", "instant download", "etsy", "digital download", "bundle", "template",
    "checklist", "tracker", "planner", "journal", "printable"
]
QUESTION_SEEDS = [
    "for beginners", "for adults", "for small business", "for daily use",
    "for productivity", "for self care", "for mental health"
]


def ensure_file(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8"):
            pass


def read_history() -> Set[str]:
    ensure_file(HISTORY_FILE)
    with open(HISTORY_FILE, "r", encoding="utf-8") as handle:
        return {line.strip().lower() for line in handle if line.strip()}


def write_lines(path: str, lines: Iterable[str], mode: str = "w") -> None:
    with open(path, mode, encoding="utf-8") as handle:
        for line in lines:
            handle.write(line + "\n")


def get_google_suggestions(query: str) -> List[str]:
    url = f"https://suggestqueries.google.com/complete/search?client=firefox&q={quote_plus(query)}"
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/122.0 Safari/537.36"}
    try:
        response = requests.get(url, headers=headers, timeout=6)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list):
            return [str(item).strip() for item in data[1] if str(item).strip()]
    except Exception as exc:
        print(f"[!] Google Suggest error for '{query}': {exc}")
    return []


def fallback_suggestions(seed: str) -> List[str]:
    return [
        f"{seed} printable pdf for adhd adults",
        f"{seed} template for small business owners",
        f"{seed} bundle for busy moms",
        f"{seed} tracker printable for students",
        f"{seed} checklist for entrepreneurs",
        f"{seed} planner for mental health",
        f"{seed} journal for productivity",
    ]


def score_niche(suggestion: str, seed: str) -> int:
    words = suggestion.lower().split()
    score = 0
    if seed.lower() in suggestion.lower():
        score += 3
    if len(words) >= 4:
        score += min(4, len(words) - 3)
    score += len(set(words).intersection(BUYER_INTENT_TRIGGERS)) * 3
    if any(token in suggestion.lower() for token in ("for", "template", "printable", "bundle", "pdf")):
        score += 4
    if any(token in suggestion.lower() for token in ("adhd", "small business", "teachers", "entrepreneurs", "moms", "students")):
        score += 4
    if set(words).intersection(STOP_WORDS):
        score -= 10
    return score


def is_buyer_intent_niche(suggestion: str, seed: str) -> bool:
    sug_lower = suggestion.lower().strip()
    words = sug_lower.split()
    if seed.lower() not in sug_lower:
        return False
    if len(words) < 4:
        return False
    if set(words).intersection(STOP_WORDS):
        return False
    if not set(words).intersection(BUYER_INTENT_TRIGGERS):
        return False
    return True


def build_queries(seed: str) -> List[str]:
    queries = [seed]
    queries.extend(f"{seed} {modifier}" for modifier in MODIFIERS)
    queries.extend(f"{seed} {suffix}" for suffix in SUFFIXES)
    queries.extend(f"{seed} {question}" for question in QUESTION_SEEDS)
    queries.extend(f"{seed} {letter}" for letter in string.ascii_lowercase)
    return queries


def collect_unique_niches(seed: str, limit: int, history: Set[str]) -> List[str]:
    ranked = {}
    for query in build_queries(seed):
        suggestions = get_google_suggestions(query)
        if not suggestions:
            suggestions = fallback_suggestions(seed)
        for suggestion in suggestions:
            normalized = suggestion.lower().strip()
            if normalized in history:
                continue
            if not is_buyer_intent_niche(normalized, seed):
                continue
            ranked[normalized] = max(ranked.get(normalized, -999), score_niche(normalized, seed))
        time.sleep(0.15)
        if len(ranked) >= limit * 3:
            break
    ordered = sorted(ranked.items(), key=lambda item: (-item[1], item[0]))
    return [item[0] for item in ordered[:limit]]


def main() -> None:
    parser = argparse.ArgumentParser(description="Stateful Google Suggest niche scraper")
    parser.add_argument("--seed", required=True, help="Base phrase, e.g. 'digital planner'")
    parser.add_argument("--limit", type=int, default=15, help="Maximum number of unique niches")
    args = parser.parse_args()

    ensure_file(OUTPUT_FILE)
    history = read_history()

    print(f"🔍 Stateful нишевой сбор для: '{args.seed}'")
    print(f"📚 История уже опубликованных ниш: {len(history)}")

    final_niches = collect_unique_niches(args.seed.strip(), args.limit, history)
    write_lines(OUTPUT_FILE, final_niches, mode="w")
    if final_niches:
        write_lines(HISTORY_FILE, final_niches, mode="a")

    print(f"✅ Уникальных новых ниш найдено: {len(final_niches)}")
    for idx, niche in enumerate(final_niches, 1):
        print(f"{idx}. {niche}")


if __name__ == "__main__":
    main()
