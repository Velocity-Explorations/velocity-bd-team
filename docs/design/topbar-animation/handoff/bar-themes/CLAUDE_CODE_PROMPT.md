Build the top bar themes for the BD dashboard from the design handoff in this repo.

WHERE THINGS ARE
- Handoff (spec and code): docs/design/topbar-animation/handoff/bar-themes/
  Start with README.md there. It is the build spec. The .tsx, .ts and .css files next to it are drop-in code.
- Design reference (the approved animations, running live): docs/design/topbar-animation/Top Bar Animation Concepts.dc.html
  The three themes are concepts 1i (Deep field, the default), 1j (Line clear) and 1f (Ground drift). Each runs in a copy of the bar at 1440 px and 390 px, with its spec next to it. The "Bar themes" section shows the settings control.
- The bar today: dashboard/components/Shell.tsx, the .topbar rules in dashboard/app/globals.css, tokens in dashboard/app/theme.css.

WHAT TO BUILD
1. Read README.md in the handoff fully before writing code.
2. Copy the components into dashboard/components/bar-themes/ and append bar-themes.css to globals.css after the .topbar rules, as the README says.
3. Map the four tokens at the top of bar-themes.css (--fx-ink, --fx-line, --fx-accent, and --muted in the settings control) to the real names in theme.css. The handoff was written without access to theme.css, so the names are guesses with hex fallbacks. Keep the fallbacks.
4. Add a nullable barTheme preference to the person's profile, using however the dashboard already stores per-person settings. Valid values: deep-field, line-clear, ground-drift. Null means deep-field. Validate on the server.
5. Render <TopbarFx theme={...} /> as the first child of the .topbar element in Shell.tsx.
6. Add <BarThemeSetting> to the personal settings page. If that page already has a radio or option card component, use it and keep only the data and copy from the handoff. Saving must switch the bar at once, with no reload.
7. Check the foot rule and the active underline against the README's Layering section, and adjust if the real markup differs from what it assumes.
8. Do not change anything else in the bar: not the layout, spacing, colours or copy.

Where the handoff and the real code disagree (class names, how the foot rule is drawn, how settings are saved), follow the real code and keep the handoff's behaviour. List each such decision in your summary.

HOW TO CHECK YOUR WORK AGAINST THE DESIGN
Serve the repo root locally (for example: npx serve .) and open the board in a browser next to the running dashboard. If you have browser automation (Playwright or similar), use it to take screenshots; otherwise describe what you checked.

For each theme (deep-field, line-clear, ground-drift):
- Compare the dashboard bar at 1440 px with that concept's 1440 px bar on the board, and at 390 px with the 390 px bar. They should match in where the motion lives, how faint it is, its speed and its timing. The board is the reference for look and feel; README.md is the reference for exact numbers.
- Every label, icon, count badge, the yellow active underline, Ask Grok and the account button must paint above the animation.
- Compare the timings with the README's tables:
  Deep field: star layers move one tile in 90, 60 and 40 s; the first craft appears about 4 s after load; one craft at a time; 5 to 16 s of empty sky between crossings.
  Line clear: the bar fills in about 60 s, holds 3 s, breaks apart left to right, and the loop is about 70 s at 1440 px.
  Ground drift: 30 s each way, alternating.
- Reduced motion: emulate prefers-reduced-motion in DevTools and use the "Show reduced motion" button on the board. Deep field: still stars, no craft. Line clear: a still, full row. Ground drift: still pools behind the mark and the account. The settings help text changes.
- Hide the tab for a minute and come back: nothing has jumped.
- Contrast: sample the brightest frame behind silver labels (#BEBEBE). It must stay at or above 4.5:1. README.md lists the expected worst cases.
- Work through every item under "Checks before merging" and "Acceptance" in README.md, and report pass or fail for each.

WHEN DONE
Summarise: the files changed; the token names you mapped; how barTheme is stored and saved; any place you departed from the handoff, and why; and the result of each check, with screenshots if you took them.
