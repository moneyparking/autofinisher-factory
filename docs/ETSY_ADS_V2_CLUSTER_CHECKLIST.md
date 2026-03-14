# Etsy Ads V2 Cluster Checklist

## 0. Fixed contracts from v1

Do not change these before running the next Etsy Ads batch:

- keep the current v1 floor unchanged
- keep `profitability/ROAS without decision-layer = v1_fail`
- keep decision-layer as a must-have for `v1-green`
- keep validator statuses as:
  - `hard_fail`
  - `v1_fail`
  - `target_fail`
  - `pass`

The v2 goal is not to relax the contract. The goal is to test repeatable decision-layer extraction under the same contract.

## 1. Scope for v2

Run a focused Etsy Ads cluster, not a mixed-marketplace batch.

Recommended size:

- start with **10 videos**
- expand to 20 only after the first v2 run shows stable extraction and validation behavior

Use only videos centered on Etsy Ads / Etsy PPC / listing-level ad decisions / ROAS / profitability / testing / budget allocation.

Do not mix in Amazon/KDP/Merch/Gumroad/Shopify for this cluster.

## 2. Intake checklist

A video must pass all of these checks:

- language is primarily English
- duration is roughly 8 to 35 minutes
- topic is explicitly Etsy Ads / Etsy PPC / paid Etsy listing decisions
- video is public and usable for transcript-based analysis
- video is not purely motivational or generic Etsy advice
- transcript contains at least one of these signal families:
  - profitability / ROAS
  - testing
  - listing-level decisions
  - budget allocation
  - pause / scale logic

Strong preference:

- screen share of Etsy Ads or listing analytics
- concrete product/listing examples
- explicit winner/loser language
- timeframe language such as “after X days/weeks” or “once you have enough data”
- operational decision logic, not just overview commentary

## 3. Tiering rubric

### Tier A — ideal

The video includes:

- Etsy Ads context
- profitability / ROAS discussion
- explicit decision workflow
- listing-level or winner/loser language
- testing cadence or enough-data logic

### Tier B — usable

The video includes:

- Etsy Ads context
- profitability / ROAS discussion
- some testing language
- but weaker operational detail

### Tier C — low priority / borderline

The video includes:

- only overview-level Etsy Ads guidance
- mostly profitability / ROAS discussion
- little or no operational decision-layer detail

## 4. Batch composition for 10 videos

Target composition:

- 6 to 7 videos from Tier A
- 2 to 3 videos from Tier B
- 1 to 2 videos from Tier C

This preserves both strong positive cases and a small number of borderline cases for negative/control behavior.

## 5. Required manifest fields

Each selected video should be recorded with at least:

```json
{
  "video_id": "XXXXXXXXXXX",
  "url": "https://www.youtube.com/watch?v=XXXXXXXXXXX",
  "language": "en",
  "duration_minutes": 18,
  "topic_cluster": "etsy_ads_v2",
  "target_marketplaces": ["etsy", "gumroad"],
  "has_screen_share": true,
  "shows_marketplace_ui": true,
  "shows_specific_listings": true,
  "contains_metrics": true,
  "contains_decision_layer_signals": true,
  "decision_layer_signal_examples": [
    "pause losers",
    "keep winners",
    "after 2 weeks",
    "listing-level budget"
  ],
  "published_at": "2024-05-12"
}
```

Mandatory for v2:

- `video_id`
- `url`
- `language`
- `duration_minutes`
- `topic_cluster`
- `target_marketplaces`

Strongly recommended:

- `has_screen_share`
- `shows_marketplace_ui`
- `shows_specific_listings`
- `contains_metrics`
- `contains_decision_layer_signals`
- `decision_layer_signal_examples`
- `published_at`

## 6. Freeze step before running

Before batch execution:

- freeze the candidate list
- write `inputs.json`
- write `cluster_manifest.json`
- confirm transcripts exist or can be fetched
- confirm all videos are still public
- confirm `--wedge-mode` is used
- do not change spec or validator rules during the batch

