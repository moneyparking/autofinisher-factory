# Autofinisher 2.0 — Wedge-First Goal

Generated: 2026-03-13
Project root: `/home/agent/autofinisher-factory`

## Core Goal

Autofinisher must stop behaving like a generic template factory.

Its job is **not** to generate "another planner", "another Notion template", or "another broad digital product" inside saturated categories.

Its job is to identify **fresh, monetizable buyer-pain wedges** from live market signals, validate them with marketplace evidence, and package them into differentiated digital products that can be shipped quickly with AI.

### Target outcome

Autofinisher should:

1. detect emerging pain signals from public and private market language,
2. convert those signals into buyer-specific wedge objects,
3. select the best monetization format _after_ the wedge is clear,
4. validate the wedge with marketplace evidence,
5. package a differentiated bundle fast enough to capture market share before the category commoditizes.

This means Autofinisher is not a planner factory.
It is a **market wedge discovery and packaging engine**.

---

## What changes right now

### 1. Signal-first instead of keyword-first

Old behavior:
- start from broad keywords,
- search a category,
- generate generic product ideas.

New behavior:
- start from **pain signals**,
- identify **buyer + pain + outcome**,
- build a **wedge object**,
- only then choose a product format.

### 2. Wedge-first instead of format-first

Old behavior:
- choose a format first (`planner`, `template`, `dashboard`),
- then look for a niche to fit it.

New behavior:
- identify the wedge first,
- then decide whether the best artifact is:
  - dashboard
  - calculator
  - mini-course
  - prompt library
  - workflow kit
  - audit pack
  - bundle
  - workbook
  - checklist
  - workspace
  - SOP pack
  - swipe file

Formats are packaging, not niches.

### 3. Kill generic planner-first ideas early

A new **kill-gate** is required.

Ideas should die immediately if they look like:
- "another planner"
- "another generic Notion template"
- "another broad productivity system"
- any abstraction without a specific buyer and outcome

Examples that should be rejected early:
- `execution system`
- `business workflow template`
- `productivity planner`
- `2026 notion template`

unless they are rewritten into a buyer-specific wedge.

### 4. WedgeScore becomes the primary ranking layer

`FMS` remains useful, but it should no longer be the only strategic score.

A new `WedgeScore` should rank opportunities by:
- pain intensity
- buyer clarity
- AI production fit
- differentiation space
- channel fit
- expansion potential
- competition penalty

`FMS` becomes a **secondary marketplace validation score**, not the sole decision-maker.

### 5. Separate topic / offer / validation query

Autofinisher must stop mixing these three layers.

Each opportunity should carry three different representations:

- `topic` — what market shift or pain area this belongs to
- `offer_title` — the human-facing product idea
- `validation_queries[]` — product-like search queries for Etsy / eBay / other marketplaces

Example:

```json
{
  "topic": "Etsy sellers struggling to test Meta Ads profitably",
  "offer_title": "Etsy Ad Testing OS",
  "validation_queries": [
    "etsy ads tracker dashboard",
    "meta ads testing calculator",
    "etsy growth dashboard",
    "creative testing template"
  ]
}
```

This is required to prevent abstract ideas from poisoning marketplace validation.

---

## New architecture

## 1. Signal Radar

### Mission
Detect live market pain signals, not just keywords.

### Inputs
- YouTube transcripts / subtitles
- Discord exports or summaries
- Reddit threads
- Etsy reviews
- Etsy listing titles/tags
- other creator/business discussions

### Output
A set of **signal objects** such as:

```json
{
  "buyer": "etsy sellers running paid traffic",
  "pain": "cannot measure ad profitability by listing type",
  "outcome": "find winning listings faster",
  "language_markers": [
    "creative fatigue",
    "which listings scale",
    "roas confusion"
  ],
  "novelty_signal": 0.81
}
```

Signal Radar should never output finished products. It should output structured market evidence.

---

## 2. Wedge Miner

### Mission
Convert signal objects into **wedge objects**.

A wedge object must contain:
- buyer
- pain
- desired outcome
- differentiating mechanism
- likely product artifact types
- channel fit
- validation queries

Example:

```json
{
  "buyer": "freelancers managing multiple clients",
  "pain": "chaotic CRM and lost follow-ups",
  "outcome": "automated client pipeline and zero missed follow-ups",
  "wedge": "freelancer client management system",
  "artifact_candidates": [
    "dashboard",
    "automation pack",
    "SOP bundle"
  ],
  "channel_fit": ["gumroad", "etsy"],
  "validation_queries": [
    "freelancer crm template",
    "client dashboard notion",
    "lead tracker template"
  ]
}
```

