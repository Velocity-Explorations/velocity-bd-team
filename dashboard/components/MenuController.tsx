"use client";

import { useEffect } from "react";

/** Which boxes in a menu are ticked, to tell whether closing it changed anything. */
function ticks(menu: HTMLDetailsElement): string {
  return [...menu.querySelectorAll<HTMLInputElement>("input[type=checkbox]")].map((box) => (box.checked ? "1" : "0")).join("");
}

/**
 * The menus' behaviour (PRO-558): one open at a time, closed by a click outside or Escape, and a
 * menu marked data-apply-on-close (the bar's Portals) submits its form when it closes changed.
 */
export function MenuController() {
  useEffect(() => {
    const closeAllBut = (keep: Element | null) => {
      for (const menu of document.querySelectorAll<HTMLDetailsElement>("details.menu[open]")) {
        if (menu !== keep && !menu.contains(keep)) menu.open = false;
      }
    };
    const onClick = (event: MouseEvent) => {
      const target = event.target instanceof Element ? event.target : null;
      closeAllBut(target?.closest("details.menu") ?? null);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeAllBut(null);
    };
    const onToggle = (event: Event) => {
      const menu = event.target;
      if (!(menu instanceof HTMLDetailsElement) || !menu.matches("details.menu[data-apply-on-close]")) return;
      if (menu.open) {
        menu.dataset.ticks = ticks(menu);
      } else if (menu.dataset.ticks !== undefined && ticks(menu) !== menu.dataset.ticks) {
        menu.querySelector("form")?.requestSubmit();
      }
    };
    document.addEventListener("click", onClick);
    document.addEventListener("keydown", onKey);
    document.addEventListener("toggle", onToggle, true);   // toggle does not bubble
    return () => {
      document.removeEventListener("click", onClick);
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("toggle", onToggle, true);
    };
  }, []);
  return null;
}
