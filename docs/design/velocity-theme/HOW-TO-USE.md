# Velocity Theme: what is in this folder and how to use it

Open `index.html` in a browser to see the colors, type and every component. `README.md` is the brand book: the rules for color, type, layout and the logo.

## Files

| File or folder | What it is |
| --- | --- |
| `README.md` | Brand book: content rules, color, type, layout, shape, logo |
| `tokens.json` | Every color, type style, space, radius and size, with a usage note on each |
| `tokens.css` | The same tokens as CSS variables and type classes, with the web fonts |
| `tokens.dtcg.json` | The tokens in the W3C design tokens format, for Figma (Tokens Studio) or Style Dictionary |
| `components/` | `bundle.css` plus one folder per component: guidelines (`README.md`) and an example (`preview.html`) |
| `fonts/` | Web fonts (`.woff2`, Latin characters) used by `tokens.css` |
| `fonts/desktop/` | Full fonts (`.ttf`) to install on a computer: Inter Tight Regular, SemiBold, Bold; Chakra Petch Regular, Medium, SemiBold, Bold |
| `assets/Logos/` | The Velocity lockup and VX mark, white for dark backgrounds and ink for light ones |
| `licenses/` | SIL Open Font License for both typefaces |

## Web pages

Link `tokens.css`, then `components/bundle.css`, and use the `vx-` classes the way each component's `README.md` shows. Sizes are for a 1920×1080 slide; halve them for a 960-wide page.

## PowerPoint or Word

1. Install the seven fonts in `fonts/desktop/` (double-click each, then Install).
2. In PowerPoint: Design > Variants > Colors > Customize Colors, and set:

| Slot | Hex | Token |
| --- | --- | --- |
| Text/Background - Dark 1 | #1E1E1E | `ground` |
| Text/Background - Light 1 | #F5F5F5 | `ink` |
| Text/Background - Dark 2 | #262626 | `surface` |
| Text/Background - Light 2 | #BEBEBE | `ink-secondary` |
| Accent 1 | #FFCB03 | `accent` |
| Accent 2 | #757575 | `ink-muted` |
| Accent 3 | #434343 | `line-strong` |
| Accent 4 | #333333 | `line` |
| Accent 5 | #555555 | `ink-faint` |
| Accent 6 | #1A1A1A | `surface-recessed` |
| Hyperlink | #FFCB03 | `accent` |
| Followed Hyperlink | #BEBEBE | `ink-secondary` |

3. Design > Variants > Fonts > Customize Fonts: Inter Tight for both headings and body. Set labels and numbers in Chakra Petch by hand, in capitals with wide letter spacing.

## Google Slides

Inter Tight and Chakra Petch are both in Google Slides under Font > More fonts. Use the hex values above for the theme colors.

## Figma

Import `tokens.dtcg.json` with the Tokens Studio plugin to get the colors, sizes and type styles as variables and styles.
