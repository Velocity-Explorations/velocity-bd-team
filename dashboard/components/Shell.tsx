import { FileText, House, Inbox, Workflow, type LucideIcon } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { AccountMenu, type ViewerMode } from "@/components/AccountMenu";
import { MenuController } from "@/components/MenuController";
import { StartDraftDialog } from "@/components/StartDraftDialog";
import { TableController } from "@/components/TableController";
import { TableSettings } from "@/components/TableSettings";
import { TooltipController } from "@/components/TooltipController";
import { formatTime } from "@/lib/format";
import { defaultFilters, drafting, initialsOf, labeler, me, timeZone } from "@/lib/me";
import { countLabel, SECTIONS, type Section } from "@/lib/nav";
import { callsHref } from "@/lib/profile";
import { aliasesFor } from "@/lib/people";
import { pastWorkGroups, pastWorkLabel } from "@/lib/pastwork";
import { overdueCount, sortIntoViews } from "@/lib/proposals";
import { countStepsReadyFor, countWaitingRequests, pastWork, proposalCalls, queueCounts } from "@/lib/queries";
import { hiddenColumns, queueMode } from "@/lib/settings";
import { allowlist, iapAudience, viewerHeader } from "@/lib/viewer";

const ICONS: Record<Section, LucideIcon> = { home: House, calls: Inbox, proposals: FileText, automation: Workflow };

/** What each section's chip counts (N3), for whoever is deciding. */
async function sectionCounts(viewer: string | null): Promise<Record<Exclude<Section, "home">, number>> {
  const users = allowlist();
  const names = viewer ? aliasesFor(viewer, users) : [];
  const [queue, toDraft, ready, requests] = await Promise.all([
    queueCounts({ portals: [], state: "", tag: "" }, queueMode() === "each" && viewer ? names : null),
    proposalCalls({ portals: [], state: "", tag: "" }).then((rows) => {
      const views = sortIntoViews(rows);   // overdue results count too (P4)
      return views["to-draft"].length + overdueCount(views.submitted, new Date().toISOString().slice(0, 10));
    }),
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
 * Every page's frame (PRO-570, PRO-574): the top bar with the brand, the four sections with their
 * counts and the account menu; then the page. Calls opens with the viewer's default filters. On Calls,
 * Table settings is offered in the account menu and the filter bar. Calls and Proposals carry the
 * Start the draft dialog (P6). Pages outside the sections (Profile settings) mark none.
 */
export async function Shell({ section, children }: { section: Section | null; children: ReactNode }) {
  const { viewer } = await me();
  const tableSettings = section === "calls";
  const startsDrafts = section === "calls" || section === "proposals";
  const [counts, hidden, label, filters, draft, tz, past] = await Promise.all([
    sectionCounts(viewer),
    tableSettings ? hiddenColumns() : null,
    labeler(),
    defaultFilters(),
    startsDrafts ? drafting() : null,
    timeZone(),
    startsDrafts ? pastWork() : null,
  ]);
  const people = await Promise.all(allowlist().map(async (p) => ({ name: p.name, label: label(p.name), initials: await initialsOf(p.name) })));
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
              <Link
                key={key}
                href={key === "calls" ? callsHref(filters) : href}
                className={key === section ? "active" : undefined}
                aria-current={key === section ? "page" : undefined}
              >
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
        <AccountMenu viewer={viewer} people={people} mode={mode} why={why} tableSettings={tableSettings} />
      </header>
      <main>{children}</main>
      {hidden ? <TableSettings hidden={hidden} /> : null}
      {draft ? (
        <StartDraftDialog
          people={people.filter((p) => p.name !== viewer).map(({ name, label }) => ({ name, label }))}
          owner={viewer ? label(viewer) : null}
          readiness={draft.readiness}
          lastSeen={draft.seenAt ? formatTime(draft.seenAt, tz) : null}
          pastWork={pastWorkGroups(past?.items ?? [], []).map((g) => ({
            title: g.title, items: g.items.map((i) => ({ id: i.id, label: pastWorkLabel(i) })),
          }))}
          indexed={past?.indexedAt ? formatTime(past.indexedAt, tz) : null}
        />
      ) : null}
      <MenuController />
      <TooltipController />
      <TableController />
    </>
  );
}
