// The tables and columns the dashboard checks for before using them, since a migration may not be applied to a
// ledger yet. Each check was a database round trip on every page; a migration is never undone, so one found is
// remembered for the life of the server process. One not found is checked again next time. No imports, so
// `node --test` can load it directly.

const found = new Set<string>();

/** True once `look` has found `name`, remembered from then on; until then, whatever `look` finds now. */
export async function present(name: string, look: () => Promise<boolean>): Promise<boolean> {
  if (found.has(name)) return true;
  const yes = await look();
  if (yes) found.add(name);
  return yes;
}
