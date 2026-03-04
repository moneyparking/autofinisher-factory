# SPEC_dashboards

## TL;DR for agents

Dashboards are read-only consumers of batch outputs, monitoring artifacts, and compact publish summary metadata.

They should prefer compact summary fields for navigation and use detailed monitoring artifacts only when deeper diagnosis is needed.

## Primary dashboard sources

### Fast navigation layer

- `publish_packets/summary.json`

Expected fields:

- `built_count`
- `items`
- `monitoring.reference_summary_path`
- `monitoring.reference_alerts_path`
- `monitoring.winner_yield`
- `monitoring.avg_fms_ratio_winners`
- `monitoring.avg_sold_ratio_winners`
- `monitoring.alerts_count`
- `monitoring.alerts_levels`

### Deep monitoring layer

- `data/batch_monitoring/reference_batch_summary.json`
- `data/batch_monitoring/reference_alerts.json`
- `data/batch_monitoring/batch_kpi_history.json`

### Per-niche detail layer

- `data/validated_niches/items/*.json`
- `data/winners/*.json`

## Dashboard sections

### 1. Batch overview

Show:

- batch id
- approved/winners count
- built count
- winner yield
- current alert count
- highest alert severity

### 2. Yield & quality card

Show:

- `winner_yield`
- `avg_fms_ratio_winners`
- `avg_sold_ratio_winners`
- alert severity color

### 3. Alerts panel

Source:

- `reference_alerts.json`

Display:

- `level`
- `code`
- `message`

### 4. Trend chart

Source:

- `batch_kpi_history.json`

Plot:

- `winner_yield`
- `avg_fms_ratio_winners`
- optional dynamic threshold overlays

### 5. Winner vs candidate comparison

Source:

- `reference_batch_summary.json`

Display:

- winner ratios
- candidate ratios
- delta interpretation

## Rendering rules

- Use compact summary values for landing pages.
- Use monitoring artifacts for diagnostic drill-downs.
- Do not recompute ratios in the dashboard layer.
- Treat field names as stable contracts.

## Current real example

Current compact monitoring block in `publish_packets/summary.json` includes:

- `winner_yield = 0.5`
- `avg_fms_ratio_winners = 1.0`
- `avg_sold_ratio_winners = 1.0`
- `alerts_count = 1`
- `alerts_levels = ["critical"]`

This is sufficient for a top-level batch health card.
