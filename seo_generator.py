#!/usr/bin/env python3
import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path

WORKSPACE = os.path.expanduser('~/autofinisher-factory')
OUTPUT_DIR = Path(WORKSPACE) / 'ready_to_publish'
MAX_TITLE_LEN = 140
MAX_TAGS = 13
MAX_TAG_LEN = 20

STOPWORDS = {
    'a', 'an', 'and', 'or', 'the', 'for', 'with', 'to', 'of', 'in', 'on', 'at', 'by',
    'your', 'from', 'this', 'that', 'into'
}


def normalize_keyword(keyword: str) -> str:
    cleaned = re.sub(r'\s+', ' ', keyword.strip())
    return cleaned


def title_case_phrase(text: str) -> str:
    words = []
    for token in text.split():
        words.append(token if token.isupper() else token.capitalize())
    return ' '.join(words)


def compact(text: str, max_len: int) -> str:
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) <= max_len:
        return text
    cut = text[:max_len].rsplit(' ', 1)[0].strip()
    return cut if cut else text[:max_len].strip()


def dedupe_keep_order(items):
    seen = set()
    out = []
    for item in items:
        key = item.lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item.strip())
    return out


def build_tags(keyword: str):
    words = [w for w in re.findall(r"[a-zA-Z0-9']+", keyword.lower()) if w not in STOPWORDS]
    base = ' '.join(words)
    variants = [
        keyword,
        f'{base} printable',
        f'{base} template',
        f'{base} planner',
        f'{base} pdf',
        f'{base} download',
        f'{base} organizer',
        f'{base} tracker',
        f'{base} gift',
        'digital download',
        'instant download',
        'etsy digital file',
        'printable planner',
        'gumroad template',
        'premium printable',
        'productivity tool',
        'self improvement',
    ]
    if len(words) >= 2:
        variants.extend([
            ' '.join(words[:2]),
            f'{words[0]} {words[-1]}',
        ])

    cleaned = []
    for item in dedupe_keep_order(variants):
        item = compact(item.lower(), MAX_TAG_LEN)
        if item:
            cleaned.append(item)
    return cleaned[:MAX_TAGS]


def build_title(keyword: str) -> str:
    core = title_case_phrase(keyword)
    candidates = [
        f'{core} Printable PDF, Instant Digital Download, Premium Editable Template',
        f'{core} Digital Download, Premium Printable Template for Etsy & Gumroad',
        f'{core} Instant Download, Printable PDF Template',
    ]
    for candidate in candidates:
        candidate = compact(candidate, MAX_TITLE_LEN)
        if len(candidate) <= MAX_TITLE_LEN:
            return candidate
    return compact(core, MAX_TITLE_LEN)


def build_description(keyword: str):
    pretty = title_case_phrase(keyword)
    bullets = [
        f'High-conversion niche product built around: {pretty}.',
        'Clean digital format designed for instant delivery and easy resale packaging.',
        'Suitable for Etsy, Gumroad, Pinterest traffic funnels, and print-on-demand style listings.',
        'Fast to use: download, print, duplicate, or bundle into a themed product line.',
    ]
    how_to = [
        'Purchase or download the file.',
        'Open it on desktop, tablet, or mobile depending on your workflow.',
        'Print at home / office or use it digitally in your preferred app.',
        'Pair it with matching mockups and SEO tags for stronger marketplace conversion.',
    ]
    body = [
        f'{pretty} is packaged as a premium digital product created for shoppers who want a polished, ready-to-use solution.',
        '',
        'What is included:',
        *[f'- {item}' for item in bullets],
        '',
        'How to use:',
        *[f'- {item}' for item in how_to],
        '',
        'Notes:',
        '- Digital product only. No physical item is shipped.',
        '- Colors may vary slightly between screens and printers.',
        '- Perfect for niche storefront testing, bundles, and seasonal listing refreshes.',
    ]
    return '\n'.join(body)


def build_payload(keyword: str):
    return {
        'keyword': keyword,
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'title': build_title(keyword),
        'tags': build_tags(keyword),
        'description': build_description(keyword),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='SEO listing generator for Etsy and Gumroad.')
    parser.add_argument('--keyword', required=True, help='Input niche keyword.')
    args = parser.parse_args()

    keyword = normalize_keyword(args.keyword)
    if not keyword:
        raise SystemExit('Keyword must not be empty.')

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_payload(keyword)
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    safe_keyword = re.sub(r'[^a-zA-Z0-9_-]+', '-', keyword.strip()).strip('-').lower()
    out_path = OUTPUT_DIR / f'seo_{safe_keyword}_{timestamp}.json'
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

    print(json.dumps({'status': 'success', 'keyword': keyword, 'seo_path': str(out_path), 'title': payload['title']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
