"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";

/** What a row click ignores: its own links, buttons, menus and fields. */
const CONTROLS = "a, button, input, select, textarea, summary, details, label";

/**
 * The tables' behaviour (PRO-572). A judge's note button ([data-panel]) opens and closes the row's
 * reasons panel; a panel's close button hands focus back to what opened it. A person's note button
 * ([data-note-tip]) shows their notes beside their vote (see the effect below). A row with data-href
 * (Home's Top 10) opens that address on a click outside its controls, or on Enter. A row marked
 * data-focus (Calls, Top 10, opened from Home) is scrolled to about 140px from the top and takes focus.
 */
export function TableController() {
  const router = useRouter();
  const pathname = usePathname();
  const search = useSearchParams();

  // A person's notes beside their vote (David, 16 Nov 2026): the button shows its box beside it on hover or keyboard
  // focus, and a click keeps the box open until a second click, a click elsewhere or Escape. The box is fixed to the
  // window and placed from the button each time, so a table that scrolls sideways cannot clip it; with no room on the
  // right it goes under the button.
  useEffect(() => {
    let open: { button: HTMLElement; tip: HTMLElement; kept: boolean } | null = null;
    let closing: number | undefined;
    const buttonOf = (target: EventTarget | null) => (target instanceof Element ? target.closest<HTMLElement>("[data-note-tip]") : null);
    const within = (node: EventTarget | null) => Boolean(open && node instanceof Node && (open.button.contains(node) || open.tip.contains(node)));
    const place = () => {
      if (!open) return;
      const { button, tip } = open;
      const box = button.getBoundingClientRect();
      const width = document.documentElement.clientWidth;
      const height = document.documentElement.clientHeight;
      let left = box.right + 8;
      let top = box.top - 6;
      if (left + tip.offsetWidth > width - 8) {
        left = Math.max(8, Math.min(box.left, width - tip.offsetWidth - 8));
        top = box.bottom + 6;
      }
      tip.style.left = `${left}px`;
      tip.style.top = `${Math.max(8, Math.min(top, height - tip.offsetHeight - 8))}px`;
    };
    const hide = () => {
      window.clearTimeout(closing);
      if (!open) return;
      open.tip.hidden = true;
      open.button.setAttribute("aria-expanded", "false");
      open = null;
    };
    const show = (button: HTMLElement, keep: boolean) => {
      window.clearTimeout(closing);
      const tip = document.getElementById(button.dataset.noteTip ?? "");
      if (!tip) return;
      const kept = keep || (open?.button === button && open.kept);
      if (open && open.button !== button) hide();
      open = { button, tip, kept };
      tip.hidden = false;
      button.setAttribute("aria-expanded", "true");
      place();
    };
    const onOver = (event: PointerEvent) => {
      const button = buttonOf(event.target);
      if (button) show(button, false);
      else if (within(event.target)) window.clearTimeout(closing);   // onto the box: it stays to be read
    };
    const onOut = (event: PointerEvent) => {
      if (!open || open.kept || !within(event.target) || within(event.relatedTarget)) return;
      window.clearTimeout(closing);
      closing = window.setTimeout(hide, 150);   // time to move from the button onto the box
    };
    const onClick = (event: MouseEvent) => {
      const button = buttonOf(event.target);
      if (button) {
        if (open?.button === button && open.kept) hide();
        else show(button, true);
      } else if (open && !open.tip.contains(event.target instanceof Node ? event.target : null)) {
        hide();
      }
    };
    const onFocus = (event: FocusEvent) => {
      const button = buttonOf(event.target);
      if (button && button === event.target) show(button, false);
    };
    const onBlur = (event: FocusEvent) => {
      if (open && !open.kept && event.target === open.button && !within(event.relatedTarget)) hide();
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || !open) return;
      const { button, tip } = open;
      const inside = document.activeElement instanceof Node && tip.contains(document.activeElement);
      hide();
      if (inside) button.focus();
    };
    const onMove = () => place();
    document.addEventListener("pointerover", onOver);
    document.addEventListener("pointerout", onOut);
    document.addEventListener("click", onClick);
    document.addEventListener("focusin", onFocus);
    document.addEventListener("focusout", onBlur);
    document.addEventListener("keydown", onKey);
    window.addEventListener("scroll", onMove, true);
    window.addEventListener("resize", onMove);
    return () => {
      hide();
      document.removeEventListener("pointerover", onOver);
      document.removeEventListener("pointerout", onOut);
      document.removeEventListener("click", onClick);
      document.removeEventListener("focusin", onFocus);
      document.removeEventListener("focusout", onBlur);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("scroll", onMove, true);
      window.removeEventListener("resize", onMove);
    };
  }, []);

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
