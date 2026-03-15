# PROJECT_NAVIGATION

## Purpose

This document is the fast navigation map for agents working inside Autofinisher Factory.

Use it to find the current source of truth quickly without re-scanning the whole repository.

## Fastest reading order

1. `README.md`
2. `AGENTS.md`
3. `ARCHITECTURE.md`
4. `docs/PROJECT_NAVIGATION.md`
5. `data/intel_packets/reseller_finance_inventory_system/manifest.json`
6. `data/intel_packets/reseller_finance_inventory_system/final_merged_intel_packet.json`
7. `data/intel_packets/reseller_finance_inventory_system/sku_spec_v1.json`
8. `monetization_pipeline_fast.py`
9. `run_monetization_batch_fast.py`
10. `niche_engine/accepted/seed_statuses.json`
11. `publish_packets/summary.json`

## Current truth layers

### 1. Market validation truth

Use these first when the question is about what the system actually decided in the latest run:

- `niche_engine/accepted/seed_statuses.json`
- `niche_engine/accepted/niche_package.json`
- `publish_packets/summary.json`

Use `seed_statuses.json` for:

- `status`
- `decision_type`
- `reason_code`
- `reason_detail`
- `market_fms_score`
- `overall_fms_score`
- Etsy/eBay diagnostics

### 2. Keyword-discovery truth

Use these when the question is about discovery inputs and shortlist quality:

- `config/keyword_discovery.yaml`
- `data/keyword_runs/<run_id>/summary.json`
- `data/keyword_runs/<run_id>/money_shortlist.csv`
- `niche_engine/candidates/keyword_discovery_index.json`

Main code:

- `keyword_engine/keyword_compiler.py`
- `keyword_engine/keyword_to_niche_candidates.py`
- `mcp/keyword_discovery_mcp.py`
- `scripts/etsy_keyword_scraper_playwright.py`
- `scripts/google_keyword_scraper_playwright.py`

### 3. Product-intel truth

Use these when the task is product packaging or SKU design:

- `data/intel_packets/reseller_finance_inventory_system/manifest.json`
- `data/intel_packets/reseller_finance_inventory_system/merged_review_notes.json`
- `data/intel_packets/reseller_finance_inventory_system/final_merged_intel_packet.json`
- `data/intel_packets/reseller_finance_inventory_system/sku_spec_v1.json`

## Main operational entrypoints

### Batch validation

- `run_monetization_batch_fast.py`
- `batch_reference_monitor.py`

### Keyword-discovery runs

- `mcp/keyword_discovery_mcp.py`

### Build / packaging

- `premium_sku_factory.py`
- `artifact_builder.py`
- `winner_duplicator.py`

## Important env flags

### Keyword import

- `KEYWORD_DISCOVERY_IMPORT_ENABLED=1`
- `KEYWORD_DISCOVERY_ONLY=1`
- `KEYWORD_DISCOVERY_RUN_ID=<run_id>`
- `KEYWORD_DISCOVERY_MAX_CANDIDATES=<n>`
- `MAX_KEYWORD_DISCOVERY_SEED_WORDS=6`

## Current 2026 practical model

### Market loop

`Keyword Discovery or Base Verticals -> monetization_pipeline_fast.py -> seed_statuses / niche_package -> monitoring`

### Product loop

`intel packet variants -> merged_review_notes -> final_merged_intel_packet -> sku_spec_v1 -> build -> publish -> live metrics`

## Where to look depending on the task

### “Why did this seed fail?”

Read:

- `niche_engine/accepted/seed_statuses.json`

### “What is the current keyword shortlist?”

Read:

- `data/keyword_runs/<run_id>/money_shortlist.csv`
- `data/keyword_runs/<run_id>/summary.json`

### “Which product are we building now?”

Read:

- `data/intel_packets/reseller_finance_inventory_system/final_merged_intel_packet.json`
- `data/intel_packets/reseller_finance_inventory_system/sku_spec_v1.json`

### “Which files should I touch?”

- validation logic → `monetization_pipeline_fast.py`, `fms_engine.py`, `fms_decision.py`
- keyword discovery → `keyword_engine/*`, `mcp/keyword_discovery_mcp.py`, `config/keyword_discovery.yaml`
- product packaging docs/artifacts → `data/intel_packets/*`
- build artifacts → `ready_to_publish/*`, `publish_packets/*`

## Agent rule of thumb

- use batch artifacts for factual runtime truth
- use intel packet artifacts for product direction
- use live listing metrics for final commercial truth
- avoid widening keywords when a live candidate cluster already exists and the task is packaging/build
