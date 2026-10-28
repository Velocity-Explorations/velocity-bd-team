"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { COLUMNS, COLUMNS_COOKIE, hiddenFromForm, hideColumn, readHidden, type TablePage } from "@/lib/columns";
import { aliasesFor } from "@/lib/people";
import { profileFromForm } from "@/lib/profile";
import { FORMATS } from "@/lib/proposals";
import {
  addMaterial,
  approveStep,
  askChanges,
  changeBuildsOn,
  decideCall,
  decideRequest,
  deleteProfile,
  noGoStep,
  portals,
  raiseCap,
  retryStep,
  saveProfile,
  setCollaborators,
  setDirection,
  startPursuit,
  tagOptions,
  tickChecklist,
  workspace,
  type DecideRequestResult,
  type DecideResult,
  type StartResult,
  type WorkspaceResult,
} from "@/lib/queries";
import { isRequestChoice } from "@/lib/requests";
import { decidedNotice, fromQueue, safeReturnTo } from "@/lib/text";
import { isDecision, STATUS_LABELS } from "@/lib/values";
import { allowlist, currentViewer, VIEWER_COOKIE } from "@/lib/viewer";
import { parseJson, permissions } from "@/lib/workspace";

const MAX_NOTE_CHARS = 2000;

function backTo(returnTo: string, key: "notice" | "error", message: string, voted?: string): never {
  const url = new URL(returnTo, "http://dashboard.local");
  url.searchParams.delete("notice");
  url.searchParams.delete("error");
  url.searchParams.delete("voted");
  url.searchParams.set(key, message);
  if (voted) url.searchParams.set("voted", voted);   // the queue links the notice to the call on All calls
  redirect(`${url.pathname}${url.search}`);
}

/**
 * Record or change a decision (the review queue's buttons, and the change control on
 * /calls). Writes human_status, human_by and human_at, appends the optional note, and keeps
 * the person's decision in `decisions`. Choosing the decision a call already has, when it is
 * someone else's, adds the viewer's own; so does every queue button while everyone decides
 * every call ("keep"). Otherwise the form carries the decision the page showed ("expected",
 * empty for undecided); if the call changed since, nothing is written.
 */
export async function decide(formData: FormData): Promise<void> {
  const returnTo = safeReturnTo(formData.get("return_to"));
  const id = String(formData.get("id") ?? "").trim();
  const asked = formData.get("status");
  const thenDraft = asked === "pursue_draft";   // the Decide menu's Pursue and start the draft (Q9)
  const status = thenDraft ? "pursue" : asked;
  const expectedField = String(formData.get("expected") ?? "");
  const note = String(formData.get("note") ?? "").slice(0, MAX_NOTE_CHARS);
  if (!id || !isDecision(status)) backTo(returnTo, "error", "Choose a decision first.");
  if (expectedField && !isDecision(expectedField)) backTo(returnTo, "error", "That form is out of date. Reload and try again.");
  const expected = isDecision(expectedField) ? expectedField : null;
  const keepCallDecision = formData.get("keep") === "1";

  const viewer = await currentViewer();
  if (!viewer) backTo(returnTo, "error", "Log in (top right) before deciding.");

  let result: DecideResult;
  try {
    result = await decideCall({ id, status, expected, keepCallDecision, by: viewer, aliases: aliasesFor(viewer, allowlist()), note });
  } catch (err) {
    const detail = err instanceof Error ? err.message.slice(0, 160) : "database error";
    backTo(returnTo, "error", `Could not save the decision: ${detail}`);
  }
  revalidatePath("/", "layout");
  if (result.ok) {
    const stays = result.callStatus && result.callStatus !== status ? ` The call stays ${STATUS_LABELS[result.callStatus]}.` : "";
    const queue = fromQueue(returnTo);
    const notice = decidedNotice(result.plan, STATUS_LABELS[status], result.title, stays, queue);
    if (thenDraft && result.callStatus === "pursue") backTo(`/proposals?start=${encodeURIComponent(id)}`, "notice", `${notice} Start the draft below.`);
    backTo(returnTo, "notice", notice, queue && result.plan !== "note" ? result.title : undefined);
  }
  backTo(returnTo, "error", result.reason);
}

/**
 * Approve or reject a change request on /requests. Writes status, decided_by, decided_at
 * and the optional note, only while the request is still proposed.
 */
