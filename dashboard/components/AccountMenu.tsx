import { ChevronDown, LogOut, Settings2, UserRound } from "lucide-react";
import Link from "next/link";
import { clearViewer, setViewer, signOutAction } from "@/app/actions";

/**
 * Who decides: from the picker (a cookie, until Google sign-in), from a sign-in proxy's header, the one
 * allowed person, or nobody when DASHBOARD_USERS is empty.
 */
export type ViewerMode = "picker" | "header" | "single" | "none" | "session";

/** A person as the menu shows them: the name decisions are recorded under, their shown name and initials (U2). */
export type MenuPerson = { name: string; label: string; initials: string };

/**
 * The account menu at the right of the top bar (U1, V1 to V4, PRO-570, PRO-574): the person, Profile
 * settings, Table settings on Calls, Switch user until Google sign-in, and Log out. With nobody chosen,
 * a Log in button lists the allowed people. Choosing a name applies at once.
 */
export function AccountMenu({ viewer, people, mode, why, tableSettings }: {
  viewer: string | null;
  people: MenuPerson[];
  mode: ViewerMode;
  why: string;
  tableSettings: boolean;
}) {
  if (!viewer && mode === "picker") {
    return (
      <details className="menu account">
        <summary className="btn btn-primary">Log in</summary>
        <div className="menu-body account-menu">
          <ChooseViewer people={people} title="Choose your name" hint="Until Google sign-in, decisions are recorded under the name you choose." />
        </div>
      </details>
    );
  }
  const you = people.find((p) => p.name === viewer);
  const shown = you?.label ?? viewer ?? (mode === "none" ? "Read only" : "Not on the list");
  const others = people.filter((p) => p.name !== viewer);
  return (
    <details className="menu account">
      <summary className="account-button" aria-label={`${shown}, ${viewer ? "deciding" : "cannot decide"}. Account menu`}>
        <span className="initials" aria-hidden="true">
          {viewer ? (you?.initials ?? "?") : "?"}
        </span>
        <span className="account-who">
          <span className="account-name">{shown}</span>
          <span className={viewer ? "account-role" : "account-role cannot"}>{viewer ? "Deciding" : "Cannot decide"}</span>
        </span>
        <ChevronDown aria-hidden="true" />
      </summary>
      <div className="menu-body account-menu">
        <div className="account-head">
          <span className="initials big" aria-hidden="true">
            {viewer ? (you?.initials ?? "?") : "?"}
          </span>
          <span>
            <strong>{shown}</strong>
            <span className="muted">{viewer ? "Decisions are recorded as you" : why}</span>
          </span>
        </div>
        {viewer || tableSettings ? (
          <div className="menu-group">
            {viewer ? (
              <Link href="/profile" className="menu-link">
                <UserRound aria-hidden="true" />
                Profile settings
              </Link>
            ) : null}
            {tableSettings ? (
              <button type="button" className="menu-item" data-opens="table-settings">
                <Settings2 aria-hidden="true" />
                Table settings
              </button>
            ) : null}
          </div>
        ) : null}
        {mode === "picker" && others.length ? (
          <ChooseViewer people={others} title="Switch user" hint="Until Google sign-in, choose who is deciding." />
        ) : null}
        {mode === "picker" && viewer ? (
          <form action={clearViewer} className="menu-group">
            <button type="submit" className="menu-item">
              <LogOut aria-hidden="true" />
              Log out
            </button>
          </form>
        ) : null}
        {mode === "session" ? (
          <form action={signOutAction} className="menu-group">
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

function ChooseViewer({ people, title, hint }: { people: MenuPerson[]; title: string; hint: string }) {
  return (
    <form action={setViewer} className="menu-group choose-viewer">
      <p className="menu-title">{title}</p>
      <p className="hint">{hint}</p>
      {people.map((person) => (
        <button key={person.name} type="submit" name="viewer" value={person.name} className="menu-item">
          <span className="initials small" aria-hidden="true">
            {person.initials}
          </span>
          {person.label}
        </button>
      ))}
    </form>
  );
}
