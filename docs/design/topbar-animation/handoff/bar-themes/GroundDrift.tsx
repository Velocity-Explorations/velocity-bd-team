'use client';

// dashboard/components/bar-themes/GroundDrift.tsx
// Bar theme "ground-drift" (board concept 1f).
// Two faint pools of light drift toward each other and back. Pure CSS motion.

import { useTabHidden } from './motion';

export function GroundDrift() {
  const hidden = useTabHidden();
  return (
    <div className="topbar-fx topbar-drift" aria-hidden="true" data-paused={hidden || undefined}>
      <div className="topbar-drift-track topbar-drift-a">
        <div className="topbar-drift-pool" />
      </div>
      <div className="topbar-drift-track topbar-drift-b">
        <div className="topbar-drift-pool" />
      </div>
    </div>
  );
}