export async function decideRequestAction(formData: FormData): Promise<void> {
  const returnTo = "/requests";
  const id = Number.parseInt(String(formData.get("id") ?? ""), 10);
  const choice = formData.get("choice");
  const note = String(formData.get("note") ?? "").slice(0, MAX_NOTE_CHARS);
  if (!Number.isInteger(id) || id <= 0 || !isRequestChoice(choice)) backTo(returnTo, "error", "Choose Approve or Reject first.");

  const viewer = await currentViewer();
  if (!viewer) backTo(returnTo, "error", "Log in (top right) before deciding.");

  let result: DecideRequestResult;
  try {
    result = await decideRequest({ id, choice, by: viewer, note });
  } catch (err) {
    const detail = err instanceof Error ? err.message.slice(0, 160) : "database error";
    backTo(returnTo, "error", `Could not save the decision: ${detail}`);
  }
  revalidatePath("/", "layout");
  if (result.ok) {
    backTo(returnTo, "notice", `${choice === "approve" ? "Approved" : "Rejected"} request #${id}: ${result.summary}`);
  }
  backTo(returnTo, "error", result.reason);
}

/** The account menu's Log in and Switch user lists, when DASHBOARD_USERS names more than one person. */
export async function setViewer(formData: FormData): Promise<void> {
  const name = String(formData.get("viewer") ?? "").trim();
  const store = await cookies();
  if (allowlist().some((person) => person.name === name)) {
    store.set(VIEWER_COOKIE, name, { httpOnly: true, sameSite: "lax", path: "/", maxAge: 60 * 60 * 24 * 365 });
  } else {
    store.delete(VIEWER_COOKIE);
  }
  revalidatePath("/", "layout");
}

/**
 * The account menu's Log out (V2): nobody is deciding until a name is chosen again. Until Google
 * sign-in it returns to Home with the sign-out notice.
 */
export async function clearViewer(): Promise<void> {
  (await cookies()).delete(VIEWER_COOKIE);
  revalidatePath("/", "layout");
  backTo("/", "notice", "You are logged out of BD Team.");
}

/** Table settings' Save: which columns each table shows, kept for this browser (PRO-555). */
export async function saveColumns(formData: FormData): Promise<void> {
  const hidden = hiddenFromForm(new Set(formData.keys()));
  (await cookies()).set(COLUMNS_COOKIE, JSON.stringify(hidden), { httpOnly: true, sameSite: "lax", path: "/", maxAge: 60 * 60 * 24 * 365 });
  revalidatePath("/", "layout");
}

/** A header menu's Hide column (PRO-572): one more column hidden on that table, for this browser. */
export async function hideColumnAction(formData: FormData): Promise<void> {
  const page = String(formData.get("page") ?? "");
  const key = String(formData.get("key") ?? "");
  if (!(page in COLUMNS)) return;
  const store = await cookies();
  const hidden = hideColumn(readHidden(store.get(COLUMNS_COOKIE)?.value), page as TablePage, key);
  store.set(COLUMNS_COOKIE, JSON.stringify(hidden), { httpOnly: true, sameSite: "lax", path: "/", maxAge: 60 * 60 * 24 * 365 });
  revalidatePath("/", "layout");
}

/** Table settings' Reset to defaults. */
export async function resetColumns(): Promise<void> {
  (await cookies()).delete(COLUMNS_COOKIE);
  revalidatePath("/", "layout");
}

/** Profile settings' Save (PRO-574): the viewer's own row, checked against the portals and tags that exist. */
export async function saveProfileAction(formData: FormData): Promise<void> {
  const viewer = await currentViewer();
  if (!viewer) backTo("/profile", "error", "Log in (top right) before saving your profile.");
  const [portalList, tagList] = await Promise.all([portals(), tagOptions()]);
  const form = new Map<string, string[]>();
  for (const key of new Set(formData.keys())) form.set(key, formData.getAll(key).map(String));
  await saveProfile(viewer, profileFromForm(form, viewer, { portals: portalList.map((p) => p.name), tags: tagList.map((t) => t.name) }));
  revalidatePath("/", "layout");
  backTo("/profile", "notice", "Saved your profile.");
}

/** Profile settings' Reset to defaults: the viewer's row goes, so every default applies again. */
export async function resetProfileAction(): Promise<void> {
  const viewer = await currentViewer();
  if (!viewer) backTo("/profile", "error", "Log in (top right) before changing your profile.");
  await deleteProfile(viewer);
  revalidatePath("/", "layout");
  backTo("/profile", "notice", "Your profile is back to the defaults.");
}

/**
 * Start the draft (P6, PRO-576): the viewer becomes the owner; the people working with them come from
 * DASHBOARD_USERS. Refusals come back as the page's notice.
 */
