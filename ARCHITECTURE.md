# ARCHITECTURE

## System shape

Autofinisher Factory is a layered, file-driven pipeline with explicit batch artifacts.

The system is organized around four operational domains:

1. **Discovery and scraping**
2. **Scoring and validation**
3. **Winner propagation and SKU production**
4. **Batch monitoring and dashboard consumption**

## Execution flow

1. `run_monetization_batch_fast.py` starts a batch.
2. `monetization_pipeline_fast.py` orchestrates Google, Etsy, and eBay signal collection.
3. `fms_engine.py` computes the canonical FMS score.
4. `winner_duplicator.py` writes validated niche snapshots and winner artifacts.
5. `batch_reference_monitor.py` computes batch KPI, history, and alerts.
6. `premium_sku_factory.py` builds publishable packets for approved winners.
7. `publish_packets/summary.json` is enriched with compact monitoring metadata.

## Artifact graph

### Validation artifacts

- `niche_engine/accepted/niche_package.json`
- `niche_engine/accepted/seed_statuses.json`
- `data/validated_niches/items/*.json`

### Winner artifacts

- `data/winners/*.json`
- `data/sku_tasks/*.json`

### Monitoring artifacts

- `data/batch_monitoring/reference_batch_summary.json`
- `data/batch_monitoring/reference_alerts.json`
- `data/batch_monitoring/batch_kpi_history.json`

### Publishing artifacts

- `ready_to_publish/*`
- `publish_packets/*`
- `publish_packets/summary.json`

## Layer boundaries

### Scraping layer

Responsibilities:

- Google candidate discovery
- Etsy shortlist generation
- eBay liquidity validation

Primary files:

- `google_niche_scraper.py`
- `etsy_mcp_scraper.py`
- `niche_profit_engine.py`

### FMS layer

Responsibilities:

- compute canonical `fms_score`
- compute `fms_components`
- keep scoring separate from alerting and publishing

Primary files:

- `fms_engine.py`
- `fms_reference.py`
- `monetization_pipeline_fast.py`

### Validation layer

Responsibilities:

- assign status/reason
- create validated snapshots
- create winner cards and sku tasks

Primary files:

- `winner_duplicator.py`
- `niche_engine/contracts/niche_win_card.schema.json`
- `niche_engine/contracts/fms_result.schema.json`

### Monitoring layer

Responsibilities:

- compute batch yield KPI
- compare batch quality to reference winner
- maintain rolling history
- emit alert JSON for dashboards and downstream agents

Primary files:

- `batch_reference_monitor.py`
- `SPEC_monitoring.md`
- `data/batch_monitoring/*`

## Design rules

- FMS decisions use canonical `fms_score` from `fms_engine.py`.
- `reference_ratios` are diagnostic, not gating.
- Monitoring is post-batch and does not change validation results.
- Publish summary contains only compact monitoring metadata and links.
- Detailed alert logic lives in monitoring artifacts, not in publish outputs.
