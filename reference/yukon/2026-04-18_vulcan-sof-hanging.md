# Vulcan SOF Scanner Hanging — Root Cause

**Date**: 2026-04-18
**Trigger**: Scan run #7 hung for 3+ days (PID 33979), never progressed past Vulcan SOF portal

## Root Cause

`wait_for_load_state("networkidle")` never completes on Angular SPAs like Vulcan SOF. The Angular app continuously fires XHR/WebSocket requests, so Playwright's "networkidle" condition (no requests for 500ms) is never met.

## Fixes Applied

1. **Replaced all `networkidle` with `domcontentloaded`** in `vulcan_sof.py` — the primary fix
2. **Added cookie persistence** (`data/vulcan_cookies.json`) to skip OTP on repeat logins
3. **Added per-portal timeout in `main.py`** via `ThreadPoolExecutor` — 300s for Playwright portals, 120s for HTTP scrapers
4. **Hardened subprocess calls** with `TimeoutExpired` and `FileNotFoundError` catches for `gog` CLI

## Key Takeaway

Never use `networkidle` with Angular/React SPAs. Use `domcontentloaded` and explicit `wait_for_timeout()` instead.

## Files

- `scanner/portals/vulcan_sof.py` — rewritten with all fixes
- `scanner/main.py` — ThreadPoolExecutor timeout wrapper
