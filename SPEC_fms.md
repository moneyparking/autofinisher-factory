# SPEC_fms

## TL;DR for agents

FMS is the canonical niche scoring layer.

Use `fms_engine.py` as the source of truth for score computation.
Do not gate winners on legacy `ranking.monetization_score`.
Use `reference_ratios` only for diagnostics, comparison, and monitoring — not as a direct acceptance gate.

## Canonical FMS fields

Primary fields:

- `fms_components`
- `fms_score`
- `etsy_metrics`
- `ebay_metrics`
- `real_performance`
- `reference_ratios`
- `validation`

Canonical contract:

- `niche_engine/contracts/fms_result.schema.json`

## Inputs

FMS consumes:

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

## Output semantics

### `fms_score`

`fms_score` is the canonical score used by the fast pipeline for ranking and acceptance decisions.

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

Current default bands:

- `< 0.4` → `low`
- `0.4 <= x < 0.5` → `weak`
- `>= 0.5` → `healthy`

## Winner gate

Current fast-pipeline gate:

- `fms_score >= 42.0`
- `str_percent >= 15.0`
- `sold_count >= 20`

This gate is intentionally stricter on liquidity than on FMS alone.

## Validation statuses

Observed status families:

- `winner`
- `candidate`
- `low_etsy`
- `low_ebay`
- `low_fms`
- `network_failed`

For the canonical FMS schema, downstream agents should normalize to the semantic layer:

- winner
- candidate
- reject

## Official artifacts

Per-niche:

- `data/validated_niches/items/*.json`

Winner propagation:

- `data/winners/*.json`
- `data/sku_tasks/*.json`

## Example interpretation

A niche can have:

- high `fms_score`
- acceptable Etsy quality
- but extremely weak `sold_ratio`

In that case the correct interpretation is:

- strong theoretical interest
- weak liquidity
- likely `candidate` or `low_ebay`, not `winner`

## Agent rules

- Keep JSON field names stable.
- Treat `fms_engine.py` as canonical.
- Do not re-derive `reference_ratios` differently in different modules.
- Use `fms_reference.py` for benchmark comparison logic.
