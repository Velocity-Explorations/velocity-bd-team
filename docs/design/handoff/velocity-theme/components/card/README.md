# Card

The default card for the Velocity Theme from 26 Oct 2026 (dashboard design 7c). Use it for every metric card and content card in apps. Slides may keep the flat surface card.

## Anatomy

1. Label band: Chakra Petch 11px, weight 600, caps, letter-spacing 0.12em, #BEBEBE. Padding 10px 14px, a 1px #333333 rule below. A card that opens a page puts an arrow at the band's right.
2. Number: Inter Tight 30px bold. Yellow (#FFCB03) only for the count that needs the person (Needs review, To draft, Agent update requests); otherwise ink.
3. Description: Chakra Petch 12px, #959595, one short line saying what the number counts.

A content card keeps the label band and puts its body below it with padding 12px 14px 14px.

## Layout

Cards in a row share three grid rows through `grid-template-rows: subgrid`, so the band, the number and the description line up across the row whatever their length. The tallest label or description sets its row for every card; nothing is cut off. Cards share the row equally, 12px apart.

## Fill, border, shadow

- Fill: `--card-fill`, a 135deg gradient from #2C2C2C to #262626 to #212121, lit from the top left.
- Border: 2px #333333, radius 4px.
- Shadow: `--card-shadow`, 4px 6px 14px rgba(0,0,0,0.45), falling to the bottom right. It is the theme's only shadow and is used on cards alone.

## States

- Hover: lift 2px, border #757575, shadow 6px 10px 22px rgba(0,0,0,0.55). 140ms ease-out.
- Pressed: back to rest (no lift, rest shadow).
- Keyboard focus: a 2px #FFCB03 outline, offset 2px.
- Selected (the open view or filter): `--card-fill-selected`, a 2px ink border, the band filled #383838 with a #555555 rule, and a 3px accent bar along the bottom. Mark it with aria-pressed="true". Hover lifts it but keeps the ink border.
- Reduced motion: no lift and no transition.

## Rules

- Every card is a link or a button. A card with no action of its own links to its detail (a judge's score to Judges, a win rate to Results for that portal), so hover never promises a click that does nothing.
- A card that switches the view below it is a button with aria-pressed; a card that opens a page is a link with an arrow and an aria-label that says the count and where it goes.
- Status is a word in the label or description, never colour alone.
- No en or em dash; ranges use "to".

## Files

- `card.css`: the custom properties to add to tokens.css, and the reference rules.
- `tokens-app.css`: the other app tokens (tones, type, corners, controls, table, menus, dialogs).
- Other app components: button, field, menu, dialog, notice, badge, tag, table, top-bar, account-menu, view-cards, tooltip, each in components/.
- `tokens.json`: version 2 adds the card group and the 3px, 4px and 6px radii.
- `Velocity Theme Card.dc.html`: the specimen, with a row, every state, a content card and the spec.
