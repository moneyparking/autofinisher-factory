# Provider Integration Notes

This document is the operational source of truth for connecting, validating, and safely activating scraping providers in Autofinisher Factory.

Scope:
- provider auth and env mapping
- endpoint format
- request parameter model
- target fit
- cost / risk notes
- activation checklist
- what is already verified in this repo vs what still requires vendor-doc confirmation

This document is intentionally strict. If a provider is not marked as verified, do not enable it for production traffic until it passes the activation checklist.

---

## Core operating rules

1. **`.env.scrape.local` is the only credential source-of-truth.**
2. **`providers.yaml` is the routing source-of-truth.**
3. **Runtime plan must be inspected through `providers/doctor.py` before any live test.**
4. **Live validation must be done through `providers/smoke_test.py` or a tier-specific smoke script.**
5. **Never assume that one provider working on Google means it will also work on Etsy/eBay listing HTML.**
6. **Never treat API tokens, proxy passwords, and account passwords as interchangeable.**
7. **Provider-specific flags must be added through `provider_param_overrides`, not by polluting tier-level params.**

---

## Current provider layer model

The runtime request model is:

`provider.default_params + tier_default_params + provider_param_overrides + extra_params`

The execution model is:

`channel -> mode -> ordered tiers -> ordered providers -> attempt classification -> success / failover / terminal`

Use these tools before spending credits:
- `python3 providers/doctor.py`
- `python3 providers/smoke_test.py --channel <channel> --url <url> --mode <mode> --timeout <seconds>`

---

## Provider matrix

## 1) Scrape.do

- **Provider key in repo:** `scrapedo`
- **Env var:** `SCRAPEDO_TOKEN`
- **Transport:** `rest_api`
- **Configured endpoint:** `https://api.scrape.do/`
- **Adapter auth model in code:** query param `token=<SCRAPEDO_TOKEN>`
- **Adapter URL model in code:** query param `url=<target_url>`
- **Current code defaults:** `customHeaders=false`
- **Current target usage:** Etsy search/listing, Google HTML, eBay HTML fallback paths
- **Operational fit:** cheap HTML fetches; useful as fallback when vendor-specific anti-bot features are not required
- **Observed runtime in this repo:** timed out on Etsy listing fallback during smoke tests
- **Cost sensitivity:** medium; avoid repeated failing retries on same target
- **Status:** integrated in code, partially runtime-tested, not yet proven stable for Etsy listing HTML
- **Activation rule:** safe to keep enabled as lower-cost fallback, but do not treat as listing-grade stable until smoke tests pass repeatedly

## 2) ScraperAPI

- **Provider key in repo:** `scraperapi`
- **Env var:** `SCRAPER_API_KEY`
- **Transport:** `rest_api`
- **Configured endpoint:** `https://api.scraperapi.com/`
- **Adapter auth model in code:** query param `api_key=<SCRAPER_API_KEY>`
- **Adapter URL model in code:** query param `url=<target_url>`
- **Operational fit:** generic HTML fetch / SERP-style routing depending on vendor features
- **Observed runtime in this repo:** not live-verified in current phase
- **Cost sensitivity:** medium
- **Status:** code-integrated, docs and runtime activation still pending
- **Activation rule:** do not enable in production until vendor-doc parameter check and one successful smoke test per target family

## 3) WebScrapingAPI

- **Provider key in repo:** `webscrapingapi`
- **Env var:** `WEBSCRAPINGAPI_KEY`
- **Transport:** `rest_api`
- **Configured endpoint:** `https://api.webscrapingapi.com/v1`
- **Adapter auth model in code:** query param `api_key=<WEBSCRAPINGAPI_KEY>`
- **Adapter URL model in code:** query param `url=<target_url>`
- **Operational fit:** generic HTML fetch / target-specific JS rendering depending on vendor support
- **Observed runtime in this repo:** currently disabled; not live-verified in current phase
- **Cost sensitivity:** medium
- **Status:** code-integrated, docs verification and runtime verification still pending
- **Activation rule:** enable only after vendor docs confirm parameter names used by adapter and smoke test passes

## 4) ScrapingBee

- **Provider key in repo:** `scrapingbee`
- **Env var:** `SCRAPINGBEE_KEY`
- **Transport:** `rest_api`
- **Configured endpoint:** `https://app.scrapingbee.com/api/v1/`
- **Adapter auth model in code:** query param `api_key=<SCRAPINGBEE_KEY>`
- **Adapter URL model in code:** query param `url=<target_url>`
- **Doc-confirmed request flags used in repo:** `render_js`, `premium_proxy`
- **Important vendor guidance confirmed:**
  - target URL must be properly encoded
  - difficult targets may require `premium_proxy=true`
  - general HTML endpoint is different from ScrapingBee Google-specific endpoint
