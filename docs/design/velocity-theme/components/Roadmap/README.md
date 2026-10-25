# Roadmap

A delivery plan as stacked rows: a phase block naming the phase and its months, then a bar naming the work and its parts.

```html
<div class="vx-roadmap">
  <div class="vx-phase vx-phase--current">
    <div class="vx-phase-block"><p class="vx-micro">Foundation</p><p class="vx-fine">Months 1 to 3</p></div>
    <div class="vx-phase-bar"><p class="vx-bar-text">Portal scanning and the ledger</p><p class="vx-caption">Portal adapters · Keyword filter · Slack alerts</p></div>
  </div>
  <div class="vx-phase vx-phase--next">
    <div class="vx-phase-block"><p class="vx-micro">Stream 1</p><p class="vx-fine">Months 3 to 9</p></div>
    <div class="vx-phase-bar">
      <p class="vx-bar-title">Review and Triage</p>
      <div class="vx-tags"><span class="vx-tag vx-caption">Judges</span><span class="vx-tag vx-caption">Tags</span></div>
    </div>
  </div>
  <div class="vx-phase">…</div>
</div>
```

- `vx-phase--current` (solid `accent`) once, `vx-phase--next` (`accent` outline) once; later phases stay plain with `line-strong` borders.
- Phase labels in `vx-micro`, months in `vx-fine` with "to" (Months 3 to 9).
- Bars carry a `vx-bar-title` and either a `vx-caption` line (parts split by middle dots) or a row of tags.
- Close the slide with a Footnote naming the dependency.
