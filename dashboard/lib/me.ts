// The viewer and their Profile settings (U2 to U6, PRO-574), read once per request. Server only.

import { headers } from "next/headers";
import { cache } from "react";
import { initials } from "./nav";
import { displayPerson } from "./people";
import { pictureUrl } from "./picture";
import { callsHref, isFreshArrival, isValidTimeZone, parseDefaultFilters, withDefaultFilters, type DefaultFilters } from "./profile";
import { workerReadiness } from "./proposals";
import { allProfiles, pictureStamps, workerStatus, type ProfileRow } from "./queries";
import { displayTimeZone } from "./settings";
import { allowlist, currentViewer } from "./viewer";

/** Every saved profile, by name. */
export const profiles = cache(allProfiles);

/** Who is deciding, and their saved profile if they have one. */
export const me = cache(async (): Promise<{ viewer: string | null; profile: ProfileRow | null }> => {
  const viewer = await currentViewer();
  return { viewer, profile: viewer ? ((await profiles()).get(viewer) ?? null) : null };
});

/** The zone every time shows in: the viewer's choice, else the dashboard's America/Denver (U5). */
export async function timeZone(): Promise<string> {
  const { profile } = await me();
  return profile?.time_zone && isValidTimeZone(profile.time_zone) ? profile.time_zone : displayTimeZone();
}

/** The viewer's default filters for Calls, or null (U4). */
export async function defaultFilters(): Promise<DefaultFilters | null> {
  const { profile } = await me();
  return profile?.default_filters ? parseDefaultFilters(profile.default_filters) : null;
}

/** How a person shows on votes, notes and the account menu: their display name, else their name (U2). */
export async function labeler(): Promise<(name: string) => string> {
  const all = await profiles();
  return (name) => all.get(name)?.display_name || name;
}

/** A person's initials: the ones they set, else from their shown name. */
export async function initialsOf(name: string): Promise<string> {
  const profile = (await profiles()).get(name);
  return profile?.initials || initials(profile?.display_name || name);
}

/** When each person's picture was set, read once per request; a failed read shows initials, never a broken frame. */
export const pictures = cache(() => pictureStamps().catch(() => new Map<string, string>()));

/** Where a person's picture is fetched, or null while they have none (David, 9 Nov 2026). */
export async function pictureOf(name: string): Promise<string | null> {
  const at = (await pictures()).get(name);
  return at ? pictureUrl(name, at) : null;
}

/** A person as they show beside their name: their picture, else their initials. */
export type Face = { initials: string; picture: string | null };

/**
 * Each person's face, looked up by the name the ledger records (a Slack id becomes the allowlisted name), once per
 * request (David, 9 Nov 2026). Null for no name.
 */
export const faceLookup = cache(async (): Promise<(by: string | null | undefined) => Face | null> => {
  const [all, stamps] = await Promise.all([profiles(), pictures()]);
  const users = allowlist();
  return (by) => {
    const name = displayPerson(by, users);
    if (!name) return null;
    const profile = all.get(name);
    const at = stamps.get(name);
    return { initials: profile?.initials || initials(profile?.display_name || name), picture: at ? pictureUrl(name, at) : null };
  };
});

/** Whether this request opens the dashboard, not a move between its own pages (U3, U4). */
async function freshArrival(): Promise<boolean> {
  const h = await headers();
  return isFreshArrival(h.get("referer"), h.get("host") ?? "");
}

/** Opening `/` takes a person who chose Calls there, with their default filters (U3). */
export async function openingRedirect(): Promise<string | null> {
  const { profile } = await me();
  if (profile?.opens !== "calls" || !(await freshArrival())) return null;
  return callsHref(parseDefaultFilters(profile.default_filters));
}

/** Calls opened fresh with no bar filter in its address takes the person's default filters (U4). */
export async function defaultsRedirect(path: string, params: Record<string, string | string[] | undefined>): Promise<string | null> {
  const filters = await defaultFilters();
  if (!filters || !(await freshArrival())) return null;
  return withDefaultFilters(path, params, filters);
}

/** Whether drafting can start (P8), and when the worker was last seen, once per request. */
export const drafting = cache(async (): Promise<{ readiness: "ready" | "offline" | "not set up"; seenAt: string | null }> => {
  const worker = await workerStatus();
  return { readiness: workerReadiness(worker, new Date()), seenAt: worker?.seen_at ?? null };
});
