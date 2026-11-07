import postgres from "postgres";

// One Postgres client per server process, created on first use so `next build` never needs
// DATABASE_URL. Never log the URL: it carries the password.

type Sql = ReturnType<typeof postgres>;

const holder = globalThis as unknown as { __ledgerSql?: Sql };

/**
 * Up to eight connections, so a page's queries and its frame's run together rather than three at a time, each a round
 * trip of about 60 ms. Each is kept ten minutes after its last query: opening one through Supabase's pooler takes about
 * 0.7 s, which a 20-second idle timeout made nearly every click pay. After ten idle minutes they close, so a dashboard
 * nobody is using holds none of the pooler's connections. prepare: false works through Supabase's transaction pooler
 * as well as the session pooler.
 */
export const POOL = { max: 8, idle_timeout: 600, connect_timeout: 10, prepare: false } as const;

export function sql(): Sql {
  if (holder.__ledgerSql) return holder.__ledgerSql;
  const url = process.env.DATABASE_URL;
  if (!url) {
    throw new Error("DATABASE_URL is not set. Add it to dashboard/.env.local (see dashboard/.env.example).");
  }
  if (!/^postgres(ql)?:\/\//i.test(url)) {
    throw new Error("DATABASE_URL must be a postgres:// URL. The dashboard does not read the SQLite dev ledger.");
  }
  holder.__ledgerSql = postgres(url, POOL);
  return holder.__ledgerSql;
}
