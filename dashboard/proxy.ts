import { NextResponse, type NextRequest } from "next/server";
import { auth } from "@/auth";
import { sql } from "@/lib/db";
import { googleKeys, IAP_HEADER, needsSignIn, verifyIapToken } from "@/lib/iap";
import { draftPageCallId } from "@/lib/proposals";
import { needsSession, SIGNED_IN_COOKIE, signInEnabled } from "@/lib/signin";

// With Google sign-in set up (phase 11), a request without a session goes to /login, saying "timed out" when this
// browser had one, and comes back after. Behind Google's IAP (DASHBOARD_IAP_AUDIENCE set), every request must carry
// IAP's signed header, except the load balancer's health check. Without either, this lets everything through, as on
// the scan PC.

const signedIn = auth((request) => {
  const path = request.nextUrl.pathname;
  if (!needsSession(path)) return NextResponse.next();
  if (request.auth) {
    const next = NextResponse.next();
    if (!request.cookies.has(SIGNED_IN_COOKIE)) {
      next.cookies.set(SIGNED_IN_COOKIE, "1", { httpOnly: true, sameSite: "lax", path: "/", maxAge: 30 * 24 * 3600 });
    }
    return next;
  }
  const login = new URL("/login", request.nextUrl.origin);
  if (path !== "/") login.searchParams.set("from", `${path}${request.nextUrl.search}`);
  if (request.cookies.has(SIGNED_IN_COOKIE)) login.searchParams.set("reason", "timed_out");
  return NextResponse.redirect(login);
});

export async function proxy(request: NextRequest): Promise<Response> {
  const passed = await gate(request);
  if (passed.headers.get("x-middleware-next") !== "1") return passed;   // sent to sign in, or refused
  return (await unknownCall(request, passed)) ?? passed;
}

/** Sign-in or IAP, as described at the top; a response that lets the request through carries x-middleware-next. */
async function gate(request: NextRequest): Promise<Response> {
  // Auth.js's wrapper is typed for app routes; here it needs no route params.
  if (signInEnabled(process.env)) return (await signedIn(request, { params: Promise.resolve({}) })) ?? NextResponse.next();
  const audience = process.env.DASHBOARD_IAP_AUDIENCE?.trim();
  if (!audience || !needsSignIn(request.nextUrl.pathname)) return NextResponse.next();
  const verified = await verifyIapToken(request.headers.get(IAP_HEADER), audience, googleKeys());
  if (verified.ok) return NextResponse.next();
  console.warn(`Refused ${request.nextUrl.pathname}: ${verified.reason}`);
  return new NextResponse("Open the dashboard through the company sign-in.", {
    status: 401,
    headers: { "content-type": "text/plain; charset=utf-8", "cache-control": "no-store" },
  });
}

/**
 * A draft page for a call the ledger does not hold answers 404 (9 Nov 2026). Every page streams from the start
 * (app/loading.tsx), which fixes the status at 200, so the page's own notFound() can show the 404 page but not send the
 * code. This checks first and hands the request to an address no page answers, which Next serves as its 404. Only page
 * loads are checked: a server action posts to the same address. If the ledger does not answer, the page decides.
 */
async function unknownCall(request: NextRequest, passed: Response): Promise<Response | null> {
  if (request.method !== "GET") return null;
  const callId = draftPageCallId(request.nextUrl.pathname);
  if (!callId) return null;
  try {
    const [found] = await sql()`SELECT 1 AS found FROM calls WHERE id = ${callId} LIMIT 1`;
    if (found) return null;
  } catch {
    return null;
  }
  const missing = NextResponse.rewrite(new URL("/no-such-call", request.nextUrl.origin));
  for (const cookie of passed.headers.getSetCookie()) missing.headers.append("set-cookie", cookie);   // sign-in's first visit
  return missing;
}
