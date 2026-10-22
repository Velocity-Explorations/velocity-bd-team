# SAM.gov Checkpoint Auto-Clear Bug

**Date**: 2026-04-20
**Status**: Fixed

## Problem

After a successful resumed SAM.gov fetch, the checkpoint file was never deleted — even though all selected ptypes completed successfully. This left stale checkpoint files in `data/checkpoints/` indefinitely.

## Root Cause

In `scanner/portals/sam_gov.py`, the `_fetch_ptype()` function's page loop has two exit conditions:

1. **Data exhausted**: `offset >= total` or `len(opps_raw) < PAGE_SIZE` → sets `completed = True`
2. **Page budget exhausted**: `pages_attempted >= max_pages` → loop exits but `completed` stays `False`

The auto-clear condition at the end of `fetch()` checks `len(completed_ptypes) == len(active_ptypes)`. Since ptypes capped by `max_pages` were never added to `completed_ptypes`, the equality never held and the checkpoint was never cleared.

**Impact**: With velocity profile defaults (`YUKON_SAM_MAX_PAGES=2`), any ptype with >200 records triggers this — which is most ptypes (Sources Sought: 136, Solicitation: 354 observed).

## Fix

Added an explicit `pages_attempted >= max_pages` check after the pagination loop body that sets `completed = True` with a log line: `"page budget (N) reached, treating as complete for this run"`.

**File**: `scanner/portals/sam_gov.py` around line 355

```python
if pages_attempted >= max_pages:
    log.info(f"SAM.gov [{ptype_label}]: page budget ({max_pages}) reached, treating as complete for this run")
    completed = True
    break
```

## Validation

Full end-to-end test with 3 ptypes (s, r, o), sequential mode, SIGTERM-interrupted first run, then resumed:
- Checkpoint persisted correctly with `completed_ptypes=['s']` after interrupt
- Resume skipped 's', fetched 'r' and 'o'
- Both 'r' and 'o' hit page budget → marked complete
- Auto-clear fired: `"checkpoint cleared after successful completion"`
- `data/checkpoints/` empty after run

## Key Line References

| Location | What |
|----------|------|
| `sam_gov.py:350-355` | Original completion check (data exhausted only) |
| `sam_gov.py:356-359` | New page-budget completion check |
| `sam_gov.py:239-241` | Auto-clear condition |
| `sam_gov.py:170-185` | `_collect()` → `_persist_checkpoint()` flow |
