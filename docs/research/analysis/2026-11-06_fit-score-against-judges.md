# The fit score against the judges' verdicts

Date: 6 Nov 2026. Evidence for PR #133 and PR #135. Counts only: the ratings stay in the ledger, because this repo is public.

## Question

PR #128 ranked the Top 10 by fit score. Once both judges had named every open call's main work, did that order put the right calls first?

## Data

The live ledger on 6 Nov, 258 open calls, after both judges re-ran them with the new profile and the MAIN WORK line. Older `judgments` rows stay as history, so the newest and the one before it can be compared per call and judge.

| Verdicts, before to now | Yes | Maybe | No |
|---|---|---|---|
| Claude | 22 to 9 | 104 to 78 | 132 to 171 |
| Grok | 16 to 6 | 65 to 32 | 177 to 220 |

| Claude, Grok | Strong | Possible | Weak | Ruled out |
|---|---|---|---|---|
| yes, yes | 2 | 1 | 0 | 0 |
| yes, maybe | 2 | 1 | 0 | 0 |
| maybe, yes | 3 | 0 | 0 | 0 |
| yes, no | 2 | 1 | 0 | 0 |
| maybe, maybe | 22 | 6 | 1 | 0 |
| maybe, no | 13 | 16 | 15 | 2 |
| no, no | 0 | 0 | 122 | 49 |
| Total | 44 | 25 | 138 | 51 |

## Finding

The score rates a call's categories: its main work, customer, type, NAICS code, keywords and access. A verdict enters only through the cap when both judges say no. So a broad listing can score 95 with no yes from anyone.

- 35 of the 44 strong calls had no yes from either judge, and 13 of those had one judge saying no.
- All of the first six places in the fit-only Top 10 were maybe from both judges. Five were there because the listing hides its scope (cycle listings whose topics sit on a portal the scanner may not read, a notice with no scope, an attached statement of work, a members-only page). The sixth stays open until 2030.
- Only 2 of the 12 open calls with a yes reached the Top 10. One that both judges rated yes, closing within a month, ranked 50th.
- No call with a yes fell to weak or ruled out, so the two signals do not contradict each other at the low end.

## Decision

The Top 10 and each portal's top picks rank a yes from both judges first, then a yes from one, then the rest. Inside each group, calls due within 60 days come first, then the highest fit score, the nearest deadline and the newest (David, 6 Nov).

Needs review stays best fit first, so the broad listings are still seen there. A call open for years can still take a slot when too few calls with a yes close within 60 days.

## Not tested

Decided calls were not re-judged, so they carry no score and this run cannot check the score against the team's decisions. A trial on 13 decided calls that morning, with no ledger writes, put 4 of 4 pursued calls in strong and 5 of 8 not-relevant calls below it, but the judges saw those decisions in their examples, which flatters the result.
