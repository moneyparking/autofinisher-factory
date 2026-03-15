from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path("/home/agent/autofinisher-factory")
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from etsy_mcp_scraper import scan_keywords as etsy_scan_keywords
from google_niche_scraper import scan_google_niches
from keyword_engine.keyword_compiler import compile_keywords
from keyword_engine.keyword_to_niche_candidates import to_niche_candidates

RAW_BASE = BASE_DIR / "data" / "keyword_raw"


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("keyword_run_%Y%m%d_%H%M%S")


def _normalize_seed(seed: str) -> str:
    return " ".join(str(seed or "").strip().split())


def _safe_filename(seed: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in seed.lower().replace(" ", "_"))
    return safe[:180] or "seed"


def _extract_etsy_payload(response: dict[str, Any], seed: str) -> dict[str, Any]:
    result = (response.get("results") or [{}])[0]
    suggestions = [str(item.get("title") or "").strip() for item in (result.get("listings") or []) if str(item.get("title") or "").strip()]
    return {
        "seed": seed,
        "keyword": seed,
        "suggestions": suggestions,
        "related_searches": [],
        "niche_candidates": [],
        "result_count": (result.get("search_metadata") or {}).get("total_results") or 0,
        "source": "etsy",
        "source_type": "existing_scraper",
    }


def _extract_google_payload(response: dict[str, Any], seed: str) -> dict[str, Any]:
    result = (response.get("results") or [{}])[0]
    suggestions = list(result.get("related_searches") or [])
    niche_candidates = list(result.get("niche_candidates") or [])
    result_count = ((result.get("serp_metadata") or {}).get("total_etsy_results") or 0) * 100
    return {
        "seed": seed,
        "keyword": seed,
        "suggestions": suggestions,
        "related_searches": suggestions,
        "niche_candidates": niche_candidates,
        "result_count": result_count,
        "source": "google",
        "source_type": "existing_scraper",
    }


async def run_etsy(seed_list: list[str], run_id: str, *, use_playwright: bool = False) -> dict[str, Any]:
    raw_dir = RAW_BASE / "etsy" / run_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    if use_playwright:
        from scripts.etsy_keyword_scraper_playwright import fetch_etsy_keywords

        for seed in seed_list:
            data = await fetch_etsy_keywords(seed)
            (raw_dir / f"{_safe_filename(seed)}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        response = etsy_scan_keywords(seed_list, max_listings_per_keyword=24)
        for result in response.get("results", []):
            seed = _normalize_seed(result.get("keyword") or "")
            if not seed:
                continue
            data = _extract_etsy_payload({"results": [result]}, seed)
            (raw_dir / f"{_safe_filename(seed)}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "done", "run_id": run_id, "source": "etsy", "raw_dir": str(raw_dir)}


async def run_google(seed_list: list[str], run_id: str, *, use_playwright: bool = False) -> dict[str, Any]:
    raw_dir = RAW_BASE / "google" / run_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    if use_playwright:
        from scripts.google_keyword_scraper_playwright import fetch_google_keywords

        for seed in seed_list:
            data = await fetch_google_keywords(seed)
            (raw_dir / f"{_safe_filename(seed)}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        response = scan_google_niches(seed_list, country="US", language="en", max_pages=1)
        for result in response.get("results", []):
            seed = _normalize_seed(result.get("query") or "")
            if not seed:
                continue
            data = _extract_google_payload({"results": [result]}, seed)
            (raw_dir / f"{_safe_filename(seed)}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "done", "run_id": run_id, "source": "google", "raw_dir": str(raw_dir)}


async def main_async(args: argparse.Namespace) -> dict[str, Any]:
    run_id = args.run_id or utc_run_id()
    if args.compile_only:
        raw_dirs = []
        for source in ("etsy", "google"):
            path = RAW_BASE / source / run_id
            if path.exists():
                raw_dirs.append(path)
        if not raw_dirs:
            raise SystemExit(f"No raw discovery directories found for run_id={run_id}")
        compile_result = compile_keywords(raw_dirs, run_id, profile=args.profile)
        bridge_result = to_niche_candidates(run_id)
        payload = {"status": "done", "run_id": run_id, "compile_result": compile_result, "bridge_result": bridge_result}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return payload

    seeds = [_normalize_seed(seed) for seed in args.seeds if _normalize_seed(seed)]
    if not seeds:
        raise SystemExit("No seeds provided.")

    use_playwright = args.use_playwright or os.getenv("PLAYWRIGHT_FALLBACK", "").strip().lower() in {"1", "true", "yes", "on"}
    raw_dirs: list[Path] = []
    if args.run_etsy:
        result = await run_etsy(seeds, run_id, use_playwright=use_playwright)
        raw_dirs.append(Path(result["raw_dir"]))
    if args.run_google:
        result = await run_google(seeds, run_id, use_playwright=use_playwright)
        raw_dirs.append(Path(result["raw_dir"]))
    if not raw_dirs:
        raise SystemExit("Select at least one source: --run-etsy and/or --run-google")

    payload = {"status": "done", "run_id": run_id, "raw_dirs": [str(p) for p in raw_dirs], "use_playwright": use_playwright}
    if args.compile:
        compile_result = compile_keywords(raw_dirs, run_id, profile=args.profile)
        bridge_result = to_niche_candidates(run_id)
        payload["compile_result"] = compile_result
        payload["bridge_result"] = bridge_result
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Keyword Discovery MCP runner")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--profile", default="default")
    parser.add_argument("--run-etsy", action="store_true")
    parser.add_argument("--run-google", action="store_true")
    parser.add_argument("--use-playwright", action="store_true")
    parser.add_argument("--compile", action="store_true")
    parser.add_argument("--compile-only", action="store_true")
    parser.add_argument("--seeds", nargs="*", default=[])
    return parser


if __name__ == "__main__":
    asyncio.run(main_async(build_parser().parse_args()))
