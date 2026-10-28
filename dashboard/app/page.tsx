import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Shell } from "@/components/Shell";
import { TopTenTable } from "@/components/TopTenTable";
import { ViewCards } from "@/components/ViewCards";
import { Flash } from "@/components/bits";
import { weekLabel } from "@/lib/brief";
import { formatAgo, formatTime } from "@/lib/format";
import { dayMonth, kindsLine } from "@/lib/home";
import { aliasesFor, displayPerson } from "@/lib/people";
import {
  countSubmittedWaiting,
  countToDraft,
  judgeAgreement,
  lastCompletedRun,
  listRuns,
  queueCounts,
  topTenIds,
  waitingRequests,
} from "@/lib/queries";
import { labeler, openingRedirect, timeZone } from "@/lib/me";
import { queueMode } from "@/lib/settings";
import { firstParam } from "@/lib/text";
import { DUE_SOON_DAYS, type ViewCard } from "@/lib/views";
import { allowlist, currentViewer } from "@/lib/viewer";

export const dynamic = "force-dynamic";
// The title template in layout.tsx only applies below the root segment, so this one is spelled out.
export const metadata: Metadata = { title: "Home | BD Team" };

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

/** Where the Top 10 comes from, in one line (H2). */
function topSource(week: string | null): string {
  return week
    ? `From the Monday brief, ${weekLabel(week)}, with each call's decision as of now.`
    : "No Monday brief yet, so this is the live ranking: yes before maybe, then the nearest deadline.";
}

/**
 * Home (H1 to H5, PRO-570): five link cards, the Top 10, a status line and the briefs. It reads the
 * ledger live and records nothing.
 */
export default async function HomePage({ searchParams }: { searchParams: SearchParams }) {
  const sp = await searchParams;
  const opening = await openingRedirect();
  if (opening) redirect(opening);
  const users = allowlist();
  const viewer = await currentViewer();
  const waitingFor = queueMode() === "each" && viewer ? aliasesFor(viewer, users) : null;
  const tz = await timeZone();
  const label = await labeler();
  const [queue, requests, toDraft, submitted, top, latest, lastRun, agreement] = await Promise.all([
    queueCounts({ portals: [], state: "", tag: "" }, waitingFor),
    waitingRequests(),
    countToDraft(),
    countSubmittedWaiting(),
    topTenIds(),
    listRuns(1),
    lastCompletedRun(),
    judgeAgreement(),
  ]);
  const run = latest[0];

  const cards: ViewCard[] = [
    {
      key: "needs-review",
      label: "Needs review",
      count: queue.waiting,
      description: `${queue.yes} yes, ${queue.waiting - queue.yes} maybe${waitingFor ? ", waiting for you" : ""}`,
      href: "/review",
      current: false,
      needsYou: true,
    },
    {
      key: "due-soon",
      label: "Due soon",
      count: queue.dueSoon,
      description: `closing by ${dayMonth(new Date(Date.now() + DUE_SOON_DAYS * 24 * 3600 * 1000), tz)}`,
      href: "/review?view=due-soon",
      current: false,
      needsYou: false,
    },
    {
      key: "requests",
      label: "Agent update requests",
      count: requests.length,
      description: requests.length ? kindsLine(requests.map((r) => r.kind)) : "nothing waiting",
      href: "/requests",
      current: false,
      needsYou: false,
    },
    { key: "to-draft", label: "Proposals to draft", count: toDraft, description: "pursued, open, no draft yet", href: "/proposals", current: false, needsYou: false },
    { key: "submitted", label: "Submitted and waiting", count: submitted, description: "waiting on a result", href: "/proposals", current: false, needsYou: false },
  ];

  return (
    <Shell section="home">
      <h1 className="sr-only">Home</h1>
      <Flash notice={firstParam(sp.notice, 300)} error={firstParam(sp.error, 300)} />
      <ViewCards label="Where to go next" cards={cards} opens />

      <section className="top-ten" aria-labelledby="top-ten-title">
        <div className="section-head">
          <h2 id="top-ten-title">Top 10</h2>
          <p className="muted">{topSource(top.week)}</p>
        </div>
        <TopTenTable ids={top.ids} description tz={tz} nameOf={(by) => label(displayPerson(by, users))} />
      </section>

      <p className="status-line">
        <Link href="/requests">
          {requests.length} {requests.length === 1 ? "request" : "requests"} waiting
        </Link>
        <span aria-hidden="true">·</span>
        <Link href="/runs">
          {run
            ? `Last scan ${run.status === "completed" ? "completed" : run.status.replace("_", " ")}, ${formatTime(run.started_at, tz)} (${formatAgo(run.started_at)})`
            : "No scan yet"}
          {run && run.status !== "completed" && lastRun ? `; last completed ${formatTime(lastRun.finished_at ?? lastRun.started_at, tz)}` : ""}
        </Link>
        <span aria-hidden="true">·</span>
        <Link href="/judges">
          {agreement && agreement.both
            ? `Claude and Grok agree on ${Math.round((100 * agreement.agree) / agreement.both)}% of the calls both judged`
            : "Claude and Grok have not both judged a call yet"}
        </Link>
      </p>
      <p className="brief-link">
        <Link href="/brief">This week&apos;s brief and past weekly briefs</Link>
      </p>
    </Shell>
  );
}
