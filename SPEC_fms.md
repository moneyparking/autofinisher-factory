# SPEC_fms

## TL;DR for agents

FMS is the canonical market-scoring layer.

Use `fms_engine.py` as the source of truth for score computation.
Do not gate winners on legacy `ranking.monetization_score`.
Do not let keyword-discovery or YouTube-derived signals replace market validation.
Use `reference_ratios` only for diagnostics, comparison, and monitoring — not as a direct acceptance gate.

## 2026 scoring model

The project now distinguishes between two related score layers:

### 1. `market_fms_score`

The pure market-facing score based on Etsy/eBay/market inputs.
This is the cleanest expression of market signal quality.

### 2. `overall_fms_score`

The synced score used by the pipeline when profile-aware uplift logic is applied.
This may incorporate bounded external hypothesis support such as:

- YouTube-derived hypothesis strength
- profile-aware sync logic
- other limited non-market uplifts allowed by the current profile

Rule:

- external signals may **uplift** the final score
- external signals may **not replace** weak market proof

## Canonical FMS fields

Primary fields observed in the current repo state:

- `fms_components`
- `market_fms_score`
- `overall_fms_score`
- `etsy_metrics`
- `ebay_metrics`
- `reference_ratios`
- `validation`
- `fms_sync`

Common sync-related fields in current 2026 artifacts/specs:

- `youtube_hypothesis_score`
- `youtube_uplift`
- `channel_validation_profile`
- `buildability_score`

Canonical contract:

- `niche_engine/contracts/fms_result.schema.json`

## Inputs

FMS consumes market inputs such as:

- Etsy metrics
  - `total_results`
  - `digital_share`
  - `avg_price`
  - `avg_reviews_top`
- eBay metrics
  - `str_percent`
  - `active_count`
  - `sold_count`
- optional real performance metrics

The synced FMS layer may additionally consume bounded hypothesis inputs, such as:

- `youtube_hypothesis_intel`
- profile-aware sync/uplift configuration
- buildability profile information

## Output semantics

### `market_fms_score`

`market_fms_score` is the clean market validation score.
Use it when discussing whether market proof itself is strong or weak.

### `overall_fms_score`

`overall_fms_score` is the synced score used by the fast pipeline when profile-aware uplift rules apply.
Use it when discussing buildability and final candidate/winner behavior inside the current pipeline.

### `channel_validation_profile`

Profiles allow the system to interpret similar niches differently depending on channel mix and expected evidence quality.

Examples of current profile semantics:

| profile_id | primary | secondary | eBay policy | uplift style |
|---|---|---|---|---|
| `general_digital_template` | Etsy/eBay | Google/Gumroad | normal | conservative |
| `etsy_seller_b2b_tool` | Etsy | Gumroad/Google | soft-signal | more tolerant |

The exact code path remains canonical in `monetization_pipeline_fast.py` and related decision modules.

### `reference_ratios`

`reference_ratios` compare a niche to the current reference winner.

Fields:

- `fms_ratio`
- `str_ratio`
- `sold_ratio`

These fields are diagnostic.
They do not change acceptance gates directly.

### `etsy_quality_band`

Derived from `digital_share`.

Values:

- `low`
- `weak`
- `healthy`
- `unknown`

## Winner and candidate gates

Current fast-pipeline winner gate remains stricter on liquidity than on FMS alone.
Observed baseline gate shape:

- `fms_score >= 42.0`
- `str_percent >= 15.0`
- `sold_count >= 20`

The current repo state also supports profile-aware candidate/build behavior, including candidate builds for fast-utility lines in some cases.

Important distinction:

- **winner** = strong enough for canonical accept path
- **buildable candidate** = not a winner, but still worth packaging/building under the current product logic

## Validation statuses and reasons

Observed semantic families in the current repo state:

- `winner`
- `candidate`
- `reject`
- `network_failed`
- `data_uncertain`

Observed reason-code style includes examples such as:

- `market_candidate_low_active`
- `market_candidate_low_sold`
- `market_candidate_low_str`
- `market_reject_weak_etsy`
- `data_uncertain_multi_source_partial`

Agents should prefer `reason_code` / `reason_detail` in `seed_statuses.json` over older coarse status families.

## Official artifacts

Batch truth:

- `niche_engine/accepted/seed_statuses.json`
- `niche_engine/accepted/niche_package.json`

Per-niche / downstream truth:

- `data/validated_niches/items/*.json`
- `data/winners/*.json`
- `data/sku_tasks/*.json`

## Example interpretation

A niche can have:

- acceptable or strong `overall_fms_score`
- but weak `active_count` or `sold_count`
- and therefore remain `candidate`, not `winner`

In that case the correct interpretation is:

- the cluster may be alive
- the market may still be under-proven for winner gates
- the next step may be better packaging / build / live validation rather than wider keyword discovery

## Agent rules

- Keep JSON field names stable.
- Treat `fms_engine.py` plus current decision logic as canonical.
- Do not re-derive `reference_ratios` differently in different modules.
- Do not treat YouTube/keyword signals as a replacement for market proof.
- Prefer `overall_fms_score` for current pipeline behavior and `market_fms_score` for market-purity analysis.
