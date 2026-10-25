# ContentSlide

The working slide: eyebrow, title and accent rule at the top, content from y=310, an optional footnote at the foot.

```html
<section class="vx-slide">
  <header class="vx-header">
    <p class="vx-eyebrow">Weekly cycle</p>
    <h2 class="vx-title">Scan to Decision</h2>
    <div class="vx-rule"></div>
  </header>
  <div class="vx-content">
    <!-- one layout of components: a vx-grid of cards, a vx-section with a list, a roadmap -->
  </div>
  <div class="vx-foot"><p class="vx-meta">30 min briefing</p><span class="vx-sep">|</span><p class="vx-meta">30 min discussion</p></div>
</section>
```

- Provide: an eyebrow, a title, and the content inside `vx-content`.
- One idea per slide. `accent` fills at most one block on it.
- Keep everything inside the 100px margins; nothing bleeds.