- **Current repo-specific override:**
  - `etsy_listing_html.tier_1.provider_param_overrides.scrapingbee.premium_proxy=true`
- **Operational fit:** general HTML scraping, especially when vendor anti-bot features are needed
- **Observed runtime in this repo:**
  - worked historically for Google through a separate Google-specific path / endpoint
  - unstable on Etsy listing HTML
  - observed outcomes include `500` and `target_404`
  - `premium_proxy=true` did not resolve Etsy listing outcome for tested URL
- **Cost sensitivity:** high enough to avoid batch testing without a fixed request profile; live tests consumed credits
- **Status:** docs-verified, code-verified, runtime-tested, not yet Etsy-listing-stable
- **Activation rule:**
  - safe for controlled testing
  - not yet the final stable provider for Etsy listing HTML
  - test one URL per profile change; avoid batch runs until a stable pattern is found

## 5) ZenRows

- **Provider key in repo:** `zenrows`
- **Env var:** `ZENROWS_KEY`
- **Transport:** `rest_api`
- **Configured endpoint:** `https://api.zenrows.com/v1/`
- **Adapter auth model in code:** query param `apikey=<ZENROWS_KEY>`
- **Adapter URL model in code:** query param `url=<target_url>`
- **Operational fit:** generic HTML / JS rendering / anti-bot use cases depending on vendor plan and flags
- **Observed runtime in this repo:** currently disabled; not live-verified in current phase
- **Cost sensitivity:** medium to high depending on anti-bot settings
- **Status:** code-integrated, docs partially verified, runtime activation pending
- **Activation rule:** enable only after docs check for target-side rendering parameters and successful smoke test

## 6) Apify Proxy

- **Provider key in repo:** `apify_proxy`
- **Env var:** `APIFY_PROXY_PASSWORD`
- **Transport:** `http_proxy`
- **Configured endpoint:** `proxy.apify.com:8000`
- **Adapter auth model in code:** proxy URL `http://<proxy_username>:<APIFY_PROXY_PASSWORD>@proxy.apify.com:8000`
- **Current default proxy username in repo:** `auto`
- **Doc-confirmed rule:** external proxy access uses `hostname=proxy.apify.com`, `port=8000`, `username=auto or groups/session/country`, `password=Apify Proxy password`
- **Important distinction:** this requires **Apify Proxy password**, not API token
- **Observed runtime in this repo:**
  - `407 Proxy Authentication Required` before auth fix
  - `403 Forbidden` after auth fix
  - plan page explicitly states that external HTTP client access is not enabled on current plan
- **Operational fit:** only usable if external proxy access is enabled on the Apify account plan
- **Cost sensitivity:** not the blocker; current blocker is plan entitlement
- **Status:** docs-verified, adapter corrected, blocked by current Apify plan
- **Activation rule:** keep disabled for real production routing until Apify plan allows external HTTP client proxy access

## 7) Bright Data

- **Provider key in repo:** `brightdata`
- **Env var:** `BRIGHT_DATA_AUTH`
- **Endpoint env var:** `BRIGHT_DATA_ENDPOINT`
- **Transport:** `http_proxy`
- **Configured endpoint:** `brd.superproxy.io:33335`
- **Adapter auth model in code:** proxy URL `http://<BRIGHT_DATA_AUTH>@<BRIGHT_DATA_ENDPOINT>`
- **Credential format expected by current repo:** combined native proxy auth string in the form `brd-customer-<ACCOUNT_ID>-zone-<ZONE_NAME>[:flags]:<ZONE_PASSWORD>`
- **Current adapter TLS behavior:** `verify=False` is used in the requests path, so live smoke tests are not blocked by missing local Bright Data CA installation
- **Important vendor guidance confirmed:**
  - Bright Data residential / proxy-network access may require either loading the Bright Data SSL certificate or explicitly bypassing SSL verification
  - proxy behavior is controlled by the username segment, for example `country-us`, `state-ny`, `asn-<ASN>`, `ip-<IP>`
  - current repo model supports this by storing the full auth string in `BRIGHT_DATA_AUTH`
- **Operational fit:** higher-cost anti-bot / proxy-heavy flows
- **Observed runtime in this repo:**
  - `providers/doctor.py` confirms `brightdata: OK`
  - key presence confirmed through `BRIGHT_DATA_AUTH`
  - endpoint resolved from `BRIGHT_DATA_ENDPOINT` to `brd.superproxy.io:33335`
  - direct isolated smoke test on `etsy_listing_html` with `tier='tier_3'` and Etsy listing URL `https://www.etsy.com/listing/1682665810/digital-planner` reached live request execution and returned `HTTP 502`
  - Phase 3 runner `providers/brightdata_phase3.py` now writes a verification ledger to `data/provider_verification/brightdata_phase3_latest.json`
  - controlled Bright Data matrix has been run for at least two variants on the same Etsy listing target:
    - `base`
    - `base__country_us`
  - both tested variants returned the same `brightdata:502` outcome in the standard provider path
  - this means Bright Data is no longer blocked on missing env / missing endpoint / basic adapter wiring, but username-level country targeting has not yet changed the Etsy listing result profile
