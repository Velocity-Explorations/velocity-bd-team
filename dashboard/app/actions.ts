"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { COLUMNS, COLUMNS_COOKIE, hiddenFromForm, hideColumn, readHidden, type TablePage } from "@/lib/columns";
import { aliasesFor } from "@/lib/people";
import { profileFromForm } from "@/lib/profile";
import { decideCall, decideRequest, deleteProfile, portals, saveProfile, tagOptions, type DecideRequestResult, type DecideResult } from "@/lib/queries";
import { isRequestChoice } from "@/lib/requests";
import { decidedNotice, fromQueue, safeReturnTo } from "@/lib/text";
import { isDecision, STATUS_LABELS } from "@/lib/values";
import { allowlist, currentViewer, VIEWER_COOKIE } from "@/lib/viewer";

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
  const status = formData.get("status");
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
