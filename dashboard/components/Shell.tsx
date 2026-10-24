import Link from "next/link";
import type { ReactNode } from "react";
import { SettingsDialog } from "@/components/SettingsDialog";
import { ViewerPicker } from "@/components/ViewerPicker";
import { countWaitingRequests } from "@/lib/queries";
import { hiddenColumns } from "@/lib/settings";
import { allowlist, currentViewer, iapAudience, viewerHeader } from "@/lib/viewer";

const LINKS = [
  { key: "queue", href: "/", label: "Review queue" },
  { key: "brief", href: "/brief", label: "Monday brief" },
  { key: "calls", href: "/calls", label: "All calls" },
  { key: "judges", href: "/judges", label: "Judges" },
  { key: "requests", href: "/requests", label: "Requests" },
  { key: "runs", href: "/runs", label: "Runs" },
  { key: "proposals", href: "/proposals", label: "Proposals" },
] as const;

export type NavKey = (typeof LINKS)[number]["key"];

export async function Shell({ current, children }: { current: NavKey; children: ReactNode }) {
  const [waiting, hidden] = await Promise.all([countWaitingRequests(), hiddenColumns()]);
  return (
    <>
      <header className="topbar">
        <Link href="/" className="brand">
          Velocity BD
        </Link>
        <nav aria-label="Main">
          {LINKS.map((link) => (
            <Link
              key={link.key}
              href={link.href}
              className={link.key === current ? "active" : undefined}
              aria-current={link.key === current ? "page" : undefined}
            >
              {link.label}
              {link.key === "requests" && waiting ? (
                <span className="badge tone-warn nav-count" aria-label={`${waiting} waiting for approval`}>
                  {waiting}
                </span>
              ) : null}
            </Link>
          ))}
        </nav>
        <ViewerControl />
        <SettingsDialog hidden={hidden} />
      </header>
      <main>{children}</main>
    </>
  );
}

async function ViewerControl() {
  const viewer = await currentViewer();
  const iap = iapAudience() !== null;
  const header = viewerHeader();
  const users = allowlist();

  if (iap || header) {
    return (
      <div className="viewer">
        {viewer ? (
          <span>
            Deciding as <strong>{viewer}</strong>
          </span>
        ) : iap ? (
          <span className="muted">Read only: this Google account is not in DASHBOARD_USERS</span>
        ) : (
          <span className="muted">Not identified: the {header} header is missing or not on the allowlist</span>
        )}
      </div>
    );
  }
  if (users.length === 0) {
    return <div className="viewer muted">Read only: set DASHBOARD_USERS to record decisions</div>;
  }
  if (users.length === 1) {
    return (
      <div className="viewer">
        <span>
          Deciding as <strong>{users[0].name}</strong>
        </span>
      </div>
    );
  }
  return <ViewerPicker names={users.map((person) => person.name)} viewer={viewer} />;
}
