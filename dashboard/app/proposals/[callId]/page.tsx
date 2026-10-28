import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Shell } from "@/components/Shell";
import { StageStrip, StepCard, StepList, WorkspaceHeader, WorkspacePanels } from "@/components/Workspace";
import { Flash } from "@/components/bits";
import { drafting, labeler, timeZone } from "@/lib/me";
import { workspace } from "@/lib/queries";
import { firstParam } from "@/lib/text";
import { allowlist, currentViewer } from "@/lib/viewer";
import { displayPerson } from "@/lib/people";
import { latestSteps, openStep, parseJson, permissions } from "@/lib/workspace";

export const dynamic = "force-dynamic";

type Params = Promise<{ callId: string }>;
type SearchParams = Promise<Record<string, string | string[] | undefined>>;

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const found = await workspace(decodeURIComponent((await params).callId));
  return { title: found?.call.title || "Proposal workspace" };
}

/**
 * The proposal workspace (PW1 to PW25, PRO-580): one pursuit followed step by step. The header, the stage
 * strip, the step list and the open step's card, with People, Checklist and Show history under the header.
 * `?step=` opens a step the pursuit has reached; a done step opens read only.
 */
export default async function WorkspacePage({ params, searchParams }: { params: Params; searchParams: SearchParams }) {
  const callId = decodeURIComponent((await params).callId);
  const sp = await searchParams;
  const found = await workspace(callId);
  if (!found) notFound();
  const { call, pursuit } = found;
  if (!pursuit) {
    return (
      <Shell section="proposals">
        <h1 className="sr-only">{call.title || call.id}</h1>
        <div className="empty">
          <p className="title">This call has no draft yet.</p>
          <p className="muted">
            Start the draft from <a href="/proposals">To draft</a> or the call&apos;s Decide menu once it is marked Pursue.
          </p>
        </div>
      </Shell>
    );
  }
  const [viewer, label, tz, worker] = await Promise.all([currentViewer(), labeler(), timeZone(), drafting()]);
  const users = allowlist();
  const name = (who: string) => label(displayPerson(who, users));
  const latest = latestSteps(found.steps);
  const open = openStep(firstParam(sp.step, 40) || undefined, latest, pursuit.current_step);
  const row = latest.get(open);
  const can = permissions(viewer, pursuit.owner, parseJson<string[]>(pursuit.collaborators, []));
  return (
    <Shell section="proposals">
      <WorkspaceHeader call={call} pursuit={pursuit} checklist={found.checklist} label={name} tz={tz} />
      <Flash notice={firstParam(sp.notice, 300)} error={firstParam(sp.error, 300)} />
      <WorkspacePanels call={call} pursuit={pursuit} checklist={found.checklist} events={found.events} step={open} can={can} label={name} tz={tz} />
      <StageStrip current={pursuit.current_step} pursuitState={pursuit.state} />
      <div className="ws-body">
        <StepList latest={latest} open={open} />
        {row ? (
          <StepCard call={call} pursuit={pursuit} row={row} can={can} worker={worker} label={name} tz={tz} />
        ) : (
          <p className="muted">Nothing has been queued for this pursuit yet.</p>
        )}
      </div>
    </Shell>
  );
}