export async function startDraftAction(formData: FormData): Promise<void> {
  const returnTo = safeReturnTo(formData.get("return_to"), "/proposals");
  const viewer = await currentViewer();
  if (!viewer) backTo(returnTo, "error", "Log in (top right) before starting a draft.");
  const callId = String(formData.get("call_id") ?? "").trim();
  if (!callId) backTo(returnTo, "error", "Choose a call to draft first.");
  const asked = String(formData.get("format") ?? "");
  const names = allowlist().map((p) => p.name);
  let result: StartResult;
  try {
    result = await startPursuit({
      callId,
      owner: viewer,
      format: FORMATS.includes(asked) ? asked : FORMATS[0],
      approvalMode: formData.get("approval_mode") === "key_gates" ? "key_gates" : "every_step",
      direction: String(formData.get("direction") ?? "").slice(0, MAX_NOTE_CHARS),
      collaborators: [...new Set(formData.getAll("with").map(String))].filter((name) => names.includes(name) && name !== viewer),
    });
  } catch (err) {
    const detail = err instanceof Error ? err.message.slice(0, 160) : "database error";
    backTo(returnTo, "error", `Could not start the draft: ${detail}`);
  }
  revalidatePath("/", "layout");
  if (result.ok) backTo("/proposals?view=drafting", "notice", `Started the draft for ${result.title}. Discovery is queued for the worker.`);
  backTo(returnTo, "error", result.reason);
}

// ----------------------------------------------------------------- the proposal workspace

function workspaceHref(callId: string, step: string): string {
  return `/proposals/${encodeURIComponent(callId)}${step ? `?step=${encodeURIComponent(step)}` : ""}`;
}

/**
 * Who is acting on a pursuit, and whether they may (PW17, PW24): logged in, and the owner to decide a step,
 * or anyone working on the draft to add material and tick items. A courtesy check until sign-in, since the
 * viewer is self-chosen until then.
 */
async function workspaceActor(formData: FormData, need: "decide" | "contribute") {
  const callId = String(formData.get("call_id") ?? "");
  const back = workspaceHref(callId, String(formData.get("step") ?? ""));
  const viewer = await currentViewer();
  if (!viewer) backTo(back, "error", "Log in (top right) first.");
  const found = callId ? await workspace(callId) : null;
  const pursuit = found?.pursuit;
  if (!found || !pursuit) backTo("/proposals?view=drafting", "error", "That draft is no longer in the ledger.");
  const allowed = permissions(viewer, pursuit.owner, parseJson<string[]>(pursuit.collaborators, []));
  if (need === "decide" && !allowed.decide) backTo(back, "error", `Only the owner, ${pursuit.owner}, decides this step.`);
  if (need === "contribute" && !allowed.contribute) {
    backTo(back, "error", `Only ${pursuit.owner} and the people working with them can add to this draft.`);
  }
  return { viewer, back, found, pursuit };
}

/** Run a workspace write and return to the step with what happened. */
async function workspaceWrite(back: string, write: () => Promise<WorkspaceResult>): Promise<never> {
  let result: WorkspaceResult;
  try {
    result = await write();
  } catch (err) {
    const detail = err instanceof Error ? err.message.slice(0, 160) : "database error";
    backTo(back, "error", `Could not save: ${detail}`);
  }
  revalidatePath("/", "layout");
  if (result.ok) backTo(back, "notice", result.notice);
  backTo(back, "error", result.reason);
}

function stepFields(formData: FormData): { stepId: number; expected: string; note: string } {
  return {
    stepId: Number(formData.get("step_id")),
    expected: String(formData.get("expected") ?? ""),
    note: String(formData.get("note") ?? "").slice(0, MAX_NOTE_CHARS),
  };
}

/** Approve and continue (PW4), and Go or Go with conditions at the gate (PW10). */
export async function approveStepAction(formData: FormData): Promise<void> {
  const { viewer, back, found } = await workspaceActor(formData, "decide");
  const { stepId, expected, note } = stepFields(formData);
  const conditions = String(formData.get("conditions") ?? "").split(/\r?\n/).map((c) => c.trim().slice(0, 300)).filter(Boolean).slice(0, 20);
  const decision = String(formData.get("decision") ?? "") || undefined;
  // Alignment's choice (PW8): keep the owner's direction, take Claude's angle, or write a new one.
  const choice = String(formData.get("direction_choice") ?? "");
  let direction: string | undefined;
  if (choice === "claude") {
    const step = found.steps.find((s) => s.id === stepId);
    direction = String(parseJson<{ angle?: string }>(step?.content, {}).angle ?? "").trim() || undefined;
  } else if (choice === "new") {
    direction = String(formData.get("direction") ?? "").trim().slice(0, MAX_NOTE_CHARS);
    if (!direction) backTo(back, "error", "Write the new direction first, or keep yours.");
  }
  await workspaceWrite(back, () => approveStep({ stepId, by: viewer, expected, decision, note, conditions, direction }));
}

