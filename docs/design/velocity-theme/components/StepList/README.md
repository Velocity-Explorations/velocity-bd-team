# StepList

Numbered next steps: a square badge, a title and one line of detail, with hairlines between. The current step's badge is filled with `accent`.

```html
<ol class="vx-steps">
  <li class="vx-step--current">
    <span class="vx-step-badge vx-numeral-badge">01</span>
    <div class="vx-step-text">
      <p class="vx-lead-strong">Check the Sunday scan (M1)</p>
      <p class="vx-body">Runs at 22:00; the brief posts Monday at 09:00</p>
    </div>
  </li>
  <li>
    <span class="vx-step-badge vx-numeral-badge">02</span>
    <div class="vx-step-text"><p class="vx-lead-strong">Triage the review queue</p><p class="vx-body">Pursue, Not relevant, Submitted or Dismiss</p></div>
  </li>
</ol>
```

- One current step at most; the rest keep `surface` badges with `ink` numerals.
- Titles in `vx-lead-strong`, detail in `vx-body` (set to `ink-muted` by the list).
- The list is 1400px wide (`list-width`).
