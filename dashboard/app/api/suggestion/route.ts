import { NextResponse } from "next/server";
import { latestSuggestion } from "@/lib/queries";
import { currentViewer } from "@/lib/viewer";

export const dynamic = "force-dynamic";

const NO_STORE = { "cache-control": "no-store" };

/** Start the draft reads a call's newest suggestion here, and when the assistant was last seen (David, 7 Nov 2026). */
export async function GET(request: Request) {
  const viewer = await currentViewer();
  if (!viewer) return NextResponse.json({ error: "Log in (top right) to see suggestions." }, { status: 401, headers: NO_STORE });
  const callId = (new URL(request.url).searchParams.get("call") ?? "").slice(0, 300);
  if (!callId) return NextResponse.json({ row: null, seenAt: null, now: new Date().toISOString() }, { headers: NO_STORE });
  const data = await latestSuggestion(callId);
  return NextResponse.json({ ...data, now: new Date().toISOString() }, { headers: NO_STORE });
}
