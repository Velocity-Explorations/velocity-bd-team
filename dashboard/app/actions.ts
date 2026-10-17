"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { decideCall, type DecideResult } from "@/lib/queries";
import { safeReturnTo } from "@/lib/text";
import { isDecision, STATUS_LABELS } from "@/lib/values";
import { allowlist, currentViewer, VIEWER_COOKIE } from "@/lib/viewer";

const MAX_NOTE_CHARS = 2000;

function backTo(returnTo: string, key: "notice" | "error", message: string): never {
  const url = new URL(returnTo, "http://dashboard.local");
  url.searchParams.delete("notice");
  url.searchParams.delete("error");
  url.searchParams.set(key, message);
  redirect(`${url.pathname}${url.search}`);
}

/**
 * Record a triage decision from the review queue. Writes human_status, human_by and
 * human_at (the columns a Slack reaction writes) and appends the optional note. A row that
 * was decided elsewhere in the meantime is left as it is.
 */
export async function decide(formData: FormData): Promise<void> {
  const returnTo = safeReturnTo(formData.get("return_to"));
  const id = String(formData.get("id") ?? "").trim();
  const status = formData.get("status");
  const note = String(formData.get("note") ?? "").slice(0, MAX_NOTE_CHARS);
  if (!id || !isDecision(status)) backTo(returnTo, "error", "That decision was not recognised.");

  const viewer = await currentViewer();
  if (!viewer) backTo(returnTo, "error", "Choose who you are (top right) before deciding.");

  let result: DecideResult;
  try {
    result = await decideCall({ id, status, by: viewer, note, onlyIfUndecided: true });
  } catch (err) {
    const detail = err instanceof Error ? err.message.slice(0, 160) : "database error";
    backTo(returnTo, "error", `Could not save the decision: ${detail}`);
  }
  revalidatePath("/");
  revalidatePath("/calls");
  if (result.ok) backTo(returnTo, "notice", `${STATUS_LABELS[status]}: ${result.title}`);
  backTo(returnTo, "error", result.reason);
}

/** The "Deciding as" picker, used when DASHBOARD_USERS lists more than one person. */
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
