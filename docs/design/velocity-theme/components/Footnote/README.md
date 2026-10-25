# Footnote

One line at the foot of a slide: a lead-in label and a sentence, or meta items, split by a `|` separator.

```html
<div class="vx-foot">
  <p class="vx-label-sm">Dependency</p><span class="vx-sep">|</span>
  <p class="vx-bar-text vx-ink-muted">Foundation must finish before the streams scale</p>
</div>
<div class="vx-foot">
  <p class="vx-meta">30 min briefing</p><span class="vx-sep">|</span><p class="vx-meta">30 min discussion</p>
</div>
```

- Inside a `vx-slide`, `vx-foot` pins the line 40px above the bottom edge. Outside one, use `vx-footnote` for the same row.
- Everything in it is `ink-muted`; the separator is `line`.
