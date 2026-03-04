# SPEC_monitoring

## TL;DR for agents

Post-batch monitoring is an official pipeline step.

It reads the current batch context from validated niche outputs and seed status artifacts, computes batch-level KPI for yield and reference-relative quality, stores rolling history, emits alerts, and exposes a compact monitoring block that is attached to `publish_packets/summary.json`.

Agents should treat the files listed below as the source of truth for batch-level monitoring.

## Monitoring step

### Inputs

Primary inputs:

- `niche_engine/accepted/niche_package.json`
- `niche_engine/accepted/seed_statuses.json`
- `data/validated_niches/items/*.json`

Required runtime values:

- `batch_id`
- `seeds_total`

### Outputs

The monitoring step produces three artifacts:

- `data/batch_monitoring/reference_batch_summary.json`
- `data/batch_monitoring/reference_alerts.json`
- append/update in `data/batch_monitoring/batch_kpi_history.json`

### Pipeline placement

Monitoring runs after niche validation and before downstream human/dashboard consumption.

The batch runner enriches `publish_packets/summary.json` with a compact `monitoring` block that points to the deeper monitoring artifacts.

## KPI model

### Batch KPI

The monitoring step computes:

- `winner_yield = winners_total / seeds_total`
- `avg_fms_ratio_winners`
- `avg_str_ratio_winners`
- `avg_sold_ratio_winners`
- `avg_fms_ratio_candidates`
- `avg_str_ratio_candidates`
- `avg_sold_ratio_candidates`
- `median_fms_ratio_winners`

### Reference-relative meaning

`*_ratio_*` values are relative to the current reference winner defined in `fms_reference.py`.

Example interpretation:

- `avg_fms_ratio_winners = 1.0` means winners match the current reference batch baseline.
- `avg_sold_ratio_candidates = 0.03` means candidates are far weaker than the reference by sold-liquidity.

## Alert model

### Static thresholds

Current static thresholds:

- warning yield floor: `0.18`
- critical yield floor: `0.10`
- warning winner FMS ratio floor: `0.80`
- critical winner FMS ratio floor: `0.60`

### Dynamic thresholds

The monitoring layer keeps rolling history across the latest batches and computes dynamic warning/critical thresholds using rolling mean/std logic.

Current implementation keeps history in:

- `data/batch_monitoring/batch_kpi_history.json`

### Alert files

`reference_alerts.json` contains:

- batch id
- batch-level KPI snapshot
- current thresholds
- alerts array with `level`, `code`, `message`

Example alert codes:

- `LOW_YIELD_GOOD_REFERENCE`
- `LOW_YIELD_LOW_REFERENCE`
- `NORMAL_YIELD_LOW_REFERENCE`
- `CANDIDATES_SOLD_RATIO_WEAK`

## Data contracts

### `reference_batch_summary.json`

Top-level fields:

- `generated_at`
- `batch_id`
- `kpi`
- `history_path`
- `alerts_path`

### `reference_alerts.json`

Top-level fields:

- `batch_id`
- `generated_at`
- `kpi`
- `thresholds`
- `alerts`

### `batch_kpi_history.json`

Top-level fields:

- `updated_at`
- `window`
- `count`
- `items`

Each history item contains batch-level KPI aggregates for one batch.

## Link into publish summary

`publish_packets/summary.json` is enriched with a compact block:

- `monitoring.reference_summary_path`
- `monitoring.reference_alerts_path`
- `monitoring.winner_yield`
- `monitoring.avg_fms_ratio_winners`
- `monitoring.avg_sold_ratio_winners`
- `monitoring.alerts_count`
- `monitoring.alerts_levels`

This block is intentionally compact. Agents and dashboards should use it as the fast navigation layer and read the detailed monitoring artifacts when deeper analysis is needed.

## Current real batch example

Current validated example batch:

- `seeds_total = 2`
- `winners_total = 1`
- `candidates_total = 1`
- `winner_yield = 0.5`
- `avg_fms_ratio_winners = 1.0`
- `avg_sold_ratio_winners = 1.0`
- `avg_fms_ratio_candidates = 0.9104`
- `avg_sold_ratio_candidates = 0.0328`

Observed alert:

- `CANDIDATES_SOLD_RATIO_WEAK`
- level: `critical`

## Operational notes for agents

When adding new KPI or alerts:

1. update `batch_reference_monitor.py`
2. keep field names stable across code, JSON, and specs
3. expose only compact pointers/KPI in `publish_packets/summary.json`
4. keep detailed alert logic in monitoring artifacts, not in the publish summary itself
