# Phase 4 — Factory Throughput

Phase 4 shifts Autofinisher Factory from scraping-provider experimentation to operational throughput.

Primary goal:
- turn stable scraping inputs into validated opportunities, SKU tasks, publish packets, and a visible release queue

This phase intentionally does **not** expand provider complexity.
Production scraping should remain Scrape.do-first until the factory proves it has outgrown that constraint.

---

## Phase 4 operating principles

1. Quality over provider novelty.
2. One production scraping path is better than many half-verified ones.
3. Every opportunity must have a visible state.
4. Validation must be reasoned, not implicit.
5. SKU generation must produce concrete downstream work.
6. Publish readiness must be observable from artifacts already in the repo.
7. New output files should be thin, explicit, and easy to verify.

---

## Production scraping policy for this phase

Production default:
- Etsy search HTML -> Scrape.do
- Etsy listing HTML -> Scrape.do
- eBay search HTML -> Scrape.do
- Google SERP HTML -> Scrape.do

Other providers remain in the architecture but are parked for now.
They are preserved for later activation, not active throughput work.

---

## Phase 4 target flow

1. Discovery
   - produce candidate niches and structured raw metrics
2. Validation
   - decide winner / candidate / reject / uncertain with explicit reasons
3. SKU conversion
   - create concrete SKU tasks from winning opportunities
4. Asset and listing preparation
   - create deliverables, packet files, preview assets, and listing metadata
5. Publish queue
   - expose a visible queue with operational status per niche/SKU cluster
6. Monitoring and iteration
   - observe batch quality and release readiness from artifacts, not guesswork

---

## Canonical queue states

Each queue item should resolve to exactly one current state:

- `validated`
  - validated artifact exists
  - no win card yet
- `winner_ready`
  - win card exists
  - SKU task may or may not exist yet
- `sku_ready`
  - SKU task exists
  - publish-ready assets are not complete yet
- `asset_ready`
  - ready-to-publish asset folder exists with core files
- `listing_ready`
  - publish packet exists with listing JSON and upload checklist
- `publish_ready`
  - asset and listing packet are both present
- `published`
  - reserved for future live publish confirmation
- `observed`
  - reserved for future post-publish observation layer
- `iterated`
  - reserved for future rework / relaunch layer

This phase only requires reliable resolution through `publish_ready`.

---

## Required artifact relationships

For a single niche, the ideal artifact path is:

- `data/validated_niches/items/<niche>.json`
- `data/winners/<niche>.json`
- `data/sku_tasks/sku_task_<niche>.json`
- `ready_to_publish/<slug>/...`
- `publish_packets/<slug>/...`

Phase 4 must make these relationships visible and easy to inspect.

---

## Minimal deliverables for Phase 4 build

1. Scrape.do-only production routing policy in `providers.yaml`
2. One queue builder that reads existing artifacts and emits a compact operational queue
3. One queue summary JSON under `publish_packets/`
4. Clear state resolution rules
5. Fast validation through compile/runtime checks

---

## Exit criteria for the first Phase 4 build

The first build is complete when:

1. `providers/doctor.py` shows Scrape.do-first plans for production channels
2. a queue builder runs without manual patching
3. the queue builder emits a JSON summary
4. each queue item has a deterministic current state
5. the output is derived only from existing repo artifacts

---

## What is intentionally deferred

Not part of this immediate build:
- provider re-activation experiments
- MCP facade work
- browser automation escalation
- live publish confirmation integration
- post-publish analytics automation

These can be added later once the factory proves stable throughput in the simpler mode.
