import { NextResponse } from "next/server";
import { threadIdOk } from "@/lib/ask";
import { aliasesFor } from "@/lib/people";
import { chatThread } from "@/lib/queries";
import { allowlist, currentViewer } from "@/lib/viewer";

export const dynamic = "force-dynamic";

const NO_STORE = { "cache-control": "no-store" };

/**
 * Ask Grok's panel reads its thread here while an answer is on its way (David, 7 Nov 2026): the viewer's own thread,
 * the newest unless ?thread= names one, and when the assistant was last seen. Nobody reads another person's thread.
 */
export async function GET(request: Request) {
  const viewer = await currentViewer();
  if (!viewer) return NextResponse.json({ error: "Log in (top right) to ask Grok." }, { status: 401, headers: NO_STORE });
  const asked = new URL(request.url).searchParams.get("thread");
  const data = await chatThread(aliasesFor(viewer, allowlist()), threadIdOk(asked) ? asked : null);
  return NextResponse.json({ ...data, now: new Date().toISOString() }, { headers: NO_STORE });
}
