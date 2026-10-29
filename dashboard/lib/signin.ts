// Google sign-in inside the dashboard (U7, PW17, phase 11): who may sign in (any Velocity Google account), the name
// they decide under, which pages need a session, where a person returns to, and what the sign-in page says. Auth.js does the OAuth (auth.ts); these are its rules. Sign-in is
// on only once its Google client is set, so until then the dashboard keeps the name picker. No imports, so
// `node --test` can load it directly.

type Env = Record<string, string | undefined>;
type Person = { name: string; email: string | null };

/** The account cookie Auth.js keeps for a session lasts this long; then the person is asked to sign in again. */
export const SESSION_HOURS = 12;
/** Set while a person has had a session in this browser, so its end reads "timed out" rather than nothing. */
export const SIGNED_IN_COOKIE = "bd_was_signed_in";

export function signInEnabled(env: Env): boolean {
  return Boolean(env.AUTH_GOOGLE_ID?.trim() && env.AUTH_GOOGLE_SECRET?.trim() && env.AUTH_SECRET?.trim());
}

/** The Google Workspace domain whose accounts may sign in. */
export function signInDomain(env: Env): string {
  return (env.DASHBOARD_DOMAIN?.trim() || "velocityexplorations.com").toLowerCase();
}

/**
 * A Google account gets in when Google verified its email and it belongs to the company's Workspace (Google's `hd`, and
 * the email's own domain). Since 29 Oct that is everyone at Velocity: no list to be on, nobody to ask.
 */
export function allowedSignIn(account: { email: string | null; verified: boolean; hd: string | null }, domain: string): boolean {
  const email = (account.email ?? "").trim().toLowerCase();
  return Boolean(email) && account.verified && (account.hd ?? "").toLowerCase() === domain && email.endsWith(`@${domain}`);
}

/**
 * The name a person decides under: DASHBOARD_USERS's name for their email, else the name first recorded when they
 * signed in, else their Google name. A name somebody else already has gets the email after it, so two people's
 * decisions are never mixed up.
 */
export function teamName(email: string, googleName: string | null | undefined, users: Person[], known: { email: string; name: string }[]): string {
  const lower = email.trim().toLowerCase();
  const listed = users.find((u) => u.email?.toLowerCase() === lower);
  if (listed) return listed.name;
  const recorded = known.find((k) => k.email.toLowerCase() === lower);
  if (recorded) return recorded.name;
  const name = (googleName ?? "").trim().replace(/\s+/g, " ") || lower.split("@")[0];
  const taken = users.some((u) => u.name === name) || known.some((k) => k.name === name);
  return taken ? `${name} (${lower})` : name;
}

/** Pages that need a session: everything but the sign-in page, Auth.js's own routes, the health check, and the files the
 *  sign-in page itself needs (Next's built files, and the public logo, fonts and images). */
export function needsSession(path: string): boolean {
  return !(path === "/login" || path.startsWith("/api/auth/") || path === "/healthz" || path.startsWith("/_next/")
    || /\.(png|jpe?g|svg|ico|webp|woff2?|ttf|css|js|map|txt)$/i.test(path));
}

/** Where a person goes after signing in: a page of this dashboard, never another site or back to sign-in. */
export function safeFrom(value: string | null | undefined): string {
  const path = (value ?? "").trim();
  if (!path.startsWith("/") || path.startsWith("//") || path.startsWith("/login") || path.startsWith("/api/auth")) return "/";
  return path;
}

const ERRORS: Record<string, string> = {
  AccessDenied: "That Google account is not a Velocity account. Sign in with your velocityexplorations.com account.",
  OAuthCallbackError: "Sign-in was cancelled.",
  Configuration: "Sign-in is not set up correctly. Tell an admin.",
};

/** The sign-in page's message (U7): signed out, timed out, not allowed or cancelled; null when there is none. */
export function loginMessage(params: { reason?: string | null; error?: string | null }): string | null {
  if (params.error) return ERRORS[params.error] ?? "Sign-in did not finish. Try again.";
  if (params.reason === "signed_out") return "You are signed out.";
  if (params.reason === "timed_out") return "Your session timed out. Sign in again to carry on.";
  return null;
}
