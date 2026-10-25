# StatTile

A tile for one figure: a label, then the value, with an optional unit line.

```html
<div class="vx-stats">
  <div class="vx-stat"><p class="vx-label">Portals</p><p class="vx-kpi">11</p><p class="vx-body">scanned weekly</p></div>
  <div class="vx-stat"><p class="vx-label">First scan</p><p class="vx-heading">24 October 2026</p></div>
</div>
```

- `vx-kpi` (72px, `accent`) for the one number the slide is about; `vx-heading` (44px, `ink`) for the rest. One `vx-kpi` per slide.
- Tiles size to their content and sit 48px apart in `vx-stats`.