This becomes the new unit of work.

---

## 3. Format Selector

### Mission
Choose the best product packaging **after** the wedge is known.

Default rule:
- course + bundle combinations are often stronger than a standalone planner,
- standalone planner ideas should usually be downgraded unless the buyer-pain-outcome fit is extremely strong.

Preferred packaging patterns:
- dashboard + checklist + quickstart guide
- mini-course + prompts + worksheet
- audit kit + SOP pack
- prompt library + swipe file + template bundle
- workspace + automation pack + setup course

Pure planners should almost never be the default recommendation.

---

## 4. Validation Engine

### Mission
Validate wedges, not abstractions.

### Primary validation
- Etsy search signal
- Etsy listing inspection
- digital share
- competitor review density
- pricing cluster
- observed sales badge signals when available

### Secondary validation
- FMS
- optional eBay, but only for **product-like queries**

### Important rule
Skip eBay when the query is too abstract.

Bad:
- `repeatable execution system`
- `business bottlenecks`

Good:
- `client onboarding workbook`
- `etsy seo checklist`
- `freelancer crm template`
- `pricing calculator spreadsheet`

---

## 5. Packaging Engine

### Mission
Turn the validated wedge into a differentiated sellable bundle.

Expected outputs:
- research report
- wedge matrix / wedge JSON
- validated ideas
- Etsy listing assets
- Templated handoff assets
- Excalidraw maps
- course outline
- prompt pack
- ready-to-sell checklist

The package should present the wedge clearly:
- buyer
- pain
- outcome
- mechanism
- product bundle
- why this is differentiated

---

## Scoring model

## WedgeScore (new primary score)

Suggested dimensions:
- `pain_intensity`
- `buyer_clarity`
- `ai_production_fit`
- `differentiation_space`
- `channel_fit`
- `expansion_potential`
- `competition_penalty`

`WedgeScore` should be the strategic ranking layer.

## FMS (existing secondary score)

Keep FMS for marketplace evidence and packaging confidence, but do not use it alone to decide what Autofinisher should build.

A good wedge can have mediocre FMS if the query design is weak or the marketplace fit is partial.
A bad wedge can look decent on FMS if it falls into a broad category with noisy search results.

The final decision should combine:
- WedgeScore
- FMS
- packaging fit
- production speed

---

## What we keep from the previous system

We keep:
- `etsy_mcp_scraper`
- `scrape_clients`
- `inspect_listing`
- `fms_engine`
- `monetization_pipeline_fast` patterns that are still useful for marketplace validation

These remain valuable as **validation infrastructure**.

What changes is the front half of the system:
- discovery
- wedge formation
- format selection
- kill-gating

---

## What we do NOT assume as fact

Revenue claims from:
- private Discord chats
- screenshots
- anecdotal posts
- private Etsy/Facebook groups

must be treated as **signals or hypotheses**, not ground truth.

They may inspire wedge formation, but Autofinisher should still validate them through public or machine-observable evidence wherever possible.

---

## Immediate implementation decisions

### Change now
1. Add `wedge_mode` as a first-class operating mode.
2. Add `buyer`, `pain`, `outcome`, `wedge`, `artifact_candidates`, `validation_queries`, and `differentiation_angle` to the internal schema.
3. Add a kill-gate that rejects planner-first and generic abstraction-first ideas.
4. Broaden the product ontology beyond planners/templates.
5. Make Etsy the primary market validator for digital goods.
6. Use eBay only for concrete product-like queries.
7. Treat transcript/subtitle ingestion as critical infrastructure, not a nice-to-have.

### Defer until after transcript reliability is fixed
1. large overnight YouTube batches,
2. aggressive WedgeScore tuning,
3. scaling to many simultaneous videos,
4. portfolio-level wedge clustering.

---

## Immediate strategic posture

Autofinisher 2.0 should now be operated under this principle:

> First identify the buyer, the pain, and the outcome.
> Then identify the wedge.
> Then decide the artifact.
> Then validate the market.
> Then package the bundle.

Not the other way around.

---

## Short version

Autofinisher is no longer a template generator.

It is a:
- **signal discovery engine**,
- **wedge mining engine**,
- **market validation engine**,
- **AI packaging engine**.

Its competitive advantage is speed of wedge capture, not volume of generic templates.

---

## Status

This document is the current north-star architecture for Autofinisher 2.0.
Any future changes should be evaluated against this question:

**Does this make Autofinisher better at discovering and capturing high-value digital wedges, or does it push the system back toward generic template production?**
