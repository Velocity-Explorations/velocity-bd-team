# PriorityMatrix

Value against complexity: four named quadrants, numbered markers, and a legend naming each marker with its scores.

```html
<div class="vx-matrix">
  <div class="vx-chart">
    <div class="vx-quad vx-quad--tl"><p class="vx-quadrant">Easy wins</p><p class="vx-micro-note">High value / low complexity</p></div>
    <div class="vx-quad vx-quad--tr"><p class="vx-quadrant">Strategic initiatives</p><p class="vx-micro-note">High value / high complexity</p></div>
    <div class="vx-quad vx-quad--bl vx-quad--low"><p class="vx-quadrant">Low-value quick</p><p class="vx-micro-note">Low value / low complexity</p></div>
    <div class="vx-quad vx-quad--br vx-quad--low"><p class="vx-quadrant">Deprioritize</p><p class="vx-micro-note">Low value / high complexity</p></div>
    <span class="vx-dot vx-marker" style="left: 20%; top: 40%">1</span>
    <p class="vx-axis vx-axis-x">Complexity →</p>
    <p class="vx-axis vx-axis-y">Value ↑</p>
  </div>
  <div>
    <p class="vx-legend-title">Feature legend</p>
    <div class="vx-legend-rows">
      <div class="vx-legend-row"><span class="vx-dot vx-dot--legend vx-micro">1</span><span class="vx-legend">Google sign-in</span><span class="vx-data">V 3.40 · C 1.80</span></div>
    </div>
  </div>
</div>
```

- Ticks: `vx-tick vx-tick-x` at `left` 0, 25, 50, 75 and 100% (1 to 5), and `vx-tick vx-tick-y` at the same `top` values from the bottom.
- Place each marker with inline `left` and `top` percentages on a 1 to 5 scale: left = (complexity - 1) / 4, top = 1 - (value - 1) / 4.
- Excluded items: `vx-dot--excluded` on the marker and `vx-legend-row--excluded` on its legend row.
- The top pair of quadrants is worth doing and takes `accent`; `vx-quad--low` turns the bottom pair grey.
- The plot is 696px tall (`chart-height`) and the legend 460px wide (`legend-width`) when the chart fills a slide.
