"use client";

// Home's two top 10s as tabs (David, 7 Nov 2026): the calls to respond to now, and the umbrellas and announcements to
// watch. Both tables render on the server, so a tab shows at once; the address keeps the open tab (/?top=watch), so a
// link or a reload opens the same one. Arrow keys move between the tabs. Fit ratings uses them too, one tab a section
// (/fit?section=keyword), with each tab's not-rated count as its badge (David, 9 Nov 2026).

import { useRef, useState, type KeyboardEvent, type ReactNode } from "react";

export type TopTabPanel = { key: string; label: string; count: number; note: string; panel: ReactNode; badge?: ReactNode };

/** `param` names the address's setting for the open tab, and the tabs' ids; `label` names the tab list. */
export function TopTabs({ initial, tabs, param = "top", label = "Top 10 lists", className = "" }: {
  initial: string;
  tabs: TopTabPanel[];
  param?: string;
  label?: string;
  className?: string;
}) {
  const [current, setCurrent] = useState(tabs.some((t) => t.key === initial) ? initial : tabs[0]?.key);
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);

  function open(key: string) {
    setCurrent(key);
    const url = new URL(window.location.href);
    if (key === tabs[0]?.key) url.searchParams.delete(param);
    else url.searchParams.set(param, key);
    window.history.replaceState(window.history.state, "", url);
  }

  function onKey(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    if (!step) return;
    event.preventDefault();
    const next = (index + step + tabs.length) % tabs.length;
    open(tabs[next].key);
    buttons.current[next]?.focus();
  }

  return (
    <>
      <div className={`top-tabs ${className}`.trim()} role="tablist" aria-label={label}>
        {tabs.map((t, i) => (
          <button
            key={t.key}
            ref={(el) => {
              buttons.current[i] = el;
            }}
            type="button"
            role="tab"
            id={`${param}-tab-${t.key}`}
            data-label={t.label}
            aria-selected={current === t.key}
            aria-controls={`${param}-panel-${t.key}`}
            tabIndex={current === t.key ? 0 : -1}
            className="top-tab"
            onClick={() => open(t.key)}
            onKeyDown={(event) => onKey(event, i)}
          >
            {t.label}
            <span className="top-tab-count">{t.count}</span>
            {t.badge}
          </button>
        ))}
      </div>
      {tabs.map((t) => (
        <div key={t.key} role="tabpanel" id={`${param}-panel-${t.key}`} aria-labelledby={`${param}-tab-${t.key}`} hidden={current !== t.key}
          className="top-panel">
          <p className="muted top-note">{t.note}</p>
          {t.panel}
        </div>
      ))}
    </>
  );
}
