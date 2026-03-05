# Autofinisher Factory — Project Memory

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
- Fast-mode Google policy: only `"{seed} etsy"`, page limit = 1, PAA disabled by default.
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
- Accepted niches in latest batch: `1`
- Built packets in latest batch: `1`
- Seed statuses tracked: `2`
- Ready publish CSV exists: `true`

## Top current result
- Top niche: `adhd cleaning checklist`
- Monetization score: `46.11`
- Suggested price: `6.83`
- STR: `34.66`
- Active listings: `176`
- Sold listings: `61`

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
