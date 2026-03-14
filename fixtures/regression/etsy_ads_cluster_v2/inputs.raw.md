# Etsy Ads v2 Cluster — Raw Intake Draft

Status: draft intake only.

Notes:
- This file preserves the user-provided candidate set as raw JSON fragments for later freeze into `inputs.json` and `cluster_manifest.json`.
- URLs are not replaced here.
- `WNQgc8NzLYc` is intentionally kept as a borderline / mixed-traffic case unless manually swapped later.
- Before freeze, fill in fields such as `duration_minutes`, `has_screen_share`, `contains_metrics`, and any other v2 checklist metadata.

## Candidate 1 — strong reference

```json
{
  "video_id": "xLmnJYWHQ34",
  "url": "https://www.youtube.com/watch?v=xLmnJYWHQ34",
  "language": "en",
  "topic_cluster": "etsy_ads_v2",
  "notes": "Running Etsy Ads the Right Way in 2025; already validated strong reference with listing-level decisions and clear winners/losers workflow.",
  "contains_decision_layer_signals": true,
  "decision_layer_signal_examples": [
    "after 2 to 4 weeks, you can pause the losers and keep the winners",
    "how to start/stop advertising listings"
  ]
}
```

## Candidate 2 — high-budget scaling / budget ladder

```json
{
  "video_id": "lhxcQLmrdhQ",
  "url": "https://www.youtube.com/watch?v=lhxcQLmrdhQ",
  "language": "en",
  "topic_cluster": "etsy_ads_v2",
  "notes": "high budget etsy ads strategy - that will crush competition; focused on staged budget increases and scale-up decision logic.",
  "contains_decision_layer_signals": true,
  "decision_layer_signal_examples": [
    "once it's at 70 to 100% spent each day, increase your budget by 25 to 50%",
    "low budget vs high budget strategy"
  ]
}
```

## Candidate 3 — stop wasting / pitfalls / who should use ads

```json
{
  "video_id": "y4I6vfdD68I",
  "url": "https://www.youtube.com/watch?v=y4I6vfdD68I",
  "language": "en",
  "topic_cluster": "etsy_ads_v2",
  "notes": "I'll Stop You BURNING MONEY With Etsy Ads - Must Watch; focused on common mistakes and who should or should not be using Etsy Ads.",
  "contains_decision_layer_signals": true,
  "decision_layer_signal_examples": [
    "who should and should not be using Etsy ads",
    "common pitfalls and when to avoid ads"
  ]
}
```

## Candidate 4 — painful ad mistakes / winners vs losers

```json
{
  "video_id": "gsTKjofEvOE",
  "url": "https://www.youtube.com/watch?v=gsTKjofEvOE",
  "language": "en",
  "topic_cluster": "etsy_ads_v2",
  "notes": "The Most PAINFUL Etsy Ad Mistakes Etsy Sellers Make Daily; likely includes turning off losers and spend reallocation toward winners.",
  "contains_decision_layer_signals": true,
  "decision_layer_signal_examples": [
    "turning off losers so more spend gets pushed towards winners",
    "biggest mistakes in Etsy ads campaign"
  ]
}
```

## Candidate 5 — not losing money / live mistakes breakdown

```json
{
  "video_id": "eOCVNj0eqqg",
  "url": "https://www.youtube.com/watch?v=eOCVNj0eqqg",
  "language": "en",
  "topic_cluster": "etsy_ads_v2",
  "notes": "How To NOT Lose Money On Etsy Ads In 2025; live-style breakdown of mistakes and how to fix them while keeping ads profitable.",
  "contains_decision_layer_signals": true,
  "decision_layer_signal_examples": [
    "biggest mistakes sellers make and how to fix them",
    "keeping ads profitable, not just running them"
  ]
}
```

## Candidate 6 — complete guide / metrics walkthrough

```json
{
  "video_id": "KmWr4jLlAMU",
  "url": "https://www.youtube.com/watch?v=KmWr4jLlAMU",
  "language": "en",
  "topic_cluster": "etsy_ads_v2",
  "notes": "Are Etsy Ads Worth It? A Complete Guide for Sellers; overview plus setup and performance improvement guidance.",
  "contains_decision_layer_signals": true,
  "decision_layer_signal_examples": [
    "how to set up an ad campaign",
    "tips and tricks for improving performance"
  ]
}
```

## Candidate 7 — general tutorial / metrics reading

```json
{
  "video_id": "4Ed4_0jbw08",
  "url": "https://www.youtube.com/watch?v=4Ed4_0jbw08",
  "language": "en",
  "topic_cluster": "etsy_ads_v2",
  "notes": "Boost Etsy Sales with This Ad Strategy - Full Tutorial; likely includes screenshots, metrics, and general ad strategy walkthrough.",
  "contains_decision_layer_signals": true,
  "decision_layer_signal_examples": [
    "full tutorial on ad strategy",
    "boost sales via ads strategy"
  ]
}
```

## Candidate 8 — stop wasting profit / recurring adjustments

```json
{
  "video_id": "O3K4ZUmv1Bw",
  "url": "https://www.youtube.com/watch?v=O3K4ZUmv1Bw",
  "language": "en",
  "topic_cluster": "etsy_ads_v2",
  "notes": "Stop Wasting Profit on Etsy Ads (Do This Monthly); likely focused on monthly reviews, cutting losers, and doubling down on winners.",
  "contains_decision_layer_signals": true,
  "decision_layer_signal_examples": [
    "do this monthly",
    "cut losers and double down on winners"
  ]
}
```

## Candidate 9 — broader Etsy context with ad-threshold signals

```json
{
  "video_id": "sa4pbYgem1Y",
  "url": "https://www.youtube.com/watch?v=sa4pbYgem1Y",
  "language": "en",
  "topic_cluster": "etsy_ads_v2",
  "notes": "I'll Save You 6 MONTHS Of Etsy PAIN In 10 Minutes; broader Etsy strategy, but useful if it includes threshold logic for when to start Etsy Ads.",
  "contains_decision_layer_signals": true,
  "decision_layer_signal_examples": [
    "don't use Etsy ads until you're making daily organic sales",
    "only start ads after proving viability"
  ]
}
```

## Candidate 10 — borderline mixed-traffic case

```json
{
  "video_id": "WNQgc8NzLYc",
  "url": "https://www.youtube.com/watch?v=WNQgc8NzLYc",
  "language": "en",
  "topic_cluster": "etsy_ads_v2",
  "notes": "Etsy Ads + Meta Ads: Ultimate tutorial for POD sellers; intentionally kept as a borderline mixed-traffic case unless manually swapped later.",
  "contains_decision_layer_signals": true,
  "decision_layer_signal_examples": [
    "ad creation process starting on Etsy",
    "combining Etsy Ads with Meta Ads"
  ]
}
```

## Before freeze

For each video:

- download or generate `transcripts/<video_id>.txt`
- optionally generate `transcripts/<video_id>.json`
- fill in:
  - `duration_minutes`
  - `has_screen_share`
  - `shows_marketplace_ui`
  - `shows_specific_listings`
  - `contains_metrics`
  - `published_at`

Then build:

- `fixtures/regression/etsy_ads_cluster_v2/inputs.json`
- `fixtures/regression/etsy_ads_cluster_v2/cluster_manifest.json`
