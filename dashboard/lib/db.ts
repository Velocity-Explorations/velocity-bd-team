import postgres from "postgres";

// One Postgres client per server process, created on first use so `next build` never needs
// DATABASE_URL. Never log the URL: it carries the password.

type Sql = ReturnType<typeof postgres>;

const holder = globalThis as unknown as { __ledgerSql?: Sql };

export function sql(): Sql {
  if (holder.__ledgerSql) return holder.__ledgerSql;
  const url = process.env.DATABASE_URL;
  if (!url) {
    throw new Error("DATABASE_URL is not set. Add it to dashboard/.env.local (see dashboard/.env.example).");
  }
  if (!/^postgres(ql)?:\/\//i.test(url)) {
    throw new Error("DATABASE_URL must be a postgres:// URL. The dashboard does not read the SQLite dev ledger.");
  }
  holder.__ledgerSql = postgres(url, {
    max: 3,
    idle_timeout: 20,
    connect_timeout: 10,
    prepare: false, // works through Supabase's transaction pooler as well as the session pooler
  });
  return holder.__ledgerSql;
}
