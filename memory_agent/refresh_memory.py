#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
MEMORY_AGENT_DIR = BASE_DIR / "memory_agent"
MEMORY_DIR = MEMORY_AGENT_DIR / "memory"
ENTITIES_DIR = MEMORY_DIR / "entities"
TIMELINE_DIR = MEMORY_DIR / "timeline"
PREFERENCES_DIR = MEMORY_DIR / "preferences"
ARCHIVE_SPECS_DIR = MEMORY_DIR / "archive" / "specs"
PROJECT_FILE = MEMORY_DIR / "project.md"
STATUS_FILE = TIMELINE_DIR / "current_status.md"
TRIGGERS_FILE = PREFERENCES_DIR / "text_triggers.md"
LAST_REFRESH_FILE = MEMORY_DIR / "last_refresh.json"

NICHE_PACKAGE_PATH = BASE_DIR / "niche_engine" / "accepted" / "niche_package.json"
SEED_STATUS_PATH = BASE_DIR / "niche_engine" / "accepted" / "seed_statuses.json"
SUMMARY_PATH = BASE_DIR / "publish_packets" / "summary.json"
CSV_PATH = BASE_DIR / "ready_to_publish" / "etsy_mass_import.csv"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def ensure_dirs() -> None:
    for directory in [MEMORY_DIR, ENTITIES_DIR, TIMELINE_DIR, PREFERENCES_DIR, ARCHIVE_SPECS_DIR]:
        directory.mkdir(parents=True, exist_ok=True)


def build_project_md() -> str:
    niche_package = load_json(NICHE_PACKAGE_PATH) or {}
    seed_statuses = load_json(SEED_STATUS_PATH) or {}
    summary = load_json(SUMMARY_PATH) or {}

    accepted_count = int(niche_package.get("accepted_count") or len(niche_package.get("items", [])) or 0)
    built_count = int(summary.get("built_count") or 0)
    seed_count = int(seed_statuses.get("seed_count") or len(seed_statuses.get("items", [])) or 0)
    top_item = (niche_package.get("items") or [{}])[0] if accepted_count else {}

    top_niche = str(top_item.get("niche") or "n/a")
    ranking = top_item.get("ranking") or {}
    metrics = top_item.get("metrics") or {}

    csv_exists = CSV_PATH.exists()
    return f"""# Autofinisher Factory — Project Memory

## Project identity
- Project: Autofinisher Factory
- Purpose: monetization conveyor for digital products.
- Core flow: Google -> Etsy -> eBay -> FMS v2 -> SKU factory.
- Primary publishing targets: Etsy and Gumroad.

## Canonical architecture
1. **Google upper layer**
   - Module: `google_niche_scraper.py`
   - Purpose: cheap radar for niche families and semantic candidates.
2. **Etsy marketplace-fit layer**
   - Module: `etsy_mcp_scraper.py`
   - Purpose: marketplace validation, listing surface, digital-share signal, competitor surface.
3. **eBay liquidity validation**
   - Module: `niche_profit_engine.py`
   - Purpose: active/sold counts and sell-through signal.
4. **FMS v2 scoring**
   - Module: `monetization_scorer.py`
   - Purpose: monetization score and suggested price.
5. **SKU factory**
   - Module: `premium_sku_factory.py`
   - Purpose: publish-ready premium packets and export assets.

## Current operating mode
- Active pipeline: `monetization_pipeline_fast.py`
- Active batch entrypoint: `run_monetization_batch_fast.py`
- Current batch target: **15 approved niches**
- Current packet build limit: **15**
- Reason for reduced target: external scraper/network instability made larger runs unrealistic in current environment.

## Current fast-batch baseline
- `TARGET_COUNT = 15`
- `GOOGLE_MAX_PAGES_FAST = 1`
- `GOOGLE_REQUESTS_PER_SEED_MAX = 1`
- `MAX_GOOGLE_REQUESTS_PER_BATCH = 20`
- `ETSY_REQUESTS_PER_SEED_MAX = 1`
- `ETSY_MAX_LISTINGS_FAST = 24`
- `MAX_ETSY_REQUESTS_PER_BATCH = 40`
- `MAX_SHORTLIST_PER_SEED = 3`
- `MIN_MONETIZATION_SCORE = 42.0`
- `MIN_ACTIVE = 8`
- `MAX_ACTIVE = 5000`
- `SCRAPER_RETRIES = 2`
- `SCRAPER_BACKOFF = 1.0`
- `MAX_ETSY_INSPECT_PER_SEED = 0`
- `MAX_NETWORK_FAILURES_PER_SEED = 2`

## Transport / network baseline
- Google scraper timeout: `30s`
- Etsy scraper timeout: `30s`
- eBay scraper timeout: `30s`
- Retry model: initial attempt + 2 retries
- Retry backoff: approximately `2s`, `4s`
- Fast-mode Google policy: only `"{{seed}} etsy"`, page limit = 1, PAA disabled by default.
- Fast-mode Etsy policy: one `most_relevant` search URL, max 24 cards, no product-page inspect.

## Important files
- `monetization_pipeline_fast.py`
- `run_monetization_batch_fast.py`
- `premium_sku_factory.py`
- `google_niche_scraper.py`
- `etsy_mcp_scraper.py`
- `niche_profit_engine.py`
- `monetization_scorer.py`
- `review_intel.py`
- `competitor_intel.py`
- `performance_intel.py`
- `vertical_families.json`

## Important outputs
- Accepted niches: `niche_engine/accepted/niche_package.json`
- Seed statuses: `niche_engine/accepted/seed_statuses.json`
- Packet summary: `publish_packets/summary.json`
- Ready publish CSV: `ready_to_publish/etsy_mass_import.csv`

## Current observed outputs
- Accepted niches in latest batch: `{accepted_count}`
- Built packets in latest batch: `{built_count}`
- Seed statuses tracked: `{seed_count}`
- Ready publish CSV exists: `{str(csv_exists).lower()}`

## Top current result
- Top niche: `{top_niche}`
- Monetization score: `{ranking.get('monetization_score', 'n/a')}`
- Suggested price: `{top_item.get('suggested_price', 'n/a')}`
- STR: `{metrics.get('sell_through_rate', 'n/a')}`
- Active listings: `{metrics.get('active_listings', 'n/a')}`
- Sold listings: `{metrics.get('sold_listings', 'n/a')}`

## Commands
- Main fast batch:
  - `python3 /home/agent/autofinisher-factory/run_monetization_batch_fast.py`
- Bootstrap memory:
  - `python3 /home/agent/autofinisher-factory/memory_agent/bootstrap_memory.py`
- Refresh memory:
  - `python3 /home/agent/autofinisher-factory/memory_agent/refresh_memory.py`

## Known operational realities
- Primary instability source: external scraper/network layer, especially ScraperAPI timeouts.
- Current strategy is not to disable enrichment completely, but to keep it slim and bounded.
- Circuit-breaker logic treats repeated network failures per seed as acceptable and moves on.
- Goal is throughput and consistent shortlist completion, not maximal enrichment depth.

## Interpretation rule for future sessions
If memory-agent needs to brief the main agent quickly, it should prioritize:
1. current batch target = 15
2. active runner = `run_monetization_batch_fast.py`
3. architecture = Google -> Etsy -> eBay -> FMS v2 -> SKU factory
4. current bottleneck = scraper/network instability
5. current output counts from latest refresh
6. output files and exact command paths
"""


