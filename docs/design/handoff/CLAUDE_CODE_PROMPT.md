# First message for Claude Code

Paste this into a Claude Code session opened on `Velocity-Explorations/velocity-bd-team`, with this handoff folder copied to `docs/design/handoff/`.

---

You are building the BD Team dashboard redesign and the proposal workspace in this repo. The design is final and approved. Your job is to build it on the codebase as it is, following the repo's own rules in AGENTS.md. Each pull request gets its own Linear ticket, its own branch and failing tests first; the docs are updated alongside it; and it is squash-merged with the ticket id in its subject.

Read these first, in this order, and tell me what you understand before writing any code:

1. `docs/design/handover-discovery.md`: what exists today, at commit 65a5fce.
2. `docs/design/handoff/README.md`: the overview, every screen, the tokens and the open items.
3. `docs/design/handoff/docs/decisions.md`: where the design and the code disagree, and David's decisions.
4. `docs/design/handoff/docs/spec-updates.md`: the spec changes.
5. `docs/design/handoff/docs/build-plan.md`: the architecture and the 13 pull requests in order.

Then:

- **Start with PR 1:** merge `spec-updates.md` into `docs/design/dashboard-design-spec.md`. If `tests/test_design_brief.py` expects one-letter requirement prefixes, renumber VC, PW and DB on merge, and record the mapping in the Decision log row.
- **Take the pull requests in order.** Stop after each one and tell me what changed, what the tests cover, and anything in the design you could not match and why.
- **Treat the design files as the reference.** `docs/design/handoff/design/Review Queue Prototype.dc.html` is the working prototype; serve the `design/` folder over HTTP to open it. Recreate the screens in the dashboard's own components, using the tokens in `docs/design/handoff/velocity-theme/` rather than literals. Do not copy the HTML.
- **Keep the ledger rule:** the dashboard only reads and writes ledger rows. Anthropic, Google Drive and Slack are called by the worker and by `run.py`, never by the dashboard.
- **The AI slop scanner stays private:** call it from `AI_SLOP_SCAN`, and never commit its code, word lists or guidance text. Its result page must never say or imply that a text was or was not written by AI.
- **Before building the top bar and sign-in,** ask me the open items 1 and 2 in the README: the app's name in the top bar, and Google sign-in inside the dashboard versus IAP.
- **House rules:**
  - no en dash or em dash anywhere (write ranges with "to");
  - plain sentence-case labels;
  - status always written as a word;
  - nothing login-gated or sensitive (Vulcan SOF content, NSTXL member pages, CUI, credentials) in commits, fixtures, screenshots or logs.
