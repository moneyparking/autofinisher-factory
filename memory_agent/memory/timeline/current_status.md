# Current Status

## Active state
- Fast pipeline is the current operating path.
- Batch target remains 15 approved niches.
- Slim-mode and budgeted external-request policy are active.
- Seed-level circuit breaker is active.

## Latest known refresh
- Refreshed at: `2026-03-04T14:35:32Z`
- Approved niches in latest batch snapshot: `1`
- Built packets in latest batch snapshot: `1`
- Top niche in current memory snapshot: `adhd cleaning checklist`

## Text command workflow
- If user says **"обновить память проекта"**, run `refresh_memory.py`.
- If user says **"перезапустить память проекта"**, run `bootstrap_memory.py`, then `refresh_memory.py`.
- If user says **"перезаписать память проекта"**, rebuild memory files from current repository state using `refresh_memory.py`.
