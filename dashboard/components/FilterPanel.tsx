import Link from "next/link";
import type { ReactNode } from "react";
import type { CallState, Sort } from "@/lib/filters";
import type { JudgeFilter } from "@/lib/judges";

const STATES: { value: CallState; label: string }[] = [
  { value: "", label: "Open and closed" },
  { value: "open", label: "Open" },
  { value: "closed", label: "Closed" },
];

const JUDGE_CHOICES: { value: JudgeFilter; label: string }[] = [
  { value: "", label: "Any" },
  { value: "disagree", label: "Claude and Grok disagree" },
  { value: "agree", label: "Claude and Grok agree" },
];

/**
 * The filter panel on the left of the review queue and All calls: a checkbox per portal,
 * open or closed, and the sort order, plus any page-specific fields passed as children.
 * A plain GET form, so every filtered view is a link that can be shared.
 */
export function FilterPanel(props: {
  action: string;
  portals: string[];
  selected: string[];
  state: CallState;
  sort: Sort;
  judges: JudgeFilter;
  filtered: boolean;
  children?: ReactNode;
}) {
  return (
    <aside className="panel" aria-label="Filters">
      <form action={props.action}>
        <fieldset>
          <legend>Portals</legend>
          {props.portals.length === 0 ? <p className="hint">No calls scanned yet.</p> : null}
          {props.portals.map((p) => (
            <label key={p} className="check">
              <input type="checkbox" name="portal" value={p} defaultChecked={props.selected.includes(p)} /> {p}
            </label>
          ))}
          {props.portals.length > 1 ? <p className="hint">None ticked shows every portal.</p> : null}
        </fieldset>
        <fieldset>
          <legend>Calls</legend>
          {STATES.map((s) => (
            <label key={s.value || "both"} className="check">
              <input type="radio" name="state" value={s.value} defaultChecked={props.state === s.value} /> {s.label}
            </label>
          ))}
        </fieldset>
        <fieldset>
          <legend>Judges</legend>
          {JUDGE_CHOICES.map((j) => (
            <label key={j.value || "any"} className="check">
              <input type="radio" name="judges" value={j.value} defaultChecked={props.judges === j.value} /> {j.label}
            </label>
          ))}
        </fieldset>
        <label className="field">
          Sort
          <select name="sort" defaultValue={props.sort}>
            <option value="newest">Newest first</option>
            <option value="due">Closing soonest</option>
          </select>
        </label>
        {props.children}
        <div className="panel-actions">
          <button type="submit">Apply</button>
          {props.filtered ? (
            <Link href={props.action} className="reset">
              Clear filters
            </Link>
          ) : null}
        </div>
      </form>
    </aside>
  );
}
