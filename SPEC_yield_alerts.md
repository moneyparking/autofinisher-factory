# SPEC_yield_alerts

## TL;DR for agents

Yield and reference-relative quality are monitored at the batch level.

The monitoring layer is post-batch. It does not change validation outputs. It reads seed status and validation artifacts, computes batch KPI, maintains rolling history, and emits alert artifacts for dashboards and downstream agents.

The current 2026 repo state also requires yield interpretation for batches that are candidate-heavy but winner-light.

## Primary artifacts

Inputs:

- `niche_engine/accepted/seed_statuses.json`
- `niche_engine/accepted/niche_package.json`
- `data/validated_niches/items/*.json`

Outputs:

- `data/batch_monitoring/reference_batch_summary.json`
- `data/batch_monitoring/reference_alerts.json`
- `data/batch_monitoring/batch_kpi_history.json`

## Batch KPI

Current KPI set may include:

- `winner_yield`
- `winner_yield_raw`
- `winner_yield_reliable`
- `reliable_seed_count`
- `avg_fms_ratio_winners`
- `avg_str_ratio_winners`
- `avg_sold_ratio_winners`
- `median_fms_ratio_winners`
- `avg_fms_ratio_candidates`
- `avg_str_ratio_candidates`
- `avg_sold_ratio_candidates`
- `market_candidate_total`
- `market_accept_total`
- `market_reject_total`
- `data_uncertain_total`

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

### Candidate-heavy, winner-light batch

Interpretation:

- the system is finding live clusters
- packaging or offer-shape may now be the bottleneck
- build-first / live-validation may be a valid next step if product-intel is strong

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

The publish summary should contain a compact `monitoring` block with fields such as:

- summary path
- alerts path
- `batch_status`
- `processed_seeds`
- `total_seeds`
- `winner_yield`
- `winner_yield_raw`
- `winner_yield_reliable`
- `market_candidate_total`
- `market_accept_total`
- `market_reject_total`
- `data_uncertain_total`
- `alerts_count`
- `alerts_levels`

Detailed alert logic remains in `data/batch_monitoring/*`, not in `publish_packets/summary.json`.

## Agent rules

- keep monitoring post-batch
- do not mutate validated niche decisions from alerting logic
- keep field names identical across monitoring JSON, specs, and dashboard consumers
- add new alerts by extending the monitoring layer and documenting them here
- when profile/buildability fields exist, prefer language that distinguishes winner yield from buildable candidate yield
