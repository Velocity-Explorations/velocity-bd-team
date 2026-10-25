Velocity Theme is how Velocity Explorations presents its work: a near-black ground, white Inter Tight titles, Chakra Petch labels and numerals, square corners, and one yellow accent that marks what matters on each slide.

## Using this system

- Sizes are px on the 1920×1080 slide. On a 960-wide frame (a web page, or the deck's native PDF size), halve every size and space.
- In HTML, load `tokens.css`, then `components/bundle.css`. Type style classes (`vx-title`, `vx-body` and the rest) set face, size, weight and tracking; `bundle.css` sets their color and capitals; component classes (`vx-card`, `vx-steps` and the rest) lay them out. Each component's guidelines show its markup.
- In a deck that takes inline styles only, copy the values from the tables below. Nothing depends on the classes.
- Fonts: Inter Tight (400, 600, 700) and Chakra Petch (400, 500, 600, 700) ship in `fonts/` under the SIL Open Font License (texts in `licenses/`). Both are also on Google Fonts.

## Content

- Plain, short and specific. Lead with the fact. No hype, no exclamation marks, no emoji.
- Titles name the topic in Title Case and fit on two lines: "Phased Delivery Plan", "Roles and Responsibilities", "Risks and Assumptions".
- Every content slide carries an eyebrow of two to four words naming its section: "Meeting structure", "Delivery schedule", "Next steps". `vx-eyebrow` sets it in capitals.
- Bullets and card text: sentence case, one line where possible, no end periods.
- Numbers give a slide its structure: zero-padded agenda and step numbers (01, 02), milestone codes (M1 to M5), durations as numerals (12 months, 30 min).
- Dates: day, month spelled out, year. 24 October 2026.
- Separators: a middle dot between items on one line (Data access · Security · Governance), a vertical bar between meta items (30 min briefing | 30 min discussion), the word "to" for ranges (Months 3 to 9). No en or em dashes.
- Classification: mark the cover (top right) and the closing slide (under the subtitle). Add markings to other slides when the program requires them.

## Color

| Token | Value | Use |
| --- | --- | --- |
| `ground` | #1E1E1E | Every slide's background |
| `surface` | #262626 | Cards, rows, tiles, bars |
| `surface-recessed` | #1A1A1A | The quieter column of cards |
| `line` | #333333 | Card borders, hairlines, axes |
| `line-strong` | #434343 | Tag borders, later roadmap phases |
| `ink` | #F5F5F5 | Titles and primary text |
| `ink-secondary` | #BEBEBE | Supporting copy |
| `ink-muted` | #757575 | Labels, meta, footers (24px and up) |
| `ink-faint` | #555555 | Out-of-play chart items only |
| `accent` | #FFCB03 | Velocity yellow |
| `on-accent` | #1E1E1E | Text on an `accent` fill |

- One accent. `accent` marks things: eyebrows, the title rule, numerals, bullets, stat numbers. It fills at most one block per slide (the current phase or the current step) and never sets body copy.
- Text steps down from `ink` (titles, primary lines) to `ink-secondary` (supporting copy) to `ink-muted` (labels and meta at 24px and up). `ink-faint` is for chart items that are out of play, never for text a reader needs.
- Depth is `surface` on `ground` with a 2px `line` border. `surface-recessed` holds the column that matters less (out of scope, assumptions).
- The palette has no status colors. Say status in words.
- `glow-cool` and `glow-warm` are radial glows for the cover, section and closing slides only.

## Type

| Style | Face | Size, weight | Use |
| --- | --- | --- | --- |
| `vx-display` | Inter Tight | 80, 700, -0.024em | Section and closing titles |
| `vx-title` | Inter Tight | 64, 700, -0.024em | Slide and cover titles |
| `vx-kpi` | Inter Tight | 72, 700 | The number in a stat tile |
| `vx-heading` | Inter Tight | 44, 600 | Names in cards, stat values |
| `vx-lead` | Inter Tight | 34, 400, line 1.5 | Agenda items, statements |
| `vx-body` | Inter Tight | 28, 400, line 1.2 | Bullets, card and row text |
| `vx-small` | Inter Tight | 24, 400 | Second lines, footers |
| `vx-eyebrow` | Chakra Petch | 24, 600, 0.145em, caps | Above every title, `accent` |
| `vx-label` | Chakra Petch | 24, 600, 0.145em, caps | Section and card labels |
| `vx-numeral-lg` | Chakra Petch | 48, 700 | Agenda numbers |
| `vx-numeral` | Chakra Petch | 28, 600 | Milestone codes |
| `vx-meta` | Chakra Petch | 24, 500 | Times, cadences |

- Inter Tight for what a reader reads; Chakra Petch for what labels, counts or codes. The Typography view lists every style down to the 12px chart notes.
- Titles track at -0.024em. Chakra Petch capitals track at 0.145em, or 0.12em at 20px and below. Numerals are not tracked.

## Layout

- Canvas 1920×1080. Margins are `space-100` left, right and top, so content is 1720 wide.
- Content slide header: eyebrow at y=100, title `space-24` below it, accent rule (`rule-width` by `rule-weight`) `space-28` below the title, first content row `space-52` below the rule at y=310. A subtitle (`vx-body` in `ink-muted`) sits `space-12` under the title and pushes the rule down.
- Two columns: 844 + `space-32` + 844. Numbered lists: two columns of 820 with `space-80` between.
- Stack cards and rows in one column with `space-16`. A section label sits `space-24` above its content.
- The footer line sits `space-40` above the bottom edge. Cover and closing slides put a full-width `line` rule `space-20` above it.
- Four slide types: cover, content, section and closing. See the Slides components.

## Shape and depth

- Corners stay nearly square: `radius-card` (2px) for cards, tiles and bars, `radius-chip` (1px) for tags and badges. Chart markers are the only circles.
- Borders are `border` (2px): `line` on cards and rules, `line-strong` on tags and later roadmap phases, `accent` on the next phase.
- No shadows. No gradients other than the two glows.

## Iconography

- There is no icon set. Square bullets (`bullet`, `bullet-lead`), numerals and the arrows ↑ and → carry structure. Don't add icons or emoji.

## Logo

- `assets/Logos` holds the lockup (VX mark and VELOCITY) and the mark alone, each in white for dark grounds and in ink (#1E1E1E) for light ones.
- Cover: lockup top left on the margin at `logo-height` (36px), level with the classification marking. Closing: lockup centered above the title at `logo-height-closing` (40px).
- Use the white lockup on `ground`. Don't stretch, outline, recolor or place it on `accent`.
