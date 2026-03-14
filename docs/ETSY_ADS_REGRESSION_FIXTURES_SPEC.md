# Etsy Ads Regression Fixtures Spec

## Goal

This spec defines the minimal regression fixture scope for the Autofinisher 2.0 / Wedge-First Architecture Etsy Ads cluster.

The objective is to freeze the current winning baseline and detect product regressions without making the suite brittle to harmless prompt, ordering, or copy changes.

The fixture layer protects these contracts:

1. Quality gate remains green.
2. Domain stays in `etsy_ads` rather than collapsing into generic Etsy.
3. Parent/sub-wedge expansion remains present.
4. Evidence quotes remain compact.
5. `digital_bundle_spec.json` exists and stays structurally valid.

## Design principles

### Golden what matters, not everything

Fixtures must validate contracts, not full raw pipeline payloads.

Do not freeze entire `validated_ideas.json` or full `digital_bundle_spec.json` payloads as exact snapshots. Those files are too sensitive to safe copy, ordering, or packaging improvements.

### Three fixture layers

- **Hard-golden**: strict exact or enum checks.
- **Threshold-golden**: minimum floors and non-degradation checks.
- **Soft-observability**: useful reporting fields that should not fail the suite.

## Source artifacts

Per-video fixture manifests are derived from:

- `youtube_output/<video_id>/quality_gate.json`
- `wedge_outputs/<video_id>/parent_wedge.json`
- `wedge_outputs/<video_id>/sub_wedges.json`
- `youtube_output/<video_id>/validated_ideas.json`
- `youtube_output/<video_id>/digital_bundle_spec.json`

If `digital_bundle_spec.json` is missing but `validated_ideas.json` exists, the fixture builder is allowed to synthesize the spec using `build_digital_bundle_specs(...)` and write it to the canonical output path.

## Canonical Etsy Ads catalog

Allowed normalized Etsy Ads sub-wedges:

- `etsy_ads_profitability_system`
- `etsy_break_even_roas_calculator`
- `etsy_ads_testing_tracker`
- `etsy_ads_margin_guardrail_toolkit`
- `etsy_listing_level_ad_decision_system`

Comparisons should use normalized slugs, not literal human-readable text.

## Etsy Ads v1 product contract note

### English

For Etsy Ads wedge-first bundles, a v1-green output requires more than profitability/ROAS analysis.
The minimum v1 product contract is met only when the pipeline extracts at least one operational decision-layer sub-wedge (for example, listing-level pause/scale logic, winner/loser handling, or testing-driven ad decisions) that can support a stronger actionable bundle.

Short version:
Profitability and ROAS alone are not sufficient for a v1-green Etsy Ads bundle.
A v1 pass requires at least one operational decision-system wedge that produces a materially stronger workflow-level offer.

### Русская версия

Для Etsy Ads v1-зелёный результат требует не только аналитических wedge’ов уровня profitability/ROAS, но и как минимум одного operational sub-wedge’а уровня decision workflow.
Если из транскрипта не извлекается отдельный listing-level / pause-scale / winner-loser decision layer, такой кейс считается продуктово неполным и остаётся v1_fail.

Коротко:
Profitability/ROAS без decision-layer = v1_fail.
=======>>>>>>> REPLACE
<<<<<<< SEARCH
Threshold-golden:

- `distinct_sub_wedge_count >= 3`
- all normalized sub-wedge ids remain inside the canonical Etsy Ads catalog
- at least one sub-wedge must be transcript-native (`origin = sub_wedge_from_transcript`)
- `quote_char_count <= 280`
- `quote_word_count <= 40`
=======
Threshold-golden:

- `distinct_sub_wedge_count >= 3`
- all normalized sub-wedge ids remain inside the canonical Etsy Ads catalog
- at least one sub-wedge must be transcript-native (`origin = sub_wedge_from_transcript`)
- at least one sub-wedge must represent an operational decision layer, for example `etsy_listing_level_ad_decision_system`, when such decision-workflow evidence exists in the transcript
- `quote_char_count <= 280`
- `quote_word_count <= 40`

## Per-video contract

### Quality gate

