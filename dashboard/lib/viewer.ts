import { cookies, headers } from "next/headers";
import { auth } from "@/auth";
import { googleKeys, IAP_HEADER, verifyIapToken } from "./iap";
import { parseUsers, pickViewer, type Person } from "./people";
import { signInEnabled } from "./signin";
import { knownPeople, personByEmail } from "./team";

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
    const email = (await auth())?.user?.email?.trim().toLowerCase();
    if (!email) return null;
    // DASHBOARD_USERS's name for this email, else the name recorded at the person's first sign-in.
    return pickViewer({ users: allowlist(), headerMode: true, headerValue: email }) ?? (await personByEmail(email));
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

/**
 * The team for Working with and the people panels: DASHBOARD_USERS, and with Google sign-in everyone who has signed in
 * (people, migration 010) and is not on it already.
 */
export async function team(): Promise<Person[]> {
  const listed = allowlist();
  if (!sessionMode()) return listed;
  const extra = (await knownPeople()).filter((k) => !listed.some((u) => u.email?.toLowerCase() === k.email || u.name === k.name));
  return [...listed, ...extra.map((k) => ({ name: k.name, email: k.email, slackId: null }))];
}
