"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";

/** What a row click ignores: its own links, buttons, menus and fields. */
const CONTROLS = "a, button, input, select, textarea, summary, details, label";

/**
 * The tables' behaviour (PRO-572). Note buttons ([data-panel]) open and close a row's reasons or
 * notes panel; a panel's close button hands focus back to what opened it. A row with data-href (Home's
 * Top 10) opens that address on a click outside its controls, or on Enter. A row marked data-focus
 * (Calls, Top 10, opened from Home) is scrolled to about 140px from the top and takes focus.
 */
export function TableController() {
  const router = useRouter();
  const pathname = usePathname();
  const search = useSearchParams();
  useEffect(() => {
    const callRow = (panel: HTMLElement): HTMLElement | null => {
      const id = panel.dataset.for;
      return id ? panel.parentElement?.querySelector<HTMLElement>(`tr[data-call-id="${CSS.escape(id)}"]`) ?? null : null;
    };
    const setOpen = (panel: HTMLElement, open: boolean) => {
      panel.hidden = !open;
      for (const button of document.querySelectorAll<HTMLElement>(`[data-panel="${CSS.escape(panel.id)}"]`)) {
        button.setAttribute("aria-expanded", String(open));
      }
      const row = callRow(panel);
      const anyOpen = [...(panel.parentElement?.querySelectorAll<HTMLElement>(`tr.panel-row[data-for="${CSS.escape(panel.dataset.for ?? "")}"]`) ?? [])]
        .some((p) => !p.hidden);
      row?.classList.toggle("panel-open", anyOpen);
    };
    const onClick = (event: MouseEvent) => {
      const target = event.target instanceof Element ? event.target : null;
      if (!target) return;
      const opener = target.closest<HTMLElement>("[data-panel]");
      if (opener) {
        const panel = document.getElementById(opener.dataset.panel ?? "");
        if (panel) setOpen(panel, panel.hidden);
        return;
      }
      const closer = target.closest<HTMLElement>("[data-close-panel]");
      if (closer) {
        const panel = document.getElementById(closer.dataset.closePanel ?? "");
        if (!panel) return;
        setOpen(panel, false);
        document.querySelector<HTMLElement>(`[data-panel="${CSS.escape(panel.id)}"]`)?.focus();
        return;
      }
      const link = target.closest<HTMLElement>("tr[data-href]");
      if (link && !target.closest(CONTROLS)) router.push(link.dataset.href ?? "/");
    };
    const onKey = (event: KeyboardEvent) => {
      const row = event.target instanceof HTMLElement ? event.target : null;
      if (event.key === "Enter" && row?.matches("tr[data-href]")) router.push(row.dataset.href ?? "/");
    };
    document.addEventListener("click", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("click", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [router]);

  // On every arrival, a page that marks a row to focus has it scrolled into view and focused.
  useEffect(() => {
    const focus = document.querySelector<HTMLElement>("tr[data-focus]");
    if (!focus) return;
    window.scrollTo({ top: focus.getBoundingClientRect().top + window.scrollY - 140 });
    focus.focus({ preventScroll: true });
  }, [pathname, search]);
  return null;
}