Hard-golden:

- `passed = true`
- `wedge_mode = true`
- `min_ideas = 10`
- `min_fms = 45.0`
- `min_bundle_power = 7.5`

Threshold-golden:

- `idea_count >= 10`
- `top_fms_score >= 68.5`
- `top_bundle_power >= 9.0`

### Parent wedge

Hard-golden:

- `domain = etsy_ads`
- `ads_context_confirmed = true`
- `origin = parent_wedge_from_transcript`

### Sub-wedges

Hard-golden:

- `domain = etsy_ads`
- `ads_context_confirmed = true`
- `primary_channel = etsy`
- `secondary_channel = gumroad`
- `claim_verification_status = unverified`
- `origin in {sub_wedge_from_transcript, sub_wedge_backfill_from_parent}`
- `source_type in {sub_wedge_from_transcript, sub_wedge_backfill_from_parent}`
- `evidence_confidence in {medium, low}`

Threshold-golden:

- `distinct_sub_wedge_count >= 3`
- all normalized sub-wedge ids remain inside the canonical Etsy Ads catalog
- at least one sub-wedge must be transcript-native (`origin = sub_wedge_from_transcript`)
- `quote_char_count <= 280`
- `quote_word_count <= 40`

### Validated ideas

Do not golden the full file. Extract a curated summary.

Threshold-golden:

- `item_count >= 10`
- `distinct_canonical_sub_wedges >= 3`
- `ads_specific_ratio >= 0.80`
- top 3 ideas remain ads-specific
- top 5 ideas remain non-generic

### Digital bundle spec

Hard-golden:

- file exists
- top-level keys include `generated_at`, `video_id`, `bundle_spec_count`, `bundle_specs`

Threshold-golden:

- `bundle_spec_count >= 3`
- every bundle spec contains:
  - `video_id`
  - `sub_wedge_id`
  - `buyer`
  - `pain`
  - `outcome`
  - `promise`
  - `wedge`
  - `artifact_stack`
  - `offer_formats`
  - `sku_ladder`
  - `price_ladder`
  - `primary_channel`
  - `secondary_channel`
  - `factory_tasks`
  - `launch_assets`
  - `bundle_power`
  - `top_fms_score`
  - `evidence`
- `artifact_stack_len >= 3`
- `offer_formats_len >= 3`
- `sku_ladder_len >= 3`
- `factory_tasks_len >= 5`
- `price_ladder` sorted ascending
- all `price_ladder` values positive
- `primary_channel = etsy`
- `secondary_channel = gumroad`
- nested `evidence.source_quote` non-empty and `<= 280` chars

## Cluster contract

For the 10-video Etsy Ads batch, the cluster-level fixture contract is:

- `expected_pass_count = 10`
- `allowed_fail_count = 0`
- `min_idea_count_across_cluster >= 10`
- `min_top_fms_across_cluster >= 68.5`
- `min_top_bundle_power_across_cluster >= 9.0`
- `min_distinct_sub_wedges_across_cluster >= 3`
- `digital_bundle_spec.json` required for all videos
- domains remain only `etsy_ads`

## Required fixture files

- `fixtures/regression/etsy_ads_cluster_v1/inputs.json`
- `fixtures/regression/etsy_ads_cluster_v1/cluster_manifest.json`
- `fixtures/regression/etsy_ads_cluster_v1/videos/<video_id>.json`

## Required scripts

- builder: derive curated manifests from raw outputs
- validator: compare current outputs against frozen fixture contracts
- packager smoke: build bundle specs from existing validated ideas for control videos

## Definition of done

Fixture scope is done when:

1. inputs are frozen
2. per-video manifests exist
3. cluster manifest exists
4. deterministic validator passes
5. packager smoke passes for `AC1zd_TTVf0` and `sUuA2_k9g18`

## Non-goals for v1

Do not exact-freeze:

- transcript text
- transcript chunks
- segment counts
- full intermediate agent outputs
- exact evidence quote text
- exact SKU titles
- exact launch copy
- exact price values
- exact ordering of sub-wedges or bundle specs

The regression suite must catch product regressions, not harmless formatting drift.
