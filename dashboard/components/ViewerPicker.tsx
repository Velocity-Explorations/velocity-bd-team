"use client";

import { clearViewer, setViewer } from "@/app/actions";

/**
 * The "Deciding as" picker, shown when DASHBOARD_USERS lists more than one person. Choosing a name
 * applies it at once; the button clears it (PRO-553). Keyed by the viewer, so the select shows the
 * name the server has after either.
 */
export function ViewerPicker({ names, viewer }: { names: string[]; viewer: string | null }) {
  return (
    <form action={setViewer} className="viewer">
      <label htmlFor="viewer">Deciding as</label>
      <select
        key={viewer ?? ""}
        id="viewer"
        name="viewer"
        defaultValue={viewer ?? ""}
        onChange={(event) => event.currentTarget.form?.requestSubmit()}
      >
        <option value="" disabled>
          Choose your name
        </option>
        {names.map((name) => (
          <option key={name} value={name}>
            {name}
          </option>
        ))}
      </select>
      <button type="submit" formAction={clearViewer} disabled={!viewer}>
        Clear User Selection
      </button>
    </form>
  );
}
