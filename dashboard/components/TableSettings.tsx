"use client";

import { useEffect, useRef } from "react";
import { resetColumns, saveColumns } from "@/app/actions";
import { COLUMNS, type Hidden, type TablePage } from "@/lib/columns";

const TABLES: { page: TablePage; title: string }[] = [
  { page: "queue", title: "Needs review" },
  { page: "calls", title: "All calls" },
];

/**
 * Table settings: which columns each table shows, kept for this browser (PRO-555). Any element marked
 * data-opens="table-settings" opens it; the account menu closes first. The native modal keeps focus
 * inside and closes on Escape; focus then goes back to what opened it, or to the menu's button when
 * that was a menu item (PRO-569). Keyed by the saved choice, so the boxes match it after Save or Reset.
 */
export function TableSettings({ hidden }: { hidden: Hidden }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const opener = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      const trigger = event.target instanceof Element ? event.target.closest<HTMLElement>("[data-opens='table-settings']") : null;
      if (!trigger || !dialog.current) return;
      opener.current = trigger;
      const menu = trigger.closest("details.menu");
      if (menu instanceof HTMLDetailsElement) menu.open = false;
      dialog.current.showModal();
    };
    document.addEventListener("click", onClick);
    return () => document.removeEventListener("click", onClick);
  }, []);

  const giveFocusBack = () => {
    const from = opener.current;
    const menu = from?.closest("details.menu");
    const target = menu instanceof HTMLDetailsElement && !menu.open ? menu.querySelector<HTMLElement>(":scope > summary") : from;
    target?.focus();
  };

  return (
    <dialog ref={dialog} id="table-settings" className="settings" aria-labelledby="settings-title" onClose={giveFocusBack}>
      <form key={JSON.stringify(hidden)} action={saveColumns} onSubmit={() => dialog.current?.close()}>
        <h2 id="settings-title">Table settings</h2>
        <p className="lead">Columns each table shows, for this browser.</p>
        <div className="settings-tables">
          {TABLES.map(({ page, title }) => (
            <fieldset key={page}>
              <legend>{title}</legend>
              {COLUMNS[page].map((column) => (
                <label key={column.key} className="check">
                  <input
                    type="checkbox"
                    name={`show:${page}:${column.key}`}
                    defaultChecked={column.fixed || !hidden[page].includes(column.key)}
                    disabled={column.fixed}
                  />
                  {column.label}
                  {column.fixed ? <span className="muted"> (always shown)</span> : null}
                </label>
              ))}
            </fieldset>
          ))}
        </div>
        <div className="settings-actions">
          <button type="submit" formAction={resetColumns} className="btn-text">
            Reset to defaults
          </button>
          <button type="button" onClick={() => dialog.current?.close()}>
            Cancel
          </button>
          <button type="submit" className="btn-primary">
            Save
          </button>
        </div>
      </form>
    </dialog>
  );
}
