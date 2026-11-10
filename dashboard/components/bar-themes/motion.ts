"use client";

// Shared helpers for the top bar themes (Claude Design handoff, docs/design/topbar-animation/handoff/bar-themes).

import { useEffect, useState, useSyncExternalStore } from "react";

/** Small deterministic PRNG, so server and client render identical output. It lives with Deep field's planets. */
export { rng } from "@/lib/sky";

/** True when the OS asks for reduced motion. Follows changes live. */
export function useReducedMotion() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const q = window.matchMedia("(prefers-reduced-motion: reduce)");
    const set = () => setReduced(q.matches);
    set();
    q.addEventListener("change", set);
    return () => q.removeEventListener("change", set);
  }, []);
  return reduced;
}

/** True while the tab is hidden, so animations can pause. */
export function useTabHidden() {
  const [hidden, setHidden] = useState(false);
  useEffect(() => {
    const set = () => setHidden(document.hidden);
    set();
    document.addEventListener("visibilitychange", set);
    return () => document.removeEventListener("visibilitychange", set);
  }, []);
  return hidden;
}

// ---------------------------------------------------------------- the themes' clock

// Not in the handoff (9 Nov 2026): every dashboard page draws its own top bar, and so does the loading screen between
// pages, so a theme is drawn afresh on every move. Each theme starts its loop at this clock rather than at zero, so the
// new bar carries on from the frame the old one showed. The clock stops while the tab is hidden, as the animations do,
// so a return does not jump either. A reload starts it from zero.

let banked = 0;
let since: number | null = null;
let watching = false;

function watch(): void {
  if (watching || typeof document === "undefined") return;
  watching = true;
  since = document.hidden ? null : performance.now();
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      if (since !== null) banked += performance.now() - since;
      since = null;
    } else if (since === null) {
      since = performance.now();
    }
  });
}

/** Milliseconds the dashboard has been visible since this page loaded. */
export function fxClock(): number {
  watch();
  return banked + (since === null ? 0 : performance.now() - since);
}

/**
 * Moves the CSS animations on these elements (and, with `subtree`, everything inside them) to the clock, so a bar
 * drawn again shows the frame the last one did.
 */
export function phaseToClock(elements: Iterable<Element | null>, subtree = false): void {
  const now = fxClock();
  for (const el of elements) {
    for (const a of el?.getAnimations({ subtree }) ?? []) a.currentTime = now;
  }
}

// ---------------------------------------------------------------- the last theme shown

let lastTheme: string | null = null;
const listeners = new Set<() => void>();

/** Remembers the theme the bar shows, for the loading screen's copy of the bar. */
export function rememberBarTheme(theme: string): void {
  if (theme === lastTheme) return;
  lastTheme = theme;
  listeners.forEach((l) => l());
}

/** The theme the bar last showed in this tab, or null before any page has drawn one (and on the server). */
export function useLastBarTheme(): string | null {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => lastTheme,
    () => null,
  );
}
