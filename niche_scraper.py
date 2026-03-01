#!/usr/bin/env python3
import requests
import string
import time
import argparse
import os

WORKSPACE = os.path.expanduser("~/autofinisher-factory")
OUTPUT_FILE = os.path.join(WORKSPACE, "keywords.txt")

# SEO-настройки для цифровых товаров
STOP_WORDS = {"free", "app", "apps", "kostenlos", "android", "windows", "software", "best", "builder", "cheap"}
BUYER_INTENT_TRIGGERS = {"for", "template", "adhd", "student", "tracker", "budget", "kids", "wedding", "fitness", "meal", "printable", "bundle"}
MODIFIERS = ["for", "template", "printable", "adhd", "pdf", "goodnotes", "notion", "tracker", "kids", "student"]

def get_google_suggestions(query):
    url = f"https://suggestqueries.google.com/complete/search?client=firefox&q={query}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            return response.json()[1]
    except Exception as e:
        print(f"[!] Ошибка API для '{query}': {e}")
    return []

def is_buyer_intent_niche(sug, seed):
    sug_lower = sug.lower()
    words = sug_lower.split()

    if seed.lower() not in sug_lower:
        return False
    # ЖЕСТКОЕ ПРАВИЛО 1: Длинный хвост (минимум 4 слова)
    if len(words) < 4:
        return False
    # ЖЕСТКОЕ ПРАВИЛО 2: Нет мусора
    if set(words).intersection(STOP_WORDS):
        return False
    # ЖЕСТКОЕ ПРАВИЛО 3: Обязательный коммерческий/нишевый триггер
    if not set(words).intersection(BUYER_INTENT_TRIGGERS):
        return False

    return True

def main():
    parser = argparse.ArgumentParser(description="Google Suggest Smart Niche Scraper")
    parser.add_argument("--seed", required=True, help="Базовое слово, например 'digital planner'")
    parser.add_argument("--limit", type=int, default=15, help="Максимум ниш")
    args = parser.parse_args()

    print(f"🔍 Умный сбор микро-ниш для: '{args.seed}'...")

    # Расширяем поиск: модификаторы + алфавит
    queries_to_test = [args.seed] \
                    + [f"{args.seed} {m}" for m in MODIFIERS] \
                    + [f"{args.seed} {letter}" for letter in string.ascii_lowercase]

    unique_niches = set()

    for q in queries_to_test:
        suggestions = get_google_suggestions(q)
        for sug in suggestions:
            if is_buyer_intent_niche(sug, args.seed):
                unique_niches.add(sug.lower())

        time.sleep(0.5)
        if len(unique_niches) >= args.limit:
            break

    final_niches = list(unique_niches)[:args.limit]

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for niche in final_niches:
            f.write(niche + "\n")

    print(f"✅ Готово! Найдено чистых микро-ниш: {len(final_niches)}")
    for i, niche in enumerate(final_niches[:15], 1):
        print(f"{i}. {niche}")

if __name__ == "__main__":
    main()