def build_status_md() -> str:
    niche_package = load_json(NICHE_PACKAGE_PATH) or {}
    summary = load_json(SUMMARY_PATH) or {}
    accepted_count = int(niche_package.get("accepted_count") or len(niche_package.get("items", [])) or 0)
    built_count = int(summary.get("built_count") or 0)
    top_item = (niche_package.get("items") or [{}])[0] if accepted_count else {}
    top_niche = str(top_item.get("niche") or "n/a")
    return f"""# Current Status

## Active state
- Fast pipeline is the current operating path.
- Batch target remains 15 approved niches.
- Slim-mode and budgeted external-request policy are active.
- Seed-level circuit breaker is active.

## Latest known refresh
- Refreshed at: `{now_iso()}`
- Approved niches in latest batch snapshot: `{accepted_count}`
- Built packets in latest batch snapshot: `{built_count}`
- Top niche in current memory snapshot: `{top_niche}`

## Text command workflow
- If user says **"обновить память проекта"**, run `refresh_memory.py`.
- If user says **"перезапустить память проекта"**, run `bootstrap_memory.py`, then `refresh_memory.py`.
- If user says **"перезаписать память проекта"**, rebuild memory files from current repository state using `refresh_memory.py`.
"""


def build_last_refresh_payload() -> dict[str, Any]:
    niche_package = load_json(NICHE_PACKAGE_PATH) or {}
    summary = load_json(SUMMARY_PATH) or {}
    seed_statuses = load_json(SEED_STATUS_PATH) or {}
    return {
        "refreshed_at": now_iso(),
        "accepted_count": int(niche_package.get("accepted_count") or len(niche_package.get("items", [])) or 0),
        "built_count": int(summary.get("built_count") or 0),
        "seed_count": int(seed_statuses.get("seed_count") or len(seed_statuses.get("items", [])) or 0),
        "csv_exists": CSV_PATH.exists(),
    }


def main() -> None:
    ensure_dirs()
    PROJECT_FILE.write_text(build_project_md(), encoding="utf-8")
    STATUS_FILE.write_text(build_status_md(), encoding="utf-8")
    LAST_REFRESH_FILE.write_text(json.dumps(build_last_refresh_payload(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "refreshed_at": now_iso(),
        "project_file": str(PROJECT_FILE),
        "status_file": str(STATUS_FILE),
        "last_refresh_file": str(LAST_REFRESH_FILE),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
