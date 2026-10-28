import { FileText, House, Inbox, Workflow, type LucideIcon } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { AccountMenu, type ViewerMode } from "@/components/AccountMenu";
import { MenuController } from "@/components/MenuController";
import { TableSettings } from "@/components/TableSettings";
import { TooltipController } from "@/components/TooltipController";
import { countLabel, SECTIONS, type Section } from "@/lib/nav";
import { aliasesFor } from "@/lib/people";
import { countStepsReadyFor, countToDraft, countWaitingRequests, queueCounts } from "@/lib/queries";
import { hiddenColumns, queueMode } from "@/lib/settings";
import { allowlist, currentViewer, iapAudience, viewerHeader } from "@/lib/viewer";

const ICONS: Record<Section, LucideIcon> = { home: House, calls: Inbox, proposals: FileText, automation: Workflow };

/** What each section's chip counts (N3), for whoever is deciding. */
async function sectionCounts(viewer: string | null): Promise<Record<Exclude<Section, "home">, number>> {
  const users = allowlist();
  const names = viewer ? aliasesFor(viewer, users) : [];
  const [queue, toDraft, ready, requests] = await Promise.all([
    queueCounts({ portals: [], state: "", tag: "" }, queueMode() === "each" && viewer ? names : null),
    countToDraft(),
    countStepsReadyFor(names),
    countWaitingRequests(),
  ]);
  return { calls: queue.waiting, proposals: toDraft + ready, automation: requests ?? 0 };
}

/** How the viewer is known, and what to say when they cannot decide. */
function viewerMode(): { mode: ViewerMode; why: string } {
  if (iapAudience()) return { mode: "header", why: "This Google account is not in DASHBOARD_USERS" };
  const header = viewerHeader();
  if (header) return { mode: "header", why: `The ${header} header is missing or not on the allowlist` };
  const users = allowlist();
  if (users.length === 0) return { mode: "none", why: "Set DASHBOARD_USERS to record decisions" };
  return { mode: users.length === 1 ? "single" : "picker", why: "" };
}

/**
 * Every page's frame (PRO-570): the top bar with the brand, the four sections with their counts and
 * the account menu; then the page. On Calls, Table settings is offered in the account menu and the
 * filter bar.
 */
export async function Shell({ section, children }: { section: Section; children: ReactNode }) {
  const viewer = await currentViewer();
  const tableSettings = section === "calls";
  const [counts, hidden] = await Promise.all([sectionCounts(viewer), tableSettings ? hiddenColumns() : null]);
  const { mode, why } = viewerMode();
  return (
    <>
      <header className="topbar">
        <Link href="/" className="brand">
          <img src="/velocity-mark-white.png" alt="" width={21} height={16} />
          BD Team
        </Link>
        <nav aria-label="Sections">
          {SECTIONS.map(({ key, label, href }) => {
            const Icon = ICONS[key];
            const n = key === "home" ? 0 : counts[key];
            return (
              <Link key={key} href={href} className={key === section ? "active" : undefined} aria-current={key === section ? "page" : undefined}>
                <Icon aria-hidden="true" />
                {label}
                {key !== "home" && n ? (
                  <span className="count-chip" role="img" aria-label={countLabel(key, n)}>
                    {n}
                  </span>
                ) : null}
              </Link>
            );
          })}
        </nav>
        <AccountMenu viewer={viewer} names={allowlist().map((p) => p.name)} mode={mode} why={why} tableSettings={tableSettings} />
      </header>
      <main>{children}</main>
      {hidden ? <TableSettings hidden={hidden} /> : null}
      <MenuController />
      <TooltipController />
    </>
  );
}
