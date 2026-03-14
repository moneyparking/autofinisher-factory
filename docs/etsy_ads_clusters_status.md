# Etsy Ads Clusters Status

## Current formal status

### `etsy_ads_cluster_v2`

This cluster is fixed as-is and should be treated as the current Etsy Ads regression reference set.

Validator outcome:

- `video_count_checked = 10`
- `hard_fail_count = 0`
- `v1_fail_count = 1`
- `target_fail_count = 0`
- `pass_count = 9`

Named outcome buckets:

- `pass`: 9
- `target_fail`: 0
- `v1_fail`: 1
- `hard_fail`: 0

Single `v1_fail`:

- `WNQgc8NzLYc`
  - expected borderline / mixed-traffic case
  - lacks a strong enough pure Etsy Ads decision-layer to clear the current threshold
  - retained intentionally as a negative / edge case

Metrics summary:

- `v1_pass_ratio = 0.9`
- `target_pass_ratio = 0.9`
- `decision_wedge_video_ratio = 0.6`
- `avg_bundle_spec_count_per_video = 3.2`
- `avg_distinct_sub_wedge_count_per_video = 3.2`
- `top_fms_min = 55.12`
- `top_fms_mean = 67.162`

## Policy decision

The current `v2` result is accepted without softening thresholds.

Interpretation:

- the v1 contract remains discriminative
- decision-layer extraction reproduces on a fresh Etsy Ads batch
- mixed Etsy + Meta traffic content can still fail honestly

This means `etsy_ads_cluster_v2` is not a failed cluster. It is a successful cluster with one expected borderline fail.

## Recommended next split

Keep:

- `etsy_ads_cluster_v2` as the main Etsy-only / mostly-clean regression cluster

Later add:

- a separate `etsy_ads_mixed_traffic_cluster` for intentionally mixed or dirty edge cases

That keeps the primary regression contract clean while preserving robustness coverage for mixed-traffic videos.
