# Color team: splitting the Writer into role agents

Proposal, 18 Nov 2026. **Nothing here is built.** The 9 Nov review agreed to aim for a color team of about twelve role
agents, with people doing only the final quality review and the vendor-facing work. It also agreed to pause new
drafting work until Shaun's color team write-ups arrive and David gives the go-ahead. Until then, the single Writer
stays as it is.

## Where the Writer is today

A pursuit runs as a list of steps (`drafting/steps.py`), each queued for the worker (`worker_jobs`):

1. Discovery
2. Opportunity summary
3. Alignment
4. Requirements and checklist
5. **Go or no-go** (a gate)
6. Outline
7. First draft
8. Compliance check
9. Reviews: external evaluator, second evaluator, Velocity leadership
10. Final checks
11. **Submit** (a gate)

Each step is one model call whose system prompt already names a role (`drafting/prompts.py`): a senior BD analyst, a
capture strategist, a capture manager, a proposal writer, the evaluators, a compliance reviewer. So the roles exist in
words, but one Writer plays them all in turn. No role keeps its own checklist, its own standards, or what it learned on
the last pursuit.

## The proposal

### 1. A role is a file

Each role gets a file, `drafting/roles/<role>.md`, holding:
- who it is and what it owns;
- what it reads;
- the one document it produces;
- its checklist;
- when it must stop and hand to a person.

A step names the role that runs it, and the prompt text moves out of `prompts.py` into the role files. The facts rule
(01 Company Reference only, `NEEDS FACT` for anything it lacks), the AI slop check, the page budget and the cost cap
apply to every role, as they do to every step now.

Shaun's write-ups set the real list. Here is a starting map from today's steps:

| Role | Owns | Today |
|---|---|---|
| Capture manager | the opportunity summary, the go or no-go brief, win themes | Discovery, Opportunity summary, Go or no-go |
| Capture strategist (blue team) | alignment, gaps and how to answer them | Alignment |
| Compliance manager | the requirements matrix, the checklist, both compliance passes | Requirements and checklist, Compliance check, part of Final checks |
| Proposal manager | the outline, the page budget per volume, the schedule and hand-offs | Outline |
| Technical volume writer | the technical approach | First draft |
| Management volume writer | management, staffing, schedule | First draft |
| Past performance writer | relevant contracts, from the Proposal Register and the library | First draft |
| Pricing volume analyst | the cost or price volume and its basis of estimate | none yet |
| Pink team | a storyboard review of the outline before writing starts | none yet |
| Red team | scoring the full draft as the evaluators will | Reviews: external and second evaluator |
| Production | formatting, page fit, the submission package | part of Final checks |
| Gold team | the leadership read before submission | Reviews: Velocity leadership |

### 2. Drafts pass through the pursuit, not from agent to agent

Every role reads the pursuit's files and saves its document in the pursuit's folder, as steps do now. When a role
finishes, the worker queues the next one, and `pursuit_events` keeps who did what and when.

A role never rewrites another role's document. It suggests changes, as Reviews does today (`step_changes`), and the
role that owns the document accepts or rejects them. A draft would move like this:

1. Outline (proposal manager), then a pink team review.
2. The volume writers, side by side, one worker job per volume.
3. The volumes assembled into Draft v1.
4. A compliance pass, then the red team's suggestions.
5. The owners' revisions, making Draft v2.
6. Production.
7. Gold team.

### 3. Two points stay with people

The 9 Nov review named two:

- **Final quality review.** A person reads the assembled final version and decides whether it goes. This is today's
  Submit gate, with the gold team's read in front of them. The Go or no-go gate also stays human, and a person still
  writes each opening paragraph (the `PERSON WRITES` rule).
- **Vendor-facing work.** Anything that speaks for Velocity outside the company: teaming partners, subcontractor quotes,
  questions to the contracting officer, registrations, and the submission itself. Agents draft these as checklist items
  (the email, the question list, the partner ask), and a person sends them.

## Open questions for Shaun and David

- The role list, and what each role signs off before the next starts.
- Whether the pricing analyst may see labor rates and past prices. Contract values are marked sensitive, so this may
  stay with a person.
- One model for every role, or a different one for some, such as the red team.
- Cost. Today a pursuit makes about one call per step. Volume writers and extra reviews multiply that, so the per-pursuit
  cap needs a new figure.
- How to judge it. Rerun the 4 Nov trial on a past winning topic with role agents and compare scores on the same eleven
  criteria.

## A first step, once approved

1. Move today's prompts into role files with no change in behavior, so the tests stay as they are.
2. Add the pink team review after the Outline.
3. Split the first draft into volume writers.

Each is one pull request.
