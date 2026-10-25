# ClassificationCallout

A full-width card that states the classification of the work in `accent`, with one line of handling guidance.

```html
<div class="vx-card vx-card--list">
  <p class="vx-label">Classification</p>
  <p class="vx-marking">UNCLASSIFIED</p>
  <p class="vx-body vx-ink-secondary">Public portal data only; nothing login-gated</p>
</div>
```

- Provide: the marking exactly as the program writes it, and one sentence.
- Follow it with a `vx-section` of reminders: a `vx-label`, then a `vx-bullets vx-bullets--inset` list.
