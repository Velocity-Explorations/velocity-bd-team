# Top bar animation

9 November 2026, David

David wants a simple looping animation that fills all or part of the dashboard's top bar. This folder holds the brief for Claude Design and, once a design comes back, its export.

## How to use

1. Paste the prompt below into Claude Design on the Velocity account. It reads this folder from GitHub, since the repo is public.
2. Export the chosen design (its HTML and handoff note) into this folder through a pull request.
3. Ask Claude Code to build the chosen concept from this folder.

The two screenshots show the bar as it is today, logged out: [a 1440px window](current-1440.png) and [a 390px phone](current-390.png), where the bar wraps to three rows.

## Prompt for Claude Design

```text
Ideate a simple looping animation for the top bar of Velocity's BD dashboard, in the Velocity Theme.

The dashboard is the internal tool a small business development team uses all day to find, judge and answer US government research and defense calls (SBIR topics, BAAs, other transaction calls). Its top bar sits on every page. We want a little life in it: an animation that fills all of the bar, or part of it, and loops quietly.

Everything you need is in the public GitHub repo Velocity-Explorations/velocity-bd-team:
https://github.com/Velocity-Explorations/velocity-bd-team/tree/main/docs/design
To read a file as plain text, use https://raw.githubusercontent.com/Velocity-Explorations/velocity-bd-team/main/ followed by its path.

Read these first:
1. The bar today: docs/design/topbar-animation/current-1440.png (a 1440px window) and current-390.png (a phone, where the bar wraps to three rows, about 172px tall).
2. The Velocity Theme: docs/design/velocity-theme/README.md (the brand book) and tokens.css. The Velocity marks are in docs/design/velocity-theme/assets/Logos.
3. The dashboard's own tokens in dashboard/app/theme.css. The bar's styles are the .topbar rules near the top of dashboard/app/globals.css, and its markup is in dashboard/components/Shell.tsx.

The bar as built:
- 56px tall on a wide window, on the ground colour #1E1E1E, with a 2px rule along its foot.
- Left: the Velocity mark and "BD TEAM" in Chakra Petch capitals.
- Then the four sections: Home, Calls, Proposals and Automation, each with a line icon. Calls and Proposals carry yellow count badges. The open section is white and semibold, with a 2px yellow underline on the bar's foot.
- Right: an outlined Ask Grok button and the account button (a picture or initials, the person's name, and "Deciding").
- On narrower windows it wraps; on a phone it is three rows.

What we want: 6 to 8 distinct concepts, each running live in a faithful copy of the real bar (logo, sections, badges, active underline, Ask Grok, account), so we judge them in place and not on an empty strip.

For each concept give:
- A name and one sentence on the idea.
- Where it lives: the whole bar behind everything, one region (behind the logo, the empty stretch between the sections and Ask Grok, the 2px foot rule, the active underline), or the logo itself.
- The motion: what moves, the loop length, the easing, and how the loop joins without a visible seam.
- Its colours, by token name.
- What it shows with reduced motion (prefers-reduced-motion): a still frame that still looks finished.
- How it is built (CSS, SVG or canvas), roughly how heavy it is, and what it costs to run.
- How it behaves when the bar wraps on a phone.

Directions worth trying, though not the only ones: a slow sweep or scan line; a drifting dot grid or star field; contour or terrain lines; a signal trace or waveform; light travelling along the foot rule; a slow shift in the ground; the Velocity mark doing something small. Include at least one concept that carries information rather than decoration, for example a line that fills as the next scheduled scan approaches, or a brief pulse when new calls arrive, and say what data it would need.

Rules it has to keep:
- Calm. People look at this bar for hours, so nothing may pull the eye from the page below. Loops of about 8 to 30 seconds, slow movement, low contrast.
- One accent. Velocity yellow (#FFCB03) marks what matters: today, the open section and the count badges. The animation lives mostly in the greys (ground, surface, line, ink at low opacity). A concept that uses yellow uses very little of it and says why.
- Legible. Every label, badge and button keeps at least 4.5:1 contrast over every frame.
- Safe. Nothing flashes more than 3 times a second, and nothing large flickers.
- Light. Animate transform and opacity, or one small canvas. No video, no large images, no animation library. It pauses while the tab is hidden.
- Dark only. The dashboard has no light theme.
- Any words you add follow the theme's content rules, which means no en or em dashes.

Finish with:
- Your top two, and why.
- For each of the two: the exact HTML and CSS (or SVG or JS) a developer can drop into the bar, built on the tokens in dashboard/app/theme.css, with its reduced-motion version.
- A short handoff note: where each piece goes in the bar's markup, and anything a developer should check.

We will export the result into docs/design/topbar-animation/ in the repo, and Claude Code will build the chosen concept from there.
```
