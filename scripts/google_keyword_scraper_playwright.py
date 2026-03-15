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


async def fetch_google_keywords(seed: str, max_results: int = 150, *, headless: bool = True) -> dict[str, Any]:
    try:
        from playwright.async_api import async_playwright
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("Playwright is not installed. Run 'pip install playwright' and 'playwright install chromium'.") from exc

    url = f"https://www.google.com/search?q={quote_plus(seed)}"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        page = await browser.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        await page.wait_for_timeout(2_000)

        try:
            await page.locator('button:has-text("Accept all")').click(timeout=2_000)
        except Exception:
            pass

        result_text = ""
        try:
            result_text = await page.locator("#result-stats").first.inner_text(timeout=3_000)
        except Exception:
            pass
        result_count = _extract_int(result_text)

        related_queries = await page.evaluate(
            """() => {
                const nodes = Array.from(document.querySelectorAll('a, span, div'));
                const out = [];
                for (const node of nodes) {
                    const text = (node.textContent || '').trim();
                    if (!text) continue;
                    const cls = (node.className || '').toString().toLowerCase();
                    if (cls.includes('s75csd') || cls.includes('related') || cls.includes('b2rnsc')) {
                        out.push(text);
                    }
                }
                return out;
            }"""
        )
        related_queries = [str(x).strip() for x in related_queries if str(x).strip()][:max_results]

        await browser.close()

    return {
        "seed": seed,
        "keyword": seed,
        "suggestions": related_queries,
        "related_searches": related_queries,
        "result_count": result_count,
        "source": "google_playwright",
        "source_type": "playwright",
        "url": url,
    }


def fetch_google_keywords_sync(seed: str, max_results: int = 150, *, headless: bool = True) -> dict[str, Any]:
    return asyncio.run(fetch_google_keywords(seed, max_results=max_results, headless=headless))