## 7. Run checklist

For the actual run:

- execute only on the frozen list
- keep the current merged contract unchanged
- keep logs and artifacts under canonical output paths
- do not blend manual overrides into the pipeline outputs

## 8. Validation checklist

After the run, inspect:

### Hard checks

- `hard_fail_count == 0`
- no domain drift
- `digital_bundle_spec.json` exists for all videos
- no quote regressions

### Contract categories

Track these separately:

- `pass`
- `target_fail`
- `v1_fail`
- `hard_fail`

For each `v1_fail`, ask:

1. is this a pipeline miss?
2. or does the source content genuinely lack a strong decision-layer?

## 9. Success criteria for v2

### Minimum acceptable

- `hard_fail_count = 0`
- `v1_fail_count <= 2`
- `pass + target_fail >= 8`

### Strong result

- `hard_fail_count = 0`
- `v1_fail_count <= 1`
- `pass >= 6`
- remaining non-pass cases are mostly `target_fail`, not `v1_fail`

### Bad result

- `v1_fail_count >= 3`
- repeated analytics-only outputs
- decision-layer detector rarely fires
- many videos remain stuck around analytics-only FMS bands

## 10. Growth metrics

In addition to validator results, write a cluster metrics file and compare v1 vs v2 on:

- `decision_wedge_video_ratio`
- `v1_pass_ratio`
- `target_pass_ratio`
- `top_fms_decision_videos_mean`
- `top_fms_no_decision_videos_mean`
- bundle richness (`3+ bundles` share)
- sub-wedge richness (`3+ sub-wedges` share)

Use:

- `v1_green_count = pass_count + target_fail_count`
- `v1_pass_ratio = v1_green_count / video_count`
- `target_pass_ratio = pass_count / video_count`

## 11. Review buckets after v2

Sort videos into three buckets:

### A. True strong cases

- decision-layer present
- strong operational wedge
- at least one bundle reaches v1/target cleanly

### B. Recoverable cases

- decision hints exist
- pipeline partially extracts them
- worth a later targeted extraction patch

### C. True weak-content cases

- mostly profitability / ROAS only
- no real operational stack
- should remain intentional fails

## 12. Stop conditions

Do not proceed to the next cluster if any of these are true:

- validator had to be softened again
- decision-layer detector creates many false positives
- many `v1-green` outputs are not actually stronger than analytics-only cases
- repeated manual review shows the contract is no longer discriminative

## One-line rule for v2

**v2 Etsy Ads is not a search for any usable ads videos; it is a search for repeatable decision-layer extraction under the existing v1 contract.**

## 13. Frozen v2 outcome (March 2026)

The current `etsy_ads_cluster_v2` run is formally fixed as-is.

Observed outcome:

- `video_count_checked = 10`
- `hard_fail_count = 0`
- `v1_fail_count = 1`
- `target_fail_count = 0`
- `pass_count = 9`
- `v1_pass_ratio = 0.9`
- `target_pass_ratio = 0.9`

Decision/richness metrics from `cluster_metrics.json`:

- `decision_wedge_video_ratio = 0.6`
- `avg_bundle_spec_count_per_video = 3.2`
- `avg_distinct_sub_wedge_count_per_video = 3.2`

The single non-pass case is:

- `WNQgc8NzLYc` → `v1_fail`

Reason for keeping it in the frozen set:

- it is an expected borderline / mixed-traffic case
- it helps verify that the validator does not silently accept mixed Etsy + Meta traffic videos as clean Etsy Ads decision-layer cases
- thresholds were not relaxed or tuned around this video

Formal interpretation:

- `etsy_ads_cluster_v2` is considered a successful regression cluster
- `9/10` videos are `v1-green` and `target-green`
- `1/10` expected `v1_fail` is retained as an intentional edge / negative case

Do not rewrite the v1 floor or decision-layer requirement to force `10/10`.
