import { cookies, headers } from "next/headers";
import { parseUsers, pickViewer, type Person } from "./people";

export const VIEWER_COOKIE = "bd_viewer";

export function allowlist(): Person[] {
  return parseUsers(process.env.DASHBOARD_USERS);
}

/** Lower-cased request header that names the viewer, when an auth proxy sets one. */
export function viewerHeader(): string | null {
  const name = process.env.DASHBOARD_USER_HEADER?.trim();
  return name ? name.toLowerCase() : null;
}

export async function currentViewer(): Promise<string | null> {
  const header = viewerHeader();
  return pickViewer({
    users: allowlist(),
    headerMode: header !== null,
    headerValue: header ? (await headers()).get(header) : null,
    cookieValue: (await cookies()).get(VIEWER_COOKIE)?.value ?? null,
  });
}
