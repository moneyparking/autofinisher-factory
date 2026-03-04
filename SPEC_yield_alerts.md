# SPEC_yield_alerts

## TL;DR for agents

Yield and reference-relative quality are monitored at the batch level.

The monitoring layer is post-batch. It does not change validation outputs. It reads validated niche snapshots, computes batch KPI, maintains rolling history, and emits alert artifacts for dashboards and downstream agents.

## Primary artifacts

Inputs:

- `niche_engine/accepted/seed_statuses.json`
- `data/validated_niches/items/*.json`

Outputs:

- `data/batch_monitoring/reference_batch_summary.json`
- `data/batch_monitoring/reference_alerts.json`
- `data/batch_monitoring/batch_kpi_history.json`

## Batch KPI

Current KPI set:

- `winner_yield`
- `avg_fms_ratio_winners`
- `avg_str_ratio_winners`
- `avg_sold_ratio_winners`
- `median_fms_ratio_winners`
- `avg_fms_ratio_candidates`
- `avg_str_ratio_candidates`
- `avg_sold_ratio_candidates`

## History model

Rolling history is stored in `batch_kpi_history.json`.

Each history item contains one batch-level KPI snapshot. The monitoring layer keeps only the latest rolling window of batches.

## Alert logic

### Static thresholds

Examples used by the current layer:

- yield warning floor
- yield critical floor
- winner FMS ratio warning floor
- winner FMS ratio critical floor

### Dynamic thresholds

Dynamic thresholds are computed from rolling history using mean/std logic.

The monitoring layer stores:

- dynamic warning threshold
- dynamic critical threshold
- historical mean
- historical std

## Combined alert semantics

### Low yield, good reference quality

Interpretation:

- not enough winners
- winners that do appear are still near benchmark quality
- likely seed generation or source coverage issue

### Normal yield, low reference quality

Interpretation:

- enough winners are being produced
- but their quality is drifting below benchmark
- likely gate relaxation or benchmark drift

### Low yield, low reference quality

Interpretation:

- few winners
- and they are below benchmark
- severe batch health problem

### Candidate sold-ratio weakness

Interpretation:

- candidates remain far below winner liquidity
- useful for spotting systematic low-conviction candidate generation

## Alert artifact contract

`reference_alerts.json` includes:

- `batch_id`
- `generated_at`
- `kpi`
- `thresholds`
- `alerts`

Each alert contains:

- `level`
- `code`
- `message`

## Link into publish summary

The publish summary should contain a compact `monitoring` block with:

- summary path
- alerts path
- `winner_yield`
- `avg_fms_ratio_winners`
- `avg_sold_ratio_winners`
- `alerts_count`
- `alerts_levels`

Detailed alert logic remains in `data/batch_monitoring/*`, not in `publish_packets/summary.json`.

## Agent rules

- keep monitoring post-batch
- do not mutate validated niche decisions from alerting logic
- keep field names identical across monitoring JSON, specs, and dashboard consumers
- add new alerts by extending the monitoring layer and documenting them here
