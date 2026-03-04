# Entity: network_constraints

- Main bottleneck: external scraper/network instability.
- Current baseline: timeout 30s, 2 retries, bounded budgets.
- Batch should not stall on a single seed.
- `network_failed` and `partial_ok` are acceptable seed-level outcomes in fast mode.