/** The Outline's last chance to change the direction (PW11), until it is approved. */
export async function setDirectionAction(formData: FormData): Promise<void> {
  const { viewer, back, pursuit } = await workspaceActor(formData, "decide");
  const direction = String(formData.get("direction") ?? "").slice(0, MAX_NOTE_CHARS);
  await workspaceWrite(back, () => setDirection({ pursuitId: pursuit.id, by: viewer, direction }));
}

/** Past work to build on (PW11, PW24): the owner and the people working with them add or remove it until the Outline is approved. */
export async function changeBuildsOnAction(formData: FormData): Promise<void> {
  const { viewer, back, pursuit } = await workspaceActor(formData, "contribute");
  const add = String(formData.get("add") ?? "") || undefined;
  const remove = String(formData.get("remove") ?? "") || undefined;
  if (!add && !remove) backTo(back, "error", "Name the past work to add: a past proposal, a project, or a link.");
  await workspaceWrite(back, () => changeBuildsOn({ pursuitId: pursuit.id, by: viewer, add, remove }));
}

/** Who works with the owner (PW24): only the owner changes the list, from People. */
export async function setCollaboratorsAction(formData: FormData): Promise<void> {
  const { viewer, back, pursuit } = await workspaceActor(formData, "decide");
  const allowed = allowlist().map((p) => p.name);
  const names = formData.getAll("with").map(String).filter((name) => allowed.includes(name) && name !== pursuit.owner);
  await workspaceWrite(back, () => setCollaborators({ pursuitId: pursuit.id, by: viewer, names }));
}

/** Ask for changes (PW4): the step is redone with the note. */
export async function askChangesAction(formData: FormData): Promise<void> {
  const { viewer, back } = await workspaceActor(formData, "decide");
  const { stepId, expected, note } = stepFields(formData);
  await workspaceWrite(back, () => askChanges({ stepId, by: viewer, expected, note }));
}

/** Retry a failed step (PW15). */
export async function retryStepAction(formData: FormData): Promise<void> {
  const { viewer, back } = await workspaceActor(formData, "decide");
  await workspaceWrite(back, () => retryStep({ stepId: Number(formData.get("step_id")), by: viewer }));
}

/** Stop here, no-go (PW4) and No-go at the gate (PW10): the pursuit stops and the call is recorded Not relevant (P7). */
export async function noGoAction(formData: FormData): Promise<void> {
  const { viewer, back, found } = await workspaceActor(formData, "decide");
  const { stepId, expected, note } = stepFields(formData);
  await workspaceWrite(back, async () => {
    const stopped = await noGoStep({ stepId, by: viewer, expected, note });
    if (!stopped.ok) return stopped;
    const status = found.call.human_status;
    const call = await decideCall({
      id: found.call.id, status: "not_relevant", expected: isDecision(status) ? status : null, keepCallDecision: false,
      by: viewer, aliases: aliasesFor(viewer, allowlist()), note: `No-go: ${note.trim()}`,
    });
    return call.ok
      ? { ok: true, notice: "No-go recorded, and the call is marked Not relevant with your reason." }
      : { ok: true, notice: `No-go recorded. The call's decision was not changed: ${call.reason}` };
  });
}

/** Raise the cap (PW19): a higher budget, and the step that reached it queued again. */
export async function raiseCapAction(formData: FormData): Promise<void> {
  const { viewer, back, pursuit } = await workspaceActor(formData, "decide");
  const budget = Number(formData.get("budget"));
  if (!Number.isFinite(budget) || budget <= pursuit.budget_usd || budget > 10_000) {
    backTo(back, "error", `Choose a cap above the current ${pursuit.budget_usd.toFixed(2)} dollars, up to 10,000.`);
  }
  await workspaceWrite(back, () => raiseCap({ pursuitId: pursuit.id, by: viewer, budget: Math.round(budget * 100) / 100 }));
}

/** Add material (PW4, PW24): a note or a link for Claude, from the owner or anyone working with them. */
export async function addMaterialAction(formData: FormData): Promise<void> {
  const { viewer, back, pursuit } = await workspaceActor(formData, "contribute");
  const stepId = Number(formData.get("step_id")) || null;
  const text = String(formData.get("material") ?? "").slice(0, MAX_NOTE_CHARS);
  await workspaceWrite(back, () => addMaterial({ pursuitId: pursuit.id, who: viewer, text, stepId }));
}

/** Tick or untick a checklist item (PW9, PW24). */
export async function tickChecklistAction(formData: FormData): Promise<void> {
  const { viewer, back } = await workspaceActor(formData, "contribute");
  await workspaceWrite(back, () => tickChecklist({
    itemId: Number(formData.get("item_id")), by: viewer, done: formData.get("done") === "1",
    expectedDone: formData.get("expected_done") === "1",
  }));
}
