# Another client's profile: irrelevant NAICS matches reaching review

**Date**: 2026-05-06
**Trigger**: 23 of 28 pending review opps for another Yukon client were completely irrelevant: matching NAICS but zero keyword relevance (pesticide training, spacecraft engineering, AI/ML services, etc.)

## Root Cause

Three compounding issues in the scanner pipeline:

### 1. No keyword gate for NAICS-matched opps (`scanner/scanner/filter.py`, lines 106-111)

```python
if opp_naics:
    if opp_naics not in profile.naics:
        return False
    # ← passes immediately, no keyword check
else:
    # keyword matching only happens when opp has NO NAICS
```

Since SAM.gov queries by NAICS code, every returned opp already has a matching NAICS → every opp auto-passes the filter.

### 2. Scorer safety net unreachable (`scanner/scanner/profile_scorer.py`, line 194)

```python
if kw_score < 2.0 and naics_score < 5.0:
    composite = min(composite, 1.5 if has_negative else 2.5)
```

Since NAICS always scores 10.0 for matched opps, `naics_score < 5.0` is never true → the cap never fires.

### 3. Broad keyword "training" inflates scores

That profile's keyword list includes bare "training" (position 4). This matches any opp containing "training" regardless of domain ("Pesticide Applicator Training", "EHV Hot Stick Training", etc.), inflating keyword scores from 1.0 to ~3.0, pushing composites to 5.3.

## Score Composition (for reference)

Weights for that profile:
- `keyword_fit` (scoreTech): **50%**
- `naics_match` (scoreEcho): **20%**
- `vehicle` (scoreVehicle): **15%**
- `kb_match` (scorePast): **15%**

Individual scorers:
- `_score_keyword_fit`: searches title+description for profile keywords, rank-weighted. Returns 1.0 if no match.
- `_score_naics_match`: 10.0 exact match, 7.0 partial (4-digit prefix), 2.0 none, 5.0 no data.
- `_score_vehicle_fit`: maps solicitation type to score (Solicitation=8.0, RFI=5.0, etc.)
- `_score_kb_match`: overlap between profile KB docs and opp text. 2.0 baseline.
- `_score_urgency`: display only, not in composite.

## Recommended Fixes

1. **Add keyword gate to filter.py**: Even when NAICS matches, require at least one profile keyword hit before passing.
2. **Fix scorer gate**: Change `kw_score < 2.0 and naics_score < 5.0` to just `kw_score < 2.0` — remove NAICS exemption.
3. **Replace broad "training" keyword** with compound phrases: "leadership training", "management training", "executive training".
4. **Generate calibration.json** for that profile (currently missing), so it learns from rejected opps.

## Resolution

Bulk-marked 23 opps as `not_valid` with `reviewed_by = 'claude-bulk-review'`. Confirmed none belonged to Velocity profile (zero NAICS overlap between that client and Velocity). Scanner pipeline fixes not yet implemented.
