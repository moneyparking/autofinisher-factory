# SPEC_money_niche_hunter

## Purpose

`money_niche_hunter` is a hybrid idea pipeline embedded inside the current `autofinisher-factory` repo.

It is designed to:
1. collect a wide raw pool of seed ideas programmatically,
2. run those seeds through the existing monetization batch contour,
3. hard-filter data-broken and obviously dead markets,
4. rank the surviving ideas into a shortlist,
5. optionally run an LLM sanity check on the shortlist,
6. accumulate feedback statistics by source and cluster.

This module does **not** replace the existing monetization pipeline.
It orchestrates idea generation and selection **around** the canonical source-of-truth pipeline:
- `run_monetization_batch_fast.py`
- `monetization_pipeline_fast.py`
- `seed_statuses.json`
- `batch_reference_monitor.py`

---

## Directory layout

```text
money_niche_hunter/
├── __init__.py
├── __main__.py
├── main.py
├── config/
│   └── settings.py
├── core/
│   ├── seeds/
│   │   └── collector.py
│   ├── pipeline/
│   │   └── runner.py
│   ├── analysis/
│   │   ├── filters.py
│   │   ├── scorer.py
│   │   └── analytics.py
│   └── review/
│       └── llm_sanity.py
├── utils/
│   └── storage.py
├── data/
└── docs/
    └── SPEC_money_niche_hunter.md
```

---

## Source of truth

The source of truth for market evaluation remains the existing repo batch contour.

`money_niche_hunter` must treat these artifacts as authoritative:
- `niche_engine/accepted/seed_statuses.json`
- `niche_engine/accepted/batch_progress.json`
- `data/batch_monitoring/reference_batch_summary.json`

`money_niche_hunter` is allowed to derive convenience tables from them, but must not redefine business truth.

---

## Step-by-step flow

### Step 1 — Collect raw seeds

Implemented in `core/seeds/collector.py`.

Input:
- manual base seeds
- Google suggest expansion (and later Etsy/eBay related expansion)

Output:
- `money_niche_hunter/data/raw_seeds.json`

Each raw seed row should contain:
- `seed`
- `source`
- `cluster`
- `level`
- optional `parent`

Example:

```json
{
  "seed": "daily planner printable",
  "source": "google_related",
  "cluster": "planner",
  "level": 1,
  "parent": "daily planner"
}
```

---

### Step 2 — Run seeds through canonical batch contour

Implemented in `core/pipeline/runner.py`.

Mechanism:
1. transform raw seeds into a compatible `vertical_families` payload,
2. write temporary `money_niche_hunter/data/vertical_families_raw.json`,
3. execute `run_monetization_batch_fast.py` with `VERTICALS_PATH` pointing to that file,
4. parse `niche_engine/accepted/seed_statuses.json`,
5. produce a flat result table with **one row per input seed**.

Output:
- `money_niche_hunter/data/batch_results.json`

Batch result fields (current minimum contract):
- `seed`
- `source`
- `cluster`
- `batch_id`
- `seed_status`
- `google_status`
- `etsy_status`
- `status`
- `decision_type`
- `reason_code`
- `reason_detail`
- `fms_score`
- `str_percent`
- `active_count`
- `sold_count`
- `etsy_digital_share`
- `etsy_total_results`
- `avg_reviews_top`
- `overall_confidence`
- `overall_completeness`
- `degraded_sources`
- `warnings`
- `fms_ratio` (placeholder for later reference integration)
- `str_ratio` (placeholder)
- `sold_ratio` (placeholder)

---

### Step 3 — Hard filters

Implemented in `core/analysis/filters.py`.

Rules:
1. Remove all `decision_type in {data_reject, data_uncertain}` from market-truth shortlist flow.
2. Remove all rows where `overall_confidence != high`.
3. Remove obviously dead markets:
   - `active_count == 0 AND sold_count == 0`
4. Remove weak demand + weak conversion:
   - `sold_count < min_sold_count AND str_percent < min_str_percent`
5. Optionally remove overheated or weak-digital niches:
   - `active_count > max_active_count`
   - `etsy_digital_share < min_digital_share`

Outputs:
- filtered in-memory list
- `money_niche_hunter/data/data_bucket.json` for data-broken rows

---

### Step 4 — Composite score + shortlist

Implemented in `core/analysis/scorer.py`.

Current composite score uses normalized:
- `fms_score`
- `sold_count`
- `str_percent`
- `etsy_digital_share`

Weights are defined in `config/settings.py`.

Output:
- `money_niche_hunter/data/shortlist_candidates.json`

Each shortlist row must include:
- all batch result fields
- `composite_score`

---

### Step 5 — LLM sanity check (optional)

Implemented in `core/review/llm_sanity.py`.

Purpose:
Apply a product/market sanity pass only to the shortlist top.

Current behavior:
- loads shortlist,
- queries configured LLM,
- writes results back in-place,
- adds:
  - `product_formats`
  - `difficulty`
  - `differentiators`
  - `toxicity_flags`
  - `sanity_verdict`
  - `sanity_reason`
  - `reviewed_at`
  - `final_score`

Environment:
- `OPENAI_API_KEY`
- optional `OPENAI_BASE_URL`
- optional `MONEY_NICHE_HUNTER_LLM_MODEL`

If no LLM key is configured, step 5 should fail gracefully and not break the whole pipeline.

---

### Step 6–7 — Analytics and feedback loop

Implemented in `core/analysis/analytics.py`.

Purpose:
Track which seed sources and clusters produce stronger outcomes.

Output:
- `money_niche_hunter/data/source_analytics.json`

Analytics dimensions:
- by `source`
- by `cluster`

Tracked counters:
- `total`
- `go`
- `maybe`
- `reject`
- `candidates`
- derived `go_rate`
- derived `success_rate`

---

## Configuration

Defined in `config/settings.py`.

### Thresholds
- `min_confidence`
- `min_sold_count`
- `min_str_percent`
- `max_active_count`
- `min_digital_share`

### Weights
- `fms_score`
- `sold_count`
- `str_percent`
- `digital_share`

### Output paths
- `RAW_SEEDS_PATH`
- `BATCH_RESULTS_PATH`
- `SHORTLIST_PATH`
- `SANITY_OUTPUT_PATH`
- `ANALYTICS_PATH`
- `SEEDS_COLLECTION_STATS_PATH`

---

## Operational notes

1. `money_niche_hunter` is not meant to bypass current monitoring.
2. Use the existing provider stack and `.env.scrape.local` on the server.
3. When running on a large seed set, expect the existing batch contour to write checkpoints in:
   - `niche_engine/accepted/seed_statuses.json`
   - `niche_engine/accepted/batch_progress.json`
4. If the batch ends as `partial`, treat the idea run as diagnostic, not authoritative.
5. If the batch ends as `completed`, use that result for shortlist generation.

---

## CLI usage

Primary entrypoint:

```bash
python3 -m money_niche_hunter
```

This performs:
- collect seeds
- run batch
- hard filters
- shortlist
- optional LLM sanity
- analytics

---

## Next planned extensions

1. Integrate `fms_reference`-based ratio metrics (`fms_ratio`, `sold_ratio`, `str_ratio`) into `batch_results.json`.
2. Add Etsy/eBay suggestion sources in the collector.
3. Add a small CLI for running individual steps.
4. Add a curated manual seed import path.
5. Add an export for reviewer workflow (`csv` / `xlsx`).
