import { cookies, headers } from "next/headers";
import { auth } from "@/auth";
import { googleKeys, IAP_HEADER, verifyIapToken } from "./iap";
import { parseUsers, pickViewer, type Person } from "./people";
import { signInEnabled } from "./signin";

export const VIEWER_COOKIE = "bd_viewer";

export function allowlist(): Person[] {
  return parseUsers(process.env.DASHBOARD_USERS);
}

/** IAP's audience for this dashboard's backend service, when it is hosted behind Google's IAP. */
export function iapAudience(): string | null {
  return process.env.DASHBOARD_IAP_AUDIENCE?.trim() || null;
}

/** Lower-cased request header that names the viewer, when an auth proxy sets one. */
export function viewerHeader(): string | null {
  const name = process.env.DASHBOARD_USER_HEADER?.trim();
  return name ? name.toLowerCase() : null;
}

/** True once Google sign-in is set up (phase 11): the session alone then says who is viewing. */
export function sessionMode(): boolean {
  return signInEnabled(process.env);
}

/**
 * With Google sign-in, the session's email, checked on every call (Server Actions included, so they never rely on
 * proxy.ts alone); the picker's cookie counts for nothing then. Behind IAP, the email in its signed header. Behind
 * another proxy, its header. Otherwise the picker.
 */
export async function currentViewer(): Promise<string | null> {
  if (sessionMode()) {
    const session = await auth();
    return pickViewer({ users: allowlist(), headerMode: true, headerValue: session?.user?.email ?? null });
  }
  const audience = iapAudience();
  if (audience) {
    const verified = await verifyIapToken((await headers()).get(IAP_HEADER), audience, googleKeys());
    return pickViewer({ users: allowlist(), headerMode: true, headerValue: verified.ok ? verified.email : null });
  }
  const header = viewerHeader();
  return pickViewer({
    users: allowlist(),
    headerMode: header !== null,
    headerValue: header ? (await headers()).get(header) : null,
    cookieValue: (await cookies()).get(VIEWER_COOKIE)?.value ?? null,
  });
}
