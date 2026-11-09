'use client';

// dashboard/components/bar-themes/motion.ts
// Shared helpers for the bar themes.

import { useEffect, useState } from 'react';

/** Small deterministic PRNG, so server and client render identical output. */
export function rng(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** True when the OS asks for reduced motion. Follows changes live. */
export function useReducedMotion() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const q = window.matchMedia('(prefers-reduced-motion: reduce)');
    const set = () => setReduced(q.matches);
    set();
    q.addEventListener('change', set);
    return () => q.removeEventListener('change', set);
  }, []);
  return reduced;
}

/** True while the tab is hidden, so animations can pause. */
export function useTabHidden() {
  const [hidden, setHidden] = useState(false);
  useEffect(() => {
    const set = () => setHidden(document.hidden);
    set();
    document.addEventListener('visibilitychange', set);
    return () => document.removeEventListener('visibilitychange', set);
  }, []);
  return hidden;
}
