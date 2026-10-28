import { ChevronDown, LogOut, Settings2 } from "lucide-react";
import { clearViewer, setViewer } from "@/app/actions";
import { initials } from "@/lib/nav";

/**
 * Who decides: from the picker (a cookie, until Google sign-in), from a sign-in proxy's header, the one
 * allowed person, or nobody when DASHBOARD_USERS is empty.
 */
export type ViewerMode = "picker" | "header" | "single" | "none";

/**
 * The account menu at the right of the top bar (U1, V1 to V4, PRO-570): the person, Table settings on
 * Calls, Switch user until Google sign-in, and Log out. With nobody chosen, a Log in button lists the
 * allowed people. Choosing a name applies at once.
 */
export function AccountMenu({ viewer, names, mode, why, tableSettings }: {
  viewer: string | null;
  names: string[];
  mode: ViewerMode;
  why: string;
  tableSettings: boolean;
}) {
  if (!viewer && mode === "picker") {
    return (
      <details className="menu account">
        <summary className="btn btn-primary">Log in</summary>
        <div className="menu-body account-menu">
          <ChooseViewer names={names} title="Choose your name" hint="Until Google sign-in, decisions are recorded under the name you choose." />
        </div>
      </details>
    );
  }
  const name = viewer ?? (mode === "none" ? "Read only" : "Not on the list");
  const others = names.filter((n) => n !== viewer);
  return (
    <details className="menu account">
      <summary className="account-button" aria-label={`${name}, ${viewer ? "deciding" : "cannot decide"}. Account menu`}>
        <span className="initials" aria-hidden="true">
          {viewer ? initials(viewer) : "?"}
        </span>
        <span className="account-who">
          <span className="account-name">{name}</span>
          <span className={viewer ? "account-role" : "account-role cannot"}>{viewer ? "Deciding" : "Cannot decide"}</span>
        </span>
        <ChevronDown aria-hidden="true" />
      </summary>
      <div className="menu-body account-menu">
        <div className="account-head">
          <span className="initials big" aria-hidden="true">
            {viewer ? initials(viewer) : "?"}
          </span>
          <span>
            <strong>{name}</strong>
            <span className="muted">{viewer ? "Decisions are recorded as you" : why}</span>
          </span>
        </div>
        {tableSettings ? (
          <div className="menu-group">
            <button type="button" className="menu-item" data-opens="table-settings">
              <Settings2 aria-hidden="true" />
              Table settings
            </button>
          </div>
        ) : null}
        {mode === "picker" && others.length ? (
          <ChooseViewer names={others} title="Switch user" hint="Until Google sign-in, choose who is deciding." />
        ) : null}
        {mode === "picker" && viewer ? (
          <form action={clearViewer} className="menu-group">
            <button type="submit" className="menu-item">
              <LogOut aria-hidden="true" />
              Log out
            </button>
          </form>
        ) : null}
      </div>
    </details>
  );
}

function ChooseViewer({ names, title, hint }: { names: string[]; title: string; hint: string }) {
  return (
    <form action={setViewer} className="menu-group choose-viewer">
      <p className="menu-title">{title}</p>
      <p className="hint">{hint}</p>
      {names.map((name) => (
        <button key={name} type="submit" name="viewer" value={name} className="menu-item">
          <span className="initials small" aria-hidden="true">
            {initials(name)}
          </span>
          {name}
        </button>
      ))}
    </form>
  );
}
