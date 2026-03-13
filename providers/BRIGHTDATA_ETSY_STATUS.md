# Bright Data Etsy status

Date: 2026-03-07

## Confirmed working

Bright Data is working in general with the new SSL certificate on port 33335.

Confirmed successful direct fetches:
- https://example.com -> 200
- https://httpbin.org/ip -> 200
- https://www.google.com -> 200

Confirmed successful provider-layer fetch:
- `providers/smoke_test.py --channel etsy_listing_html --url https://example.com --mode expensive --tier tier_3 --timeout 25 --json`
- result: `brightdata` success, HTTP 200, failover_count 0

## Etsy-specific status

Representative Etsy listing URL tested:
- https://www.etsy.com/listing/1682665810/digital-planner

Observed result through Bright Data:
- HTTP 502

Controlled variants tested:
- base auth + browser-like headers
- `country-us` + browser-like headers
- `country-us-state-ny` + browser-like headers

Observed result for all tested variants:
- HTTP 502
- no useful body content returned

## Conclusion

This is no longer a Bright Data integration problem.
It is an Etsy-target-specific failure under the current Bright Data proxy/request model.

Current honest status:
- Bright Data provider: working
- Bright Data certificate path: working
- general fetch path: working
- Etsy listing fetch path: not working yet

## Operational implication

Do not treat Etsy listing via Bright Data as ready for Phase 4 promotion yet.
The next step would require a different acquisition strategy, likely involving a heavier browser / render / session layer rather than more small proxy-flag permutations.
