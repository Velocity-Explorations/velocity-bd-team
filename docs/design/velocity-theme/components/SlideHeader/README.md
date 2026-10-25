# SlideHeader

The top of every content slide: eyebrow, title, optional subtitle, and the accent rule.

```html
<header class="vx-header">
  <p class="vx-eyebrow">Automation roadmap</p>
  <h2 class="vx-title">Phased Delivery Plan</h2>
  <p class="vx-body vx-subtitle">From scan to drafted proposal</p>
  <div class="vx-rule"></div>
</header>
```

- Provide: the eyebrow in any case (it is set in capitals), a Title Case title, and if needed a subtitle of a few words.
- The eyebrow is always `accent` and the title always `ink`. Nothing else in the header takes the accent.
- Follow it with `vx-content`, which starts 52px below the rule.
