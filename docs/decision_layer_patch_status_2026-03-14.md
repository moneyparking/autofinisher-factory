# Decision-layer targeted patch status (2026-03-14)

## Result

After adding the Etsy Ads decision-layer detector and rerunning only the two problem videos:

- WNQgc8NzLYc -> top_fms_score = 55.12 -> still v1_fail
- 0Xrx-OXQmd4 -> top_fms_score = 68.5 -> now v1-green

## Cluster summary

- hard_fail_count = 0
- v1_fail_count = 1
- target_fail_count = 3
- pass_count = 6

## Remaining v1_fail

- WNQgc8NzLYc

## Interpretation

The decision-layer patch successfully upgraded 0Xrx-OXQmd4 to a v1-green output, but WNQgc8NzLYc still does not reach the v1 floor. This supports the current contract choice: profitability/ROAS without a sufficiently strong operational decision-layer remains v1_fail.
