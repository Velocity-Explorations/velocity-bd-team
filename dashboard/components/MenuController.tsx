"use client";

import { useEffect } from "react";

/** What arrow keys move between inside an open menu. */
const ITEMS = "a[href], button:not([disabled]), input:not([disabled]):not([type=hidden]), select:not([disabled])";

/** Whether any box differs from the page as served, the filter now applied. Comparing with the served
 *  state, not with the boxes when the menu opened, keeps a quick tick from racing the toggle event. */
function changed(menu: HTMLDetailsElement): boolean {
  return [...menu.querySelectorAll<HTMLInputElement>("input[type=checkbox]")].some((box) => box.checked !== box.defaultChecked);
}

function itemsOf(menu: HTMLDetailsElement): HTMLElement[] {
  const body = menu.querySelector(".menu-body");
  return body ? [...body.querySelectorAll<HTMLElement>(ITEMS)] : [];
}

/**
 * The menus' behaviour (PRO-558, PRO-569): one open at a time, closed by a click outside or Escape.
 * Focus moves into a menu when it opens (to the chosen item, else the first), the arrow keys, Home
 * and End move between its items, and Escape hands focus back to the menu's button. A menu marked
 * data-apply-on-close (the bar's Portals) submits its form when it closes changed.
 */
export function MenuController() {
  useEffect(() => {
    const openMenus = () => [...document.querySelectorAll<HTMLDetailsElement>("details.menu[open]")];
    const closeAllBut = (keep: Element | null) => {
      for (const menu of openMenus()) {
        if (menu !== keep && !menu.contains(keep)) menu.open = false;
      }
    };
    const onClick = (event: MouseEvent) => {
      const target = event.target instanceof Element ? event.target : null;
      closeAllBut(target?.closest("details.menu") ?? null);
    };
    const onKey = (event: KeyboardEvent) => {
      const open = openMenus();
      if (!open.length) return;
      const holding = open.filter((menu) => menu.contains(document.activeElement)).pop();
      if (event.key === "Escape") {
        closeAllBut(null);
        holding?.querySelector<HTMLElement>(":scope > summary")?.focus();
        return;
      }
      if (!holding || !["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
      const items = itemsOf(holding);
      if (!items.length) return;
      event.preventDefault();
      const at = items.indexOf(document.activeElement as HTMLElement);
      const next =
        event.key === "Home" ? 0
        : event.key === "End" ? items.length - 1
        : event.key === "ArrowDown" ? (at + 1) % items.length
        : (at - 1 + items.length) % items.length;
      items[next].focus();
    };
    const onToggle = (event: Event) => {
      const menu = event.target;
      if (!(menu instanceof HTMLDetailsElement) || !menu.matches("details.menu")) return;
      if (menu.open) {
        const items = itemsOf(menu);
        (items.find((item) => item.matches(".active, [aria-current], :checked")) ?? items[0])?.focus({ preventScroll: true });
      } else if (menu.matches("[data-apply-on-close]") && changed(menu)) {
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
