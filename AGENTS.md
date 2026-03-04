# AGENTS

## TL;DR

Agents in this project are file-oriented and contract-driven.

Each agent should read only the artifacts it needs, modify only its owned outputs, and preserve JSON field names exactly as specified by contracts and existing artifacts.

## Agent map

### 1. Orchestrator

Primary entrypoints:

- `run_monetization_batch_fast.py`
- `autofinisher_orchestrator.py`

Responsibilities:

- start batch runs
- coordinate validation, monitoring, and SKU production
- expose top-level batch outputs

Reads:

- `vertical_families.json`
- `niche_engine/accepted/niche_package.json`
- `data/batch_monitoring/*.json`

Writes:

- `publish_packets/summary.json`

### 2. Scraper agent layer

Primary files:

- `google_niche_scraper.py`
- `etsy_mcp_scraper.py`
- `niche_profit_engine.py`

Responsibilities:

- collect Google/Etsy/eBay signals
- return structured data to the fast pipeline

May write:

- temporary/debug artifacts only when already established by current code

Must not own:

- validated snapshots
- winner tasks
- publish summary

### 3. FMS evaluator

Primary files:

- `fms_engine.py`
- `fms_reference.py`
- `monetization_pipeline_fast.py`

Responsibilities:

- compute canonical `fms_components`
- compute canonical `fms_score`
- classify niche quality via status/reason inputs to validation layer

Reads:

- Etsy metrics
- eBay metrics
- optional real performance
- reference winner config

Writes:

- in-memory FMS fields passed to validation layer

### 4. Validation / winner-flow agent

Primary file:

- `winner_duplicator.py`

Responsibilities:

- write `data/validated_niches/items/*.json`
- write `data/winners/*.json`
- write `data/sku_tasks/*.json`
- preserve links between validated, winner, and task artifacts

Reads:

- FMS fields from pipeline
- niche metadata/intel

Writes:

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

### 6. SKU / packet builder

Primary file:

- `premium_sku_factory.py`

Responsibilities:

- build publish-ready packet outputs
- populate `publish_packets/summary.json`
- generate listing-ready files under `ready_to_publish/`

Reads:

- approved winners and niche package outputs

Writes:

- `ready_to_publish/*`
- `publish_packets/*`
- `publish_packets/summary.json`

## Modification rules for agents

Agents should only modify files they own or are explicitly allowed to enrich.

Safe enrichment targets:

- `publish_packets/summary.json` may be enriched by the orchestrator with monitoring metadata
- validated niche files may be updated by the monitoring layer for recalculated fields

Agents should avoid:

- renaming stable JSON fields
- changing file locations without updating specs and contracts
- introducing new top-level outputs without documenting them in the thin-spec set
