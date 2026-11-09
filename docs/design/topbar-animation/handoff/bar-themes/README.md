# Top bar themes: handoff for Claude Code

The top bar gets a quiet animated layer behind its contents. Each person picks one of three themes in their personal settings. **Deep field is the default.**

| Theme id | Name | Board concept | What it does |
| --- | --- | --- | --- |
| `deep-field` | Deep field | 1i | Faint stars drift left; now and then a shuttle, satellite, rocket or UFO crosses |
| `line-clear` | Line clear | 1j | Faint blocks stack across the bar, then break apart, fade and start again |
| `ground-drift` | Ground drift | 1f | Two soft pools of light drift slowly across the bar |

Board: `Top Bar Animation Concepts.dc.html`. It is the visual reference; this folder is the build spec.

## Files

All components go in `dashboard/components/bar-themes/`.

| File | What it is |
| --- | --- |
| `TopbarFx.tsx` | Theme ids, default, settings copy, and the switch that renders the chosen theme |
| `DeepField.tsx` | Deep field: star layers and the craft scheduler; tunables in `DEEP_FIELD` |
| `deep-field-craft.tsx` | The four craft glyphs (20 x 10 SVG, `currentColor`) |
| `LineClear.tsx` | Line clear: layout builder and Web Animations runner; tunables in `LINE_CLEAR` |
| `GroundDrift.tsx` | Ground drift: two elements, CSS motion |
| `motion.ts` | Shared `rng`, `useReducedMotion`, `useTabHidden` |
| `BarThemeSetting.tsx` | The settings control (radio group) |
| `bar-themes.css` | Append to `dashboard/app/globals.css` after the `.topbar` rules |
| `markup-examples.tsx` | Reference only: Shell and settings placement |

No new packages, images or fonts. No animation library.

## Build steps

