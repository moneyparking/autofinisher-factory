# Digital Product Factory v1

This module adds a normalized digital product build layer on top of Autofinisher.

Core contracts:
- `digital_product_spec.json`
- `artifact_manifest.json`
- `listing_packet.json`

Flow:
1. Create or generate product config
2. Compile it into `digital_product_spec.json`
3. Build or place product artifacts
4. Generate `artifact_manifest.json`
5. Compile `listing_packet.json`
6. Run QA before publish queue

This layer intentionally stays simple.
It does not try to automate Canva UX end-to-end.
It normalizes product truth, artifact truth, and listing truth so the monetization loop can stay compact and deterministic.