- **Cost sensitivity:** high
- **Status:** code-integrated, docs-aligned, auth/env model aligned, live-tested, Phase-3-verified through a saved ledger, but not yet Etsy-listing-stable
- **Activation rule:** keep available for controlled tier-specific testing and future MCP-facing facade work, but do not treat as stable production routing for Etsy listing HTML until a clean success profile is reproduced

## 8) Oxylabs

- **Provider key in repo:** `oxylabs`
- **Env var:** `OXYLABS_KEY`
- **Transport:** `http_proxy`
- **Configured endpoint:** `realtime.oxylabs.io:60000`
- **Adapter auth model in code:** proxy URL `http://<OXYLABS_KEY>@realtime.oxylabs.io:60000`
- **Special adapter behavior in code:** when `render=true|1|html` is passed in `extra_params`, adapter adds header `X-Oxylabs-Render: html`
- **Important note:** Oxylabs commonly uses username/password style credentials in docs; current adapter assumes a single combined credential string in `OXYLABS_KEY`
- **Operational fit:** high-end anti-bot / rendered HTML use cases
- **Observed runtime in this repo:** not live-verified
- **Cost sensitivity:** high
- **Status:** code-integrated, exact auth format still needs vendor-doc confirmation against current account credentials before activation
- **Activation rule:** do not enable until credential format is verified from docs/account console and one smoke test passes

---

## Channel guidance

## Etsy search HTML

Preferred testing order:
1. `scrapedo`
2. `scraperapi`
3. `webscrapingapi`
4. `scrapingbee`

Notes:
- search pages are usually easier than listing pages
- avoid expensive proxy tiers until cheap tier is proven unstable

## Etsy listing HTML

Current tested reality:
- `scrapingbee` is the most advanced configured provider for this target
- `premium_proxy=true` is already applied specifically to ScrapingBee
- current tested outcomes are still unstable on Etsy listing HTML

Recommended order for further validation:
1. ScrapingBee with stable one-URL smoke testing
2. ScraperAPI or WebScrapingAPI after docs validation
3. Scrape.do as lower-cost fallback
4. premium proxy vendors only after auth formats are verified

## Google SERP HTML

Important distinction:
- Google in this repo historically used a separate path in `google_niche_scraper.py`
- this included `searchapi`, `serpapi`, and a ScrapingBee Google-specific endpoint path
- do not assume Google success means generic HTML provider success on Etsy/eBay

## eBay search HTML

Prefer cheaper REST providers first.
Do not escalate to premium proxy providers until one provider fails consistently with a reproducible pattern.

---

## Activation checklist for any provider

Before enabling:
1. Confirm correct credential type in vendor docs / console.
2. Add secret to `.env.scrape.local`.
3. Run `python3 providers/doctor.py` and confirm `api_key_env -> OK`.
4. Inspect execution plan in `doctor.py` for the target channel/mode.
5. Run one single live smoke test on one representative URL.
6. Capture outcome type: success / timeout / provider auth / rate limit / target_404 / provider_500.
7. Only then move provider upward in routing order.

Never enable a provider solely because:
- the endpoint resolves by TCP
- the env var is present
- it worked for a different target family

---

## Cost control rules

1. Prefer `doctor.py` and execution-plan inspection before live tests.
2. Change only one parameter at a time.
3. Never batch test expensive providers before a stable profile is found.
4. Stop repeating the same failing request once the outcome pattern is clear.
5. For providers that bill aggressively or consume credits, test one URL only per profile revision.

---

## Current project truth snapshot

- **ScrapingBee:** best-integrated REST provider so far, but Etsy listing stability not yet proven.
- **Apify Proxy:** integration corrected; blocked by account plan for external proxy access.
- **Scrape.do:** inexpensive fallback, but not yet reliable for Etsy listing HTML in current tests.
- **ScraperAPI / WebScrapingAPI / ZenRows:** present in architecture, still need docs-verified activation.
- **Bright Data:** present in architecture, auth/env model is aligned with the repo, Phase 3 verification ledger exists, and both `base` and `country-us` controlled Etsy listing tests currently reproduce `HTTP 502`; treat as experimental until a success case is reproduced.
- **Oxylabs:** present in architecture, but exact auth model still needs validation against vendor/account credentials before activation.

---

## Recommended next implementation step

Create a small provider-by-provider verification ledger after each live test with these fields:
- date
- provider
- channel
- target URL family
- request profile
- result outcome
- credit impact / cost note
- activation decision

This should become the operational evidence base for changing provider order in `providers.yaml`.