1. Copy the `.tsx` and `.ts` files into `dashboard/components/bar-themes/`.
2. Append `bar-themes.css` to `dashboard/app/globals.css` after the existing `.topbar` rules.
3. Map the tokens at the top of the CSS to `dashboard/app/theme.css`: `--fx-ink` (near white text, #F5F5F5), `--fx-line` (hairline, #333333), `--fx-accent` (yellow, #FFCB03), and `--muted` in the settings control (silver, #BEBEBE). Keep the hex fallbacks.
4. Add the preference to the person's profile (below).
5. In `Shell.tsx`, render `<TopbarFx theme={profile.barTheme} />` as the first child of the element with `className="topbar"`.
6. On the personal settings page, add `<BarThemeSetting value={profile.barTheme} onChange={save} />`.
7. Run the checks at the end.

## The preference

- Field: `barTheme` on the person's profile or preferences record (`bar_theme` in the database if it uses snake case). Type: text, nullable.
- Values: `deep-field`, `line-clear`, `ground-drift`. `null` means the default.
- Read it wherever Shell already loads the person for the account button, and pass it to `<TopbarFx>`.
- `resolveBarTheme()` turns `null`, empty or unknown values into `deep-field`, so a theme can be retired later without a migration.
- On change: save, and update the value Shell reads at once (optimistic update or a revalidate), so the bar switches without a reload. `<TopbarFx>` keys each theme by id, so switching unmounts the old one and cancels its animations.
- To change the default for everyone, change `DEFAULT_BAR_THEME` in `TopbarFx.tsx`. People who never chose keep following it.
- Validate on the server against the three ids.

## Settings control

- Label: **Top bar animation**.
- Help text: "A quiet loop behind the top bar. It pauses when the tab is hidden." With reduced motion on: "Your system is set to reduce motion, so the bar shows a still frame of the theme you pick."
- Options, in this order, with these descriptions (also in `BAR_THEMES`):
  - Deep field: Faint stars drift behind the bar. Now and then a shuttle, satellite, rocket or UFO crosses.
  - Line clear: Faint blocks stack across the bar, then break apart and start again.
  - Ground drift: Two soft pools of light drift slowly across the bar.
- The chosen option has a yellow 1px border; focus shows the theme's yellow focus ring. If the settings page already has an option or radio card component, use it instead of the CSS here.
- The bar itself is the preview: the choice applies as soon as it is saved.

## Shared rules (all themes)

- **Layering.** `.topbar` gets `position: relative` and `isolation: isolate` (if it is already `sticky` or `fixed`, keep that and add `isolation`). `.topbar-fx` is `position: absolute; inset: 0; z-index: -1`, so it paints above the bar's background and below every label, icon, badge, button and the yellow active underline. Bar content must not set a negative `z-index`. If the 2px foot rule is a child element, give it `z-index: -2`.
- **Clipping.** Only `.topbar-fx` has `overflow: hidden`. Do not add it to `.topbar`; menus would be cut off.
- **Colour.** Only the ink token at low opacity, over the ground (#1E1E1E). No yellow in any theme.
- **Reduced motion.** Each theme shows a still frame that looks finished (details per theme below). The hook follows OS changes live.
- **Tab hidden.** Every animation pauses while `document.hidden` is true, and resumes where it stopped.
- **Cost.** Transform and opacity only, on the compositor. No per-frame JavaScript. No layout work while running.
- **Safety.** Nothing flashes or flickers; no large area changes brightness quickly.

## Deep field (`deep-field`, default)

Three layers of faint stars drift slowly left behind everything. Every 5 to 16 s one craft crosses at a steady speed: a delta wing shuttle, a satellite, a rocket or a UFO, chosen at random.

#### Stars

| Layer | Tile | Stars per tile | Radius | Ink opacity | One tile in | Speed |
| --- | --- | --- | --- | --- | --- | --- |
| Far | 320 px | 20 | 0.6 px | 14% | 90 s | 3.6 px/s |
| Mid | 480 px | 12 | 0.8 px | 20% | 60 s | 8 px/s |
| Near | 640 px | 6 | 1.1 px | 24% | 40 s | 16 px/s |

- Each tile is a 172 px tall SVG used as a CSS mask on an element filled with `--fx-ink`, so the colour stays a token.
- Star positions come from a seeded PRNG, so server and client render the same markup and there is no hydration mismatch.
- The element is one tile wider than the bar and moves left by exactly one tile per loop (`linear`, `infinite`). The last frame equals the first, so the loop has no seam.
- On the 56 px wide bar, only the top 56 px of each tile shows. On the phone (three rows, about 172 px) the whole tile shows.

#### Craft

One craft at a time. After it leaves the bar, the sky stays empty for a random 5 to 16 s, then the next is picked. The first appears 4 s after load.

| Craft | Chance | Crossing at 1440 px | Direction | Path | Ink opacity |
| --- | --- | --- | --- | --- | --- |
| Shuttle | 30% | 22 s | left to right | climbs 3 px over the crossing | body 22%, engine 14%, trail up to 10% |
| Satellite | 25% | 24 s | either | fixed lane at y 6, above every label | head 45%, 30 px trail |
| Rocket | 23% | 13 s | left to right | straight | body 22%, trail up to 12% |
| UFO | 22% | 30 s | either | bobs 2.5 px, three times per crossing | saucer 22%, dome 14% |

- Lane: random y between 4 px and the bar height minus 12 px. On the phone that covers all three rows.
- Crossing time scales with bar width: base seconds times `clamp(width / 1440, 0.75, 1.25)`. A 390 px phone bar uses 0.75, so a shuttle crosses it in 16.5 s.
- Every craft starts 60 px off one edge and ends 60 px off the other, so it never appears or disappears inside the bar.
- Movement is linear (a steady speed reads as travel, not as a UI transition). No easing, no bounce.
- Motion uses `element.animate()` with `transform` only. The craft element is removed when it lands.
- To change the mix, edit `DEEP_FIELD.craft`. To add a craft, add a type to `CraftType`, a glyph in `deep-field-craft.tsx` and an entry in `DEEP_FIELD.craft`. Keep new glyphs at 20 x 10, facing right, at 22% ink or below.

#### Colours

Only the ink token (#F5F5F5) at low opacity, over the ground (#1E1E1E). No yellow; yellow stays reserved for the open section, the count badges and today.

#### Contrast

Worst cases, silver label text (#BEBEBE) over the brightest pixel behind it:

- Ground alone: 9.0:1.
- Near star, ink 24% (about #4B4B4B): 4.7:1.
- Craft body, ink 22% (about #484848): 4.8:1.
- Satellite, ink 45%: only flies at y 6, above all labels, which start at about y 12.

Badges and the Ask Grok button have opaque fills or borders and are unaffected. White semibold labels (#F5F5F5) stay above 7:1 over every frame.

#### Reduced motion

`prefers-reduced-motion: reduce` shows the star field still and renders no craft. It still looks finished: the stars are just there. The hook listens for changes, so switching the OS setting takes effect without a reload.

#### Tab hidden

When `document.hidden` is true, `<DeepField>` sets `data-paused`: the star drift pauses, any craft in flight pauses where it is, and the timer for the next craft is cleared. On return, the craft resumes and a new timer starts.

#### Cost

- Three star elements with CSS `transform` animations, run on the compositor. Each is a single layer.
- At most one craft element, animated with the Web Animations API, also on the compositor.
- No per-frame JavaScript. One `setTimeout` between crossings.
- About 5 KB of source before minification. The star masks are built once per mount (about 40 small circles in all).

#### Safety

Nothing flashes or flickers. The fastest movement is the rocket at about 110 px/s, a 20 px glyph at 22% ink. No large area changes brightness.

#### Reduced motion and pause

Reduced motion: stars hold still and no craft is rendered. Tab hidden: star drift pauses (`data-paused`), a craft in flight pauses where it is, and the timer for the next one is cleared; on return the craft resumes and a new timer starts.

## Line clear (`line-clear`)

Faint blocks drift in from the left and stack against the right edge until the whole bar is full. The full bar holds, then breaks apart from left to right, each cell drifting, turning slightly and fading. After a short empty pause it starts again.

#### Layout

- The bar is split into strips two cells tall: `round(height / 56)` strips. The wide 56 px bar is one strip of 28 px cells; the 172 px phone bar is three strips of 28 px cells.
- Columns: `floor(width / cell)`, rounded down to even. The stack is flush right; any leftover column sits under the left edge fade.
- Each strip is filled right to left with three shapes that tile a two-cell strip exactly: O (2 x 2), a pair of I pieces (2 x 4), or an interlocking L and J (2 x 4). Choice is from a seeded PRNG, so the same width always gives the same sequence.
- Strips are interleaved, so on the phone all three rows fill together.
- At 1440 px: 50 columns, about 100 cells and 30 pieces.

#### Timing (one loop)

| Phase | Length |
| --- | --- |
| Fill | about 60 s at any width: a new piece every `min(4, 60 / pieces)` s (about 2 s at 1440 px, 4 s on a phone) |
| Each piece | fades in 160 px short of its place, then slides in over 3.2 s, ease out `cubic-bezier(0.2, 0.7, 0.2, 1)`, no bounce; the fade takes the first 45% of the slide |
| Hold | 3 s, full bar |
| Break | runs left to right over 1.4 s; each cell drifts up to 20 px, turns up to 18 degrees, shrinks to 70% and fades over 3.6 s |
| Rest | 2.8 s, empty |

Loop is about 70 s at 1440 px. Every cell is invisible at the reset, so there is no seam.

#### Colour and contrast

Cell fill: ink at 2%. Cell edge: 1px, ink at 4.5%. Over the ground that is about #222222 and #262626. Silver labels stay above 8:1 over every frame. No yellow, and no flash when the row clears.

#### Build and cost

- `buildLineClear(width, height)` is pure and builds every cell with its own keyframe list, once per size.
- One `element.animate()` per cell, `iterations: Infinity`, transform and opacity only. About 100 elements at 1440 px, 180 at 2560 px.
- Measured after mount and on resize (debounced 150 ms). A resize rebuilds the layout and restarts the loop from empty; that is expected.
- Client only: it renders an empty layer on the server, so there is nothing to hydrate.

#### Reduced motion and pause

Reduced motion: no animations start, so every cell shows in place: a still, full row of faint blocks. Tab hidden: every cell animation pauses.

## Ground drift (`ground-drift`)

Two faint pools of light drift toward each other across the ground and back, so the bar is never quite flat.

#### Motion

- Two radial pools, 640 x 256 px, centred above the bar (top -100 px). One starts behind the mark, the other behind the account.
- Each moves 45% of the bar width toward the other over 30 s, then back, `cubic-bezier(0.45, 0, 0.55, 1)`, `alternate`, `infinite`. Speed is zero at both ends, so the turn is invisible. Full loop 60 s.

#### Colour and contrast

Ink at 4.5% at the centre of each pool, fading to nothing. The brightest point is about #262626; silver labels stay above 8:1.

#### Build and cost

Pure CSS: two animated elements, two pools. Under 1 KB. Server rendered; no measuring.

#### Reduced motion and pause

Reduced motion: the pools rest at their start, behind the mark and behind the account. Tab hidden: `data-paused` pauses both.

## Phone (bar wraps to three rows, about 172 px)

- Deep field: star tiles are 172 px tall, so stars fill all three rows; craft lanes cover all three; crossings scale to 0.75 of the 1440 px time.
- Line clear: three strips fill together.
- Ground drift: the pools are taller than the bar, so they read as soft columns across all three rows.

## Checks before merging

1. Each theme at 1440 px: the motion is behind every label, icon, badge, the yellow underline, Ask Grok and the account button.
2. Each theme at 390 px (three rows).
3. Switch themes in settings: the bar changes at once with no reload, and the old theme leaves nothing behind (no stray animations in the Animations panel).
4. A person with no saved value, and one with an unknown value, both get Deep field.
5. Reduced motion emulated in DevTools: Deep field still with no craft; Line clear a still full row; Ground drift still pools. The settings help text changes.
6. Hide the tab for a minute and return: nothing has jumped.
7. Resize the window across the wrap points: Line clear rebuilds; Deep field and Ground drift adapt with no seam.
8. Open the account menu and every other bar popover: nothing is clipped.
9. No hydration warnings.
10. Performance panel: composited frames only; no long tasks or layout while running.
11. Every token resolves to theme.css, not the fallback.

## Acceptance

- At a glance the bar looks as it does today; the motion is noticed only when looked for.
- Every label keeps at least 4.5:1 contrast on every frame of every theme.
- No visible seam in any loop.
- Reduced motion shows a still, finished frame for every theme.
- Animation pauses while the tab is hidden.
- The chosen theme persists across sessions and devices (it lives on the profile).
