"use client";

import { useRef } from "react";
import { resetColumns, saveColumns } from "@/app/actions";
import { COLUMNS, type Hidden, type TablePage } from "@/lib/columns";

const TABLES: { page: TablePage; title: string }[] = [
  { page: "queue", title: "Review queue" },
  { page: "calls", title: "All calls" },
];

/**
 * The Settings button and its dialog: which columns each table shows, kept for this browser
 * (PRO-555). Keyed by the saved choice, so the boxes match it after Save or Reset.
 */
export function SettingsDialog({ hidden }: { hidden: Hidden }) {
  const dialog = useRef<HTMLDialogElement>(null);
  return (
    <>
      <button type="button" onClick={() => dialog.current?.showModal()}>
        Settings
      </button>
      <dialog ref={dialog} className="settings" aria-labelledby="settings-title">
        <form key={JSON.stringify(hidden)} action={saveColumns} onSubmit={() => dialog.current?.close()}>
          <h2 id="settings-title">Settings</h2>
          <p className="muted">Columns each table shows, for this browser.</p>
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
            <button type="submit" formAction={resetColumns}>
              Reset to defaults
            </button>
            <button type="button" onClick={() => dialog.current?.close()}>
              Cancel
            </button>
            <button type="submit" className="btn-pursue">
              Save
            </button>
          </div>
        </form>
      </dialog>
    </>
  );
}
