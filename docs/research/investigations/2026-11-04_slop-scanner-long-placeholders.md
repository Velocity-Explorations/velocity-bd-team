# The AI slop scanner misses long placeholders

Found on 2026-11-04, in the final version of the second drafting trial run of the day.

## What happened

The placeholder sweep (`placeholder_counts` in drafting/steps.py) found 81 open placeholders in the final version.
The AI slop scanner's open-item findings (family `prop_open_item`) found 77. The four it missed were the four
longest: 216, 217, 240 and 247 characters, one PERSON WRITES, one NEEDS INPUT and two NEEDS EVIDENCE. Every
placeholder up to 205 characters was found, so the scanner's open-item pattern stops at a length limit of about
210 characters. The scanner is private; its code stays out of this repo.

## Why it matters

Final checks keeps Approve and continue disabled until the newest scan of the final version says Ready, and Ready
needs no open items in the scan. A final version whose only open items are long placeholders would read Ready while
the sweep still lists them. The Submit gate's Placeholders check uses the sweep, so the miss would show there, one
step late.

## Fix options

1. Count open items in drafting/slop_gate.py with the repo's own placeholder pattern on the scanned text, and
   require zero for Ready. The gate's rule then lives in this repo.
2. Raise the length limit in the private scanner.

## Resolution

Option 1, on 4 Nov (David's choice). `slop_gate.with_missed` sweeps the scanned text with the patterns the Submit gate
counts with (PLACEHOLDER, OTHER_NOTE and FACT_POINTER in drafting/steps.py) and adds each placeholder no open-item
finding covers as a finding of its own, marked `"source": "placeholder sweep"`. `run_scan` applies it, so the worker's
scans, the pipeline, the check command and the saved slop_scan.json all carry it, and the dashboard lists the added
items with the rest. A finding covers a placeholder on its line when one starts the other: the scanner reports its
line as text and cuts its matches at 120 characters. On the 4 Nov final version the sweep added exactly the four
missed placeholders, and the verdict went from 77 open items to 81.
