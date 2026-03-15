from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import quote_plus


def _extract_int(value: str | None) -> int:
    text = str(value or "")
    digits = re.findall(r"\d[\d,]*", text)
    if not digits:
        return 0
    try:
        return int(max(digits, key=len).replace(",", ""))
    except Exception:
        return 0


async def fetch_etsy_keywords(seed: str, max_results: int = 200, *, headless: bool = True) -> dict[str, Any]:
    try:
        from playwright.async_api import async_playwright
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("Playwright is not installed. Run 'pip install playwright' and 'playwright install chromium'.") from exc

    url = f"https://www.etsy.com/search?q={quote_plus(seed)}"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        page = await browser.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        await page.wait_for_timeout(2_000)

        suggestions = await page.evaluate(
            """() => {
                const nodes = Array.from(document.querySelectorAll('a, button'));
                const values = [];
                for (const node of nodes) {
                    const text = (node.textContent || '').trim();
                    if (!text) continue;
                    const href = node.getAttribute('href') || '';
                    const cls = (node.className || '').toString().toLowerCase();
                    if (href.includes('/search?q=') || cls.includes('suggest')) {
                        values.push(text);
                    }
                }
                return values;
            }"""
        )
        suggestions = [str(x).strip() for x in suggestions if str(x).strip()][:max_results]

        body_text = await page.locator("body").inner_text()
        result_count = 0
        for line in body_text.splitlines():
            low = line.lower()
            if "results" in low:
                result_count = _extract_int(line)
                if result_count:
                    break

        await browser.close()

    return {
        "seed": seed,
        "keyword": seed,
        "suggestions": suggestions,
        "related_searches": [],
        "result_count": result_count,
        "source": "etsy_playwright",
        "source_type": "playwright",
        "url": url,
    }


def fetch_etsy_keywords_sync(seed: str, max_results: int = 200, *, headless: bool = True) -> dict[str, Any]:
    return asyncio.run(fetch_etsy_keywords(seed, max_results=max_results, headless=headless))
