"use client";

import { useEffect } from "react";

/**
 * Hover-only text reachable without a mouse (PRO-569): an element with a title shows it in a tooltip
 * when it takes focus from the keyboard, 6px below it, until focus leaves or Escape. The mouse keeps
 * the browser's own title.
 */
export function TooltipController() {
  useEffect(() => {
    let tip: HTMLDivElement | null = null;
    let pointerAt = 0;
    const hide = () => {
      tip?.remove();
      tip = null;
    };
    const onPointer = () => {
      pointerAt = Date.now();
    };
    const onFocus = (event: FocusEvent) => {
      hide();
      const target = event.target instanceof HTMLElement ? event.target : null;
      const text = target?.getAttribute("title")?.trim();
      if (!target || !text || Date.now() - pointerAt < 500) return;   // focus from a click: the title shows on hover
      tip = document.createElement("div");
      tip.className = "tooltip";
      tip.setAttribute("role", "tooltip");
      tip.textContent = text;
      document.body.append(tip);
      const box = target.getBoundingClientRect();
      const widest = document.documentElement.clientWidth - tip.offsetWidth - 8;
      tip.style.left = `${window.scrollX + Math.max(8, Math.min(box.left, widest))}px`;
      tip.style.top = `${window.scrollY + box.bottom + 6}px`;
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") hide();
    };
    document.addEventListener("pointerdown", onPointer, true);
    document.addEventListener("focusin", onFocus);
    document.addEventListener("focusout", hide);
    document.addEventListener("keydown", onKey);
    return () => {
      hide();
      document.removeEventListener("pointerdown", onPointer, true);
      document.removeEventListener("focusin", onFocus);
      document.removeEventListener("focusout", hide);
      document.removeEventListener("keydown", onKey);
    };
  }, []);
  return null;
}
