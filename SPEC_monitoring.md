# SPEC_monitoring

## TL;DR for agents

Post-batch monitoring is an official pipeline step.

It reads the current batch context from seed status and validation artifacts, computes batch-level KPI for yield and quality, stores rolling history, emits alerts, and exposes a compact monitoring block inside `publish_packets/summary.json`.

Monitoring is now expected to track not only canonical winners, but also candidate quality and build-oriented batch behavior.

## Monitoring step

### Inputs

Primary inputs:

- `niche_engine/accepted/niche_package.json`
- `niche_engine/accepted/seed_statuses.json`
- `data/validated_niches/items/*.json`

Required runtime values:

- `batch_id`
- `processed_seeds`
- `total_seeds`

### Outputs

The monitoring step produces three artifacts:

- `data/batch_monitoring/reference_batch_summary.json`
- `data/batch_monitoring/reference_alerts.json`
- append/update in `data/batch_monitoring/batch_kpi_history.json`

### Pipeline placement

Monitoring runs after niche validation and before downstream human/dashboard consumption.

The batch runner enriches `publish_packets/summary.json` with a compact `monitoring` block that points to the deeper monitoring artifacts.

## KPI model

### Core batch KPI

The monitoring step may compute and/or expose:

- `winner_yield`
- `winner_yield_raw`
- `winner_yield_reliable`
- `reliable_seed_count`
- `winner_count`
- `candidate_count`
- `rejected_count`
- `market_accept_total`
- `market_candidate_total`
- `market_reject_total`
- `data_uncertain_total`
- `network_retry_events_total`
- `network_retry_seeds`

### Reference-relative KPI

Where reference comparison is available, the monitoring layer may also compute:

- `avg_fms_ratio_winners`
- `avg_str_ratio_winners`
- `avg_sold_ratio_winners`
- `avg_fms_ratio_candidates`
- `avg_str_ratio_candidates`
- `avg_sold_ratio_candidates`
- `median_fms_ratio_winners`

`*_ratio_*` values are relative to the current reference winner defined in `fms_reference.py`.

### Current 2026 interpretation

Monitoring should now distinguish among:

- **winners**
- **buildable candidates**
- **soft-profile / partial-market candidates**
- **data-uncertain cases**

This matters because the current repo supports experimental build flow from strong candidate clusters even when canonical winner count is zero.

## Profile-aware monitoring

Where profile fields are available in current outputs, monitoring should be able to segment by:

- `profile_id`
- `channel_validation_profile`
- candidate vs winner vs soft-profile candidate families

Useful profile-aware KPIs include:

- count of niches with `overall_fms_score >= X` by profile
- count of niches with `buildability_score >= Y` by profile
- count of buildable candidates with no winner accept

## Alert model

### Static thresholds

Examples of static thresholds still used by the current layer:

- warning yield floor
- critical yield floor
- winner FMS ratio warning floor
- winner FMS ratio critical floor

### Dynamic thresholds

The monitoring layer keeps rolling history across recent batches and computes dynamic warning/critical thresholds using rolling mean/std logic.

Current implementation keeps history in:

- `data/batch_monitoring/batch_kpi_history.json`

### Alert files

`reference_alerts.json` contains:

- batch id
- batch-level KPI snapshot
- current thresholds
- alerts array with `level`, `code`, `message`

Examples of alert families in the current model:

- low yield
- low reference quality
- weak candidate sold-ratio
- batch drift vs reference
- candidate-heavy / winner-light behavior

## Data contracts

### `reference_batch_summary.json`

Top-level fields commonly include:

- `generated_at`
- `batch_id`
- `kpi`
- `history_path`
- `alerts_path`

### `reference_alerts.json`

Top-level fields commonly include:

- `batch_id`
- `generated_at`
- `kpi`
- `thresholds`
- `alerts`

### `batch_kpi_history.json`

Top-level fields commonly include:

- `updated_at`
- `window`
- `count`
- `items`

Each history item contains batch-level KPI aggregates for one batch.

## Link into publish summary

`publish_packets/summary.json` is enriched with a compact block such as:

- `monitoring.reference_summary_path`
- `monitoring.reference_alerts_path`
- `monitoring.batch_status`
- `monitoring.processed_seeds`
- `monitoring.total_seeds`
- `monitoring.winner_yield`
- `monitoring.winner_yield_raw`
- `monitoring.winner_yield_reliable`
- `monitoring.market_candidate_total`
- `monitoring.market_accept_total`
- `monitoring.market_reject_total`
- `monitoring.data_uncertain_total`
- `monitoring.alerts_count`
- `monitoring.alerts_levels`

This block is intentionally compact. Agents and dashboards should use it as a fast navigation layer and read the detailed monitoring artifacts when deeper analysis is needed.

## Current practical rule

A batch with:

- `0 winners`
- high `candidate_count`
- good cluster concentration
- strong buildability/product-intel direction

should not automatically be interpreted as a total failure.

In the current repo, that pattern may instead indicate:

- candidate cluster exists
- packaging / offer shape is now the main blocker
- build-first / live-validation can be the correct next step

## Operational notes for agents

When adding new KPI or alerts:

1. update `batch_reference_monitor.py`
2. keep field names stable across code, JSON, and specs
3. expose only compact pointers/KPI in `publish_packets/summary.json`
4. keep detailed alert logic in monitoring artifacts, not in the publish summary itself
5. prefer profile-aware monitoring terminology when current outputs expose profile fields
