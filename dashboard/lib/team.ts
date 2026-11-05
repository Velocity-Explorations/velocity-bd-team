// The team behind Google sign-in (phase 11): everyone who has signed in with their Velocity Google account, kept in the
// ledger's people table (migration 010) so they can be chosen for Working with and named in history.

import { sql } from "./db";
import { parseUsers } from "./people";
import { teamName } from "./signin";
import { isoNow } from "./format";
import { present } from "./schema";
import { cacheMs, forget, remember } from "./remember";

export type KnownPerson = { email: string; name: string };

async function hasPeople(): Promise<boolean> {
  return present("people", async () => {
    const [row] = await sql()<{ present: boolean }[]>`SELECT to_regclass('people') IS NOT NULL AS present`;
    return Boolean(row?.present);
  });
}

/** Everyone who has signed in, by name. Empty before migration 010. Kept for a minute (remember.ts). */
export function knownPeople(): Promise<KnownPerson[]> {
  return remember("people", cacheMs(process.env), async () => {
    if (!(await hasPeople())) return [];
    return [...(await sql()<KnownPerson[]>`SELECT email, name FROM people ORDER BY name`)];
  });
}

/** The name a signed-in person decides under, as recorded at their first sign-in. Kept for a minute. */
export function personByEmail(email: string): Promise<string | null> {
  const lower = email.trim().toLowerCase();
  return remember(`person:${lower}`, cacheMs(process.env), async () => {
    if (!(await hasPeople())) return null;
    const [row] = await sql()<{ name: string }[]>`SELECT name FROM people WHERE email = ${lower}`;
    return row?.name ?? null;
  });
}

/** A sign-in, recorded: a new person gets their name (lib/signin.ts teamName), anyone else just their latest sign-in. */
export async function recordSignIn(email: string, googleName: string | null): Promise<void> {
  if (!(await hasPeople())) return;
  const lower = email.trim().toLowerCase();
  const now = isoNow();
  const name = teamName(lower, googleName, parseUsers(process.env.DASHBOARD_USERS), await knownPeople());
  await sql()`
    INSERT INTO people (email, name, first_seen_at, last_seen_at) VALUES (${lower}, ${name}, ${now}, ${now})
    ON CONFLICT (email) DO UPDATE SET last_seen_at = EXCLUDED.last_seen_at`;
  forget("people");
  forget("person");
}
