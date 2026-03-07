# Bright Data Phase 3

This document defines the Phase 3 activation workflow for Bright Data inside Autofinisher Factory.

Phase 3 scope:
- provider-specific verification workflow
- reproducible Bright Data test matrix
- evidence ledger for activation decisions
- MCP-ready interface planning for later remote server exposure

Phase 3 does **not** mean Bright Data is production-promoted.
It means Bright Data has a controlled activation path with repeatable evidence.

---

## Objectives

1. Verify Bright Data through the standard provider layer rather than one-off scripts.
2. Capture outcomes in a ledger that is safe to compare over time.
3. Test one representative target URL family at a time.
4. Keep Bright Data in controlled mode until a clean success profile is reproduced.
5. Define the future MCP facade as a consumer of the provider layer, not a replacement for it.

---

## Current Bright Data contract in repo

- Env auth: `BRIGHT_DATA_AUTH`
- Env endpoint: `BRIGHT_DATA_ENDPOINT`
- Expected auth shape: `<username>:<password>`
- Common username base example: `brd-customer-<ACCOUNT>-zone-<ZONE>`
- Optional routing flags are appended to the username segment:
  - `-country-us`
  - `-state-ny`
  - `-asn-56386`
  - `-ip-1.1.1.1`
- Current endpoint default: `brd.superproxy.io:33335`

---

## Standard verification runner

Use:

```bash
python3 providers/brightdata_phase3.py --json
```

This runner:
- reads `BRIGHT_DATA_AUTH`
- builds a controlled variant matrix
- calls the standard provider layer through `providers.smoke_test.build_smoke_report`
- writes the latest ledger file under `data/provider_verification/`

Default matrix:
1. base auth
2. `country-us`

Optional expansions:
- `--state ny`
- `--asn 56386`
- `--ip 1.1.1.1`

---

## Activation decision states

Use one of these states when reading the ledger:

- `experimental`
  - no clean success yet
  - Bright Data remains controlled-test-only
- `candidate_for_promotion`
  - at least one controlled profile succeeded cleanly
  - still requires repeated confirmation before routing promotion
- `promoted`
  - only after repeated success, cost review, and target-family confirmation

Current rule in repo:
- Phase 3 runner promotes only to `candidate_for_promotion`
- production promotion remains a later routing decision

---

## Evidence ledger fields

The ledger stores:
- generation timestamp
- provider
- channel
- representative URL
- mode
- tier
- timeout
- endpoint
- activation decision
- per-variant auth flags
- full report
- summarized outcome

This is the operational evidence base for changing provider order later.

---

## MCP-ready interface direction

A future remote MCP server should sit **above** the provider layer and expose narrow tools such as:

- `brightdata_fetch_html`
  - input: `url`, `channel`, optional `country/state/asn/ip`, optional `timeout_s`
  - output: normalized HTML + provider meta
- `brightdata_resolve_execution_plan`
  - input: `channel`, `mode`, optional `tier`
  - output: execution plan visible to operator tooling
- `brightdata_verify_profile`
  - input: representative URL + auth flags
  - output: smoke summary + ledger entry

The MCP server should not bypass `providers.registry.fetch()`.
It should consume the same provider contracts already used by runtime.

---

## ChatGPT / MCP note

For ChatGPT connectivity, the practical target is a **remote** MCP server or connector-facing service.
A local repo script is not sufficient by itself.
Therefore the sequence should be:

1. finish provider activation in repo
2. stabilize Bright Data verification and success criteria
3. wrap verified functions behind a remote MCP facade
4. connect ChatGPT to that remote endpoint
5. connect the same facade into Autofinisher system workflows

---

## Current Phase 3 exit criteria

Bright Data Phase 3 can be considered complete when all of the following are true:

1. `providers/doctor.py` shows Bright Data as OK
2. `providers/smoke_test.py --tier tier_3` works as the standard isolated path
3. `providers/brightdata_phase3.py` writes a ledger successfully
4. at least one controlled variant matrix has been run and saved
5. the activation decision is recorded explicitly
6. the MCP-ready interface shape is documented for the next layer

As of now, the remaining unknown is target success quality, not provider-layer wiring.
