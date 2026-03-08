# Operator Guide — Digital Product Factory

## How to run a product

```bash
cd digital_product_factory
python3 scripts/run_product.py <product_id>
# or by niche:
python3 scripts/run_product.py --niche-id 2026_adhd_digital_planner_v1 --product-kind planner
```

## Where outputs are stored

Generated files are written to:

`outputs/<product_slug>/`

Do not commit `outputs/`.

## Where publish packets are stored

The Etsy-ready packet is written to:

`outputs/<product_slug>/listing_packet_etsy.json`

## How to use `listing_packet_etsy.json`

- Copy-paste `title`, `description`, `feature_bullets`, `benefit_bullets`, and `tags` into the Etsy listing.
- Extended optional fields such as `description_intro`, `description_whats_included`, and `description_how_it_works` can be used as ready-made listing sections.
- `artifacts` contains the exact upload paths.
- `upload_order_hint` and `photo_sequence_hint` explain the suggested upload order.

## Manual operator steps

1. Run replay mode to review the current state:
   ```bash
   python3 scripts/replay_product.py --product-slug budget-spreadsheet
   ```
2. Open `listing_packet_etsy.json`.
3. Copy the relevant listing fields into Etsy.
4. Upload files in the order suggested by `upload_order_hint`.
5. Review preview assets (`master.png`, `mockup.png`) before publishing.

## How to run the integration check

```bash
python3 scripts/integration_check.py
```

## Replay mode (no rebuild)

```bash
python3 scripts/replay_product.py --product-slug budget-spreadsheet
```

Replay mode only reads the existing output folder. It never rebuilds artifacts.
