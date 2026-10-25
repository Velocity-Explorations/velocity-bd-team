# CoverSlide

The opening slide: logo and classification marking along the top, the briefing's name in the middle, the company line at the foot.

```html
<section class="vx-slide vx-slide--cover">
  <div class="vx-topbar">
    <img class="vx-logo" src="assets/Logos/velocity-lockup-white.png" alt="Velocity">
    <p class="vx-label vx-ink-secondary">Unclassified</p>
  </div>
  <div class="vx-cover-body">
    <p class="vx-eyebrow">Pipeline review</p>
    <h1 class="vx-title">BD Automation<br>Scans, Review and Triage</h1>
    <div class="vx-rule vx-rule--hero"></div>
    <p class="vx-lead">Document VX-0000</p>
    <p class="vx-body">26 October 2026 | Colorado Springs, CO</p>
  </div>
  <div class="vx-foot vx-foot--ruled"><p class="vx-small vx-ink-muted">Velocity Explorations, Inc.</p></div>
</section>
```

- Provide: the eyebrow (the event), a title of one or two lines, an identifier line (contract or document number), a date and place line, and the classification marking.
- `vx-slide--cover` draws both glows. Add no pictures.
- The title block sits on the left margin, centered top to bottom.
