# AGENTS

## TL;DR

Agents in this project are file-oriented and contract-driven.

Read only the artifacts needed for the current task, preserve existing JSON field names, and treat batch artifacts as the primary runtime truth.

The repo now has **two connected agent loops**:

1. **validation loop** — discovery → FMS / Etsy / eBay decisioning → batch artifacts
2. **product loop** — intel packets → merged packet → SKU spec → build artifacts

## Fast start for a new agent

Read in this order:

1. `README.md`
2. `ARCHITECTURE.md`
3. `docs/PROJECT_NAVIGATION.md`
4. `data/intel_packets/reseller_finance_inventory_system/manifest.json`
5. `data/intel_packets/reseller_finance_inventory_system/final_merged_intel_packet.json`
6. `data/intel_packets/reseller_finance_inventory_system/sku_spec_v1.json`
7. `monetization_pipeline_fast.py`
8. `run_monetization_batch_fast.py`
9. `niche_engine/accepted/seed_statuses.json`
10. `publish_packets/summary.json`

## Agent map

### 1. Orchestrator

Primary entrypoints:

- `run_monetization_batch_fast.py`
- `autofinisher_orchestrator.py`

Responsibilities:

- start batch runs
- coordinate validation, monitoring, and packaging flow
- expose top-level batch outputs

Reads:

- `vertical_families.json`
- `niche_engine/accepted/niche_package.json`
- `data/batch_monitoring/*.json`
- `data/intel_packets/**/*.json`

Writes:

- `publish_packets/summary.json`

### 2. Discovery / scraper agent layer

Primary files:

- `google_niche_scraper.py`
- `etsy_mcp_scraper.py`
- `niche_profit_engine.py`
- `mcp/keyword_discovery_mcp.py`
- `keyword_engine/keyword_compiler.py`
- `keyword_engine/keyword_to_niche_candidates.py`

Responsibilities:

- collect Google/Etsy/eBay signals
- build keyword discovery runs
- compile keyword shortlists
- import keyword-derived seeds into the main pipeline

May write:

- `data/keyword_runs/<run_id>/*`
- `niche_engine/candidates/keyword_discovery_index.json`
- temporary/debug artifacts already established by current code

Must not own:

- final monitoring history
- merged product intel packet
- publish summary as source of truth

### 3. FMS evaluator

Primary files:

- `fms_engine.py`
- `fms_reference.py`
- `monetization_pipeline_fast.py`
- `fms_decision.py`

Responsibilities:

- compute canonical `fms_components`
- compute canonical `fms_score`
- classify niche quality via status/reason inputs to validation layer
- keep keyword discovery signal separate from canonical FMS scoring

Reads:

- Etsy metrics
- eBay metrics
- optional real performance
- reference winner config
- keyword-derived imported seeds

Writes:

- in-memory FMS fields passed downstream to batch artifacts

### 4. Validation / batch artifact agent

Primary files:

- `monetization_pipeline_fast.py`
- `winner_duplicator.py`

Responsibilities:

- write `niche_engine/accepted/seed_statuses.json`
- write `niche_engine/accepted/niche_package.json`
- preserve `reason_code`, `reason_detail`, FMS, Etsy/eBay diagnostics
- propagate accepted results into winner / task flow when applicable

Reads:

- FMS fields from pipeline
- niche metadata/intel

Writes:

- accepted batch snapshots
- validated niche snapshots
- winner cards
- SKU tasks

### 5. Alerting / monitoring agent

Primary file:

- `batch_reference_monitor.py`

Responsibilities:

- compute batch KPI
- compare winners/candidates to reference winner
- maintain rolling history
- emit batch-level alerts

Reads:

- `data/validated_niches/items/*.json`
- `niche_engine/accepted/seed_statuses.json`

Writes:

- `data/batch_monitoring/reference_batch_summary.json`
- `data/batch_monitoring/reference_alerts.json`
- `data/batch_monitoring/batch_kpi_history.json`

### 6. Product-intel / merge agent

Primary files:

- `data/intel_packets/reseller_finance_inventory_system/*.json`

Responsibilities:

- archive user / assistant packet variants
- compare variants
- produce merged review notes
- produce final merged packet
- keep external Etsy/YouTube claims clearly separated from batch-verified facts

Writes:

- `manifest.json`
- `merged_review_notes.json`
- `final_merged_intel_packet.json`
- `sku_spec_v1.json`

### 7. SKU / packet builder

Primary files:

- `premium_sku_factory.py`
- `artifact_builder.py`

Responsibilities:

- build publish-ready packet outputs
- generate listing-ready files under `ready_to_publish/`
- populate `publish_packets/*`

Reads:

- approved winners and accepted niche package outputs
- or synthetic bridge inputs when building an experimental SKU from `sku_spec_v1`

Writes:

- `ready_to_publish/*`
- `publish_packets/*`
- `publish_packets/summary.json`

## Modification rules for agents

Agents should only modify files they own or are explicitly allowed to enrich.

Safe enrichment targets:

- `publish_packets/summary.json` may be enriched by the orchestrator with monitoring metadata
- accepted / validated niche files may be updated by monitoring for recalculated fields
- intel packet artifacts may be extended by the product-intel flow

Agents should avoid:

- renaming stable JSON fields
- changing file locations without updating docs
- treating external listing/video claims as factual unless rechecked
- widening keyword discovery when a live candidate cluster already exists and the task is product packaging

## Current practical rule

- For **market truth**, trust batch artifacts first.
- For **product direction**, trust the merged intel packet and SKU spec.
- For **final validation**, trust live listing performance once a SKU is published.
