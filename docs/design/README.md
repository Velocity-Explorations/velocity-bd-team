# Dashboard redesign brief

Everything needed to redesign the BD triage dashboard in the Velocity Theme, kept in the repo so that Claude Design on the Velocity account can read it from GitHub. The repo is public, and nothing here is login-gated.

| Part | What it is |
| --- | --- |
| [dashboard-design-spec.md](dashboard-design-spec.md) | Every requirement and decision behind the dashboard, with IDs (Q1, C1, F1 and so on), how the theme fits, and the open design questions |
| [dashboard-snapshot/](dashboard-snapshot/README.md) | Today's seven pages as static HTML with their real markup and styling, and ten screenshots |
| [velocity-theme/](velocity-theme/README.md) | The Velocity Theme design system: brand book, tokens, fonts, logos and components |
| [dashboard-build-prompts.md](dashboard-build-prompts.md) | Prompt 0 for Claude Design, then prompts 1 to 5 for Claude Code to build the design |

## Reading order for a design

1. The spec, all of it. A redesign keeps every requirement; only the look is open.
2. The snapshot's README and screenshots, then its pages for exact markup and content.
3. The theme's [README.md](velocity-theme/README.md) (the brand book) and [HOW-TO-USE.md](velocity-theme/HOW-TO-USE.md), then [tokens.json](velocity-theme/tokens.json) and the components.
4. Prompt 0 in the build prompts, which lists the artboards to make.

Where the spec and the theme disagree, the spec decides behaviour and wording and the theme decides the look. One rule holds over both: no en dash or em dash anywhere, and ranges are written with "to".

## Where the design goes

Claude Code runs on David's own login, which cannot open designs on the Velocity account. Export the finished design (its HTML or handoff bundle, with the handoff note) into `docs/design/redesign/` through a pull request; build prompts 1 to 5 read it there.

## About these copies

- The theme is David's Velocity-Theme.zip of 8 Oct 2026 with two changes. The example text in the component previews, guidelines and tokens came from an internal slide deck and now uses this project's own content, and ranges are written with "to" instead of an en dash. Colours, type, sizes, fonts, logos and component markup are unchanged.
- The snapshot was captured on 25 Oct 2026 from a copy of the ledger holding only public-portal calls, with sample decisions by Analyst A and Analyst B. Vulcan SOF is left out because its pages sit behind a login.
- The spec and prompts began as Claude Docs on 25 Oct 2026. These files are now the ones to keep current.
