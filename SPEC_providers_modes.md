# Spec: Provider Layer, Scrape Modes, and Multi‑Provider Waterfall (Autofinisher Factory)

## Context and intent
The project now relies on external scraping providers (currently scrape.do, previously ZenRows). We need to:

1. **Centralize provider selection and API key management** so switching providers or plans is a one‑file change.
2. **Introduce explicit cost/quality modes** (economy/balanced/expensive) so wide discovery runs are cheap and deep validation runs are expensive only where it matters.
3. **Support multi‑provider routing** (primary + fallback waterfall) per channel to improve reliability and reduce vendor lock‑in.
4. Provide a **practical plan** for “self use” (not a SaaS): how to manage credits, provider rotation, and implementation complexity.

This spec is written to fit the current repo architecture:
- `network_retry.py` is the canonical retry/metadata layer.
- `scrape_clients.py` is the current provider wrapper.
- Channel-specific scrapers exist: `etsy_mcp_scraper.py`, `google_niche_scraper.py`, `niche_profit_engine.py` (eBay).
- Batch orchestrators: `monetization_pipeline_fast.py`, `run_monetization_batch_fast.py`, `money_niche_hunter/*`.

---

## Definitions

### Channel
A **channel** is a logical scraping purpose and contract. Examples:
- `google_serp_html`
- `etsy_search_html`
- `etsy_listing_html`
- `ebay_search_html`

Each channel may use different providers and different “tiers”.

### Tier
A **tier** is a technical capability class for requests:
- **Tier 1 (Economy)**: datacenter/basic proxies, no JS render, minimal options.
- **Tier 2 (Standard)**: better proxies/rotations, moderate reliability.
- **Tier 3 (Premium/Stealth)**: residential/mobile (“super”), optional JS rendering, most expensive.

### Mode
A **mode** is an operator-level cost profile for a run:
- `cheap` → discovery/wide batches
- `balanced` → default operation
- `expensive` → deep validation on shortlist / winners

Mode chooses:
- which tiers/providers are allowed/preferred
- timeout/retry budgets
- optional deep signals (e.g. Etsy sales top‑N inspect)

---

## Requirements

### R1: Single control plane for provider config
- Provider selection **must not** be scattered across modules.
- All provider endpoints/feature flags/tokens must be addressable via **one config module** and `.env*`.

### R2: Mode is a single knob
- All batch entrypoints must accept `SCRAPE_MODE` via env (`cheap|balanced|expensive`).
- Modules should not implement their own ad-hoc “cheap/expensive” logic.

### R3: Waterfall fallback per channel
- Each request must be able to attempt multiple providers in a deterministic order:
  - stop on success
  - fail over only on retryable failures (timeouts, connection errors, provider 5xx, provider 4xx that indicates auth/rate limits)
  - **do not** fail over for “market 404/empty results” type cases

### R4: Telemetry and reproducibility
- Persist in `source_quality`:
  - `provider_name`, `tier_used`, `failover_count`
  - `attempts` list with provider-level status
- Persist in batch monitoring:
  - requests per provider
  - failovers per provider
  - estimated credit cost (optional, best-effort)

### R5: “Self use” practicality
- Keep implementation lightweight.
- Avoid building/operating an in-house proxy pool.
- Make it easy to plug in new trial credits.

---

## Non‑requirements
- No need for multi-tenant key storage or user-level quotas.
- No need for perfect credit accounting (provider dashboards differ). We only need approximate “what consumed what”.
- No need for fully async scraping framework.

---

## Proposed architecture

### 1) New module: `providers/registry.py`
Create a small provider registry and request router.

**Responsibilities**:
- Load `.env`, `.env.openai.local`, `.env.scrape.local` (already done in `scrape_clients.py`; we will move that logic here).
- Load a declarative provider map from `providers.yaml` (or `providers.json`).
- Expose:
  - `get_provider(channel: str, tier: str | None, mode: str) -> ProviderSpec`
  - `fetch(channel: str, url: str, *, purpose: str, mode: str | None = None, allow_render: bool | None = None, ...) -> (html, meta)`

**ProviderSpec fields** (minimum):
- `name`: logical provider name
- `type`: `scrapedo|scrapingbee|zenrows|scraperapi|...`
- `api_key_env`: env var name
- `endpoint_env` or static endpoint
- `default_params`: per-provider defaults (render, geoCode, super, customHeaders)
- `cost_profile`: `ultra_cheap|cheap|medium|premium`
- `capabilities`: `render`, `residential`, `geo`, `js`


### 2) Config file: `providers.yaml`
A single source of truth for:
- channels
- available providers per tier
- waterfall order per mode

**Example structure** (conceptual):

- `channels.<channel>.tiers.tier_1|tier_2|tier_3`: ordered list of provider names
- `channels.<channel>.waterfall.<mode>.tiers`: list of tiers to attempt (e.g. `[tier_1, tier_2]`)
- `providers.<provider_name>`: provider definitions


### 3) Replace direct provider selection with channel calls
Update channel scrapers to use the registry:

- `google_niche_scraper.py`:
  - replace `GOOGLE_HTML_CLIENT = ScrapeClient(...)` with `providers.fetch(channel="google_serp_html", ...)`

- `etsy_mcp_scraper.py`:
  - both `scan_keywords()` and `inspect_listing()` use `providers.fetch(channel="etsy_search_html")` and `providers.fetch(channel="etsy_listing_html")`

- `niche_profit_engine.py` (eBay):
  - use `providers.fetch(channel="ebay_search_html")`

