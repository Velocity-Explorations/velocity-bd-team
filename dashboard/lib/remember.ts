// Reads that change only when a scan runs, someone signs in or a setting is saved, kept for a short while in this
// server process so each page does not ask the ledger again: every read is a round trip of about 60 ms to Supabase.
// Decisions, queues and drafts are never kept. A write that changes a kept read calls forget, so the next page reads it
// fresh. No imports, so `node --test` can load it directly.

const kept = new Map<string, { until: number; value: Promise<unknown> }>();

/** How long reads are kept: DASHBOARD_CACHE_SECONDS, else a minute. The workspace tests set 0. */
export function cacheMs(env: Record<string, string | undefined>): number {
  const raw = env.DASHBOARD_CACHE_SECONDS?.trim() ?? "";
  return /^\d+$/.test(raw) ? Number(raw) * 1000 : 60_000;
}

/** The kept answer to `read` under `name`, read again once `ms` have passed; pages asking at once share one read. */
export function remember<T>(name: string, ms: number, read: () => Promise<T>, now: () => number = Date.now): Promise<T> {
  const found = kept.get(name);
  if (found && found.until > now()) return found.value as Promise<T>;
  const value = read();
  if (ms > 0) {
    kept.set(name, { until: now() + ms, value });
    value.catch(() => kept.delete(name));   // a failed read is not kept
  }
  return value;
}

/** Drop what is kept under `name`, and under `name:` followed by anything. */
export function forget(name: string): void {
  for (const key of [...kept.keys()]) if (key === name || key.startsWith(`${name}:`)) kept.delete(key);
}
