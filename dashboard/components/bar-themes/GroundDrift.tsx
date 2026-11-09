"use client";

// Bar theme "ground-drift" (board concept 1f, Claude Design handoff). Two faint pools of light drift toward each other
// and back. Pure CSS motion.

import { useLayoutEffect, useRef } from "react";
import { phaseToClock, useTabHidden } from "./motion";

export function GroundDrift() {
  const hidden = useTabHidden();
  const a = useRef<HTMLDivElement>(null);
  const b = useRef<HTMLDivElement>(null);

  // Carry on from the frame the last bar showed (motion.ts, the themes' clock), before the first paint.
  useLayoutEffect(() => phaseToClock([a.current, b.current]), []);

  return (
    <div className="topbar-fx topbar-drift" aria-hidden="true" data-paused={hidden || undefined}>
      <div ref={a} className="topbar-drift-track topbar-drift-a">
        <div className="topbar-drift-pool" />
      </div>
      <div ref={b} className="topbar-drift-track topbar-drift-b">
        <div className="topbar-drift-pool" />
      </div>
    </div>
  );
}
