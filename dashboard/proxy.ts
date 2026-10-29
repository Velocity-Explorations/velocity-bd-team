import { NextResponse, type NextRequest } from "next/server";
import { auth } from "@/auth";
import { googleKeys, IAP_HEADER, needsSignIn, verifyIapToken } from "@/lib/iap";
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
