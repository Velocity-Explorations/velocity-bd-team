"use client";

// The top bar's animated layer (David, 9 Nov 2026; Claude Design handoff, docs/design/topbar-animation/handoff/
// bar-themes). Picks the person's theme and renders it as the first child of .topbar. The ids, the default and the
// settings copy are in lib/barthemes.ts, where the server checks a saved theme too.

import { useEffect } from "react";
import { resolveBarTheme } from "@/lib/barthemes";
import { DeepField } from "./DeepField";
import { GroundDrift } from "./GroundDrift";
import { LineClear } from "./LineClear";
import { rememberBarTheme, useLastBarTheme } from "./motion";

export function TopbarFx({ theme }: { theme?: string | null }) {
  const t = resolveBarTheme(theme);
  useEffect(() => rememberBarTheme(t), [t]);
  // key: switching themes unmounts the old one, which cancels its animations
  if (t === "line-clear") return <LineClear key={t} />;
  if (t === "ground-drift") return <GroundDrift key={t} />;
  return <DeepField key={t} />;
}

/**
 * The loading screen's copy of the bar draws the theme the last page's bar showed, so moving between pages keeps the
 * animation going. The loading screen cannot wait for the person's profile. Nothing on a first load.
 */
export function TopbarFxCarryOver() {
  const theme = useLastBarTheme();
  return theme ? <TopbarFx theme={theme} /> : null;
}
