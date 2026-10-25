# Card

A bordered `surface` panel for one person, statement or list: the building block of most content slides.

```html
<div class="vx-grid">
  <div class="vx-card">
    <p class="vx-label vx-accent">Technical lead</p>
    <p class="vx-heading">BD Team</p>
    <p class="vx-body vx-ink-secondary">Scans, reviews and proposal drafts</p>
  </div>
  <div class="vx-card vx-card--list vx-card--recessed">
    <p class="vx-label">Out of scope</p>
    <ul class="vx-bullets vx-bullets--muted vx-body vx-ink-secondary">
      <li>Portals that block automated reading</li>
    </ul>
  </div>
</div>
```

- `vx-card` (32px padding): a label, then a heading or statement, then a line.
- `vx-card--list` (36px): a label, then a bullet list.
- `vx-card--row`: one line in `vx-body` with a `vx-meta` at the right (meetings, cadences). Stack rows in `vx-stack`.
- `vx-card--compact` (20px by 24px): two short lines, such as a risk or a report and its basis.
- `vx-card--recessed`: add it to the cards in the column that matters less, with `ink-secondary` text and `--muted` bullets.
- Side by side in `vx-grid` (32px gap); stacked in `vx-stack` (16px gap). Cards in a row share a height.
- Role labels: `accent` for our side, `ink-secondary` for a partner's, `ink-muted` for a section.