**Result**: Changing providers does not touch these modules.


### 4) Mode and tier routing rules

#### Mode defaulting
- If `SCRAPE_MODE` env is set, it becomes default for the process.
- Entry points may override:
  - `money_niche_hunter` seed discovery → default `cheap`
  - shortlist deep validation → default `expensive`


#### What mode changes

| Control | cheap | balanced | expensive |
|---|---:|---:|---:|
| retries | 0–1 | 1–2 | 2–3 |
| timeout | short | medium | long |
| allow JS render | off | only if needed | on (for listing pages if required) |
| tiers attempted | T1 only | T1→T2 | T1→T2→T3 |
| Etsy listing inspect top‑N | 0–2 | 2–3 | 5–10 |

Implementation detail: `providers.fetch()` receives `mode` and computes:
- provider order (waterfall)
- timeout/retry budgets
- default params (render, super, geoCode)


### 5) Waterfall / fallback policy

#### Failover triggers (retryable)
Failover to next provider if:
- connection/timeout
- provider 5xx
- provider 429
- provider 401/403 **only if** it clearly indicates provider auth/rate (not site-level “market access denied”) — heuristics via error body + provider context

Do **not** fail over if:
- page returns 200 with “0 results” type content
- eBay/Etsy legitimately returns empty results

#### Data quality recording
Add to `meta`:
- `provider_name`
- `tier`
- `failover_count`
- `attempts`: list of `{provider, status, latency_ms, error_code, failure_stage}`

`fms_decision.aggregate_data_quality()` should treat provider failover as a warning, not a fatal condition, if final response is ok.


### 6) Credit/cost accounting (best-effort)

Add to batch-level stats:
- `requests_by_provider` (count)
- `failovers_by_provider` (count)
- `requests_by_channel` (count)

Optional: `estimated_credits_by_provider`:
- maintained via static multipliers in `providers.yaml` per provider/tier (e.g. `credits_per_request_estimate`)
- used only for internal planning, not as source-of-truth


---

## Operational workflow for “self use”

### Goal
Run discovery cheaply most of the time, and spend expensive credits only on candidates/winners.

### Recommended run patterns

1) **Discovery runs (cheap)**
- `SCRAPE_MODE=cheap`
- `ETSY_INSPECT_TOP_N_SALES=0..2`
- tiers: T1 only

2) **Validation runs (balanced)**
- `SCRAPE_MODE=balanced`
- `ETSY_INSPECT_TOP_N_SALES=2..3`
- tiers: T1→T2

3) **Deep verification (expensive)**
- `SCRAPE_MODE=expensive`
- `ETSY_INSPECT_TOP_N_SALES=5..10`
- tiers: T1→T2→T3
- optional JS render only on Etsy listing pages

### Provider rotation strategy
- Keep 1 paid “primary” provider.
- Keep 1–2 “trial/backup” providers configured as fallbacks.
- Avoid manual switching; rely on waterfall.

### Complexity vs benefit
For a personal project:
- Implementing the registry + YAML + waterfall is moderate complexity (1–2 days).
- Operating your own proxy pool is high complexity (weeks) and not justified.
- Multi-provider fallback provides 80% of “availability” benefits with low ops burden.

---

## Implementation plan (phased)

### Phase 0 — Hardening prerequisites (already mostly done)
- Ensure env files load from a single place.
- Ensure provider tokens are never printed.

### Phase 1 — Provider registry + config
1. Add `providers.yaml` with current providers (scrape.do, scrapingbee).
2. Add `providers/registry.py`:
   - load env
   - parse YAML
   - build ProviderSpec objects
3. Add `providers/fetch.py`:
   - `fetch(channel, url, mode, ...)` with waterfall

Deliverable: A single test script can fetch Etsy search HTML via registry.

### Phase 2 — Migrate channel scrapers
- Replace `ScrapeClient` usage in:
  - `google_niche_scraper.py`
  - `etsy_mcp_scraper.py`
  - `niche_profit_engine.py`

Deliverable: no module imports provider tokens directly.

### Phase 3 — Mode wiring
- Add env `SCRAPE_MODE` used by default.
- Update entry points:
  - `run_monetization_batch_fast.py` sets mode based on run type
  - `money_niche_hunter` uses cheap for discovery, balanced/expensive for shortlist.

Deliverable: switching mode changes tiers/timeouts/inspect depth.

### Phase 4 — Telemetry
- Extend `network_retry` meta schema to include provider/tier/attempts.
- Update monitoring summary to include `requests_by_provider` etc.

Deliverable: batch summaries show provider mix and failovers.

### Phase 5 — Optional refinements
- Per-channel “render policy” (only Etsy listing pages can enable render).
- Per-channel “super policy” (super only in T3).

---

## Acceptance criteria

1. Changing provider for Etsy search is a **config-only change** (`providers.yaml` + env keys).
2. `SCRAPE_MODE` toggles actual behavior:
   - cheap runs do not use tier_3
   - expensive runs can use tier_3 and render
3. Waterfall works:
   - forced provider failure causes automatic failover
4. Monitoring shows:
   - provider used
   - failovers
   - requests counts

---

## Notes on the scrape.do Hobby plan
The Hobby plan (250k credits, 5 concurrency, super + render + geo) is suitable if:
- cheap mode is used for broad discovery
- expensive mode is used only on shortlist

If expensive mode is used on every seed (e.g. `ETSY_INSPECT_TOP_N_SALES=5` + super everywhere), credits may drain quickly. The design above explicitly prevents that by default.
