"use client";

export default function ErrorPage({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  return (
    <main className="error-page">
      <h1>This page could not load</h1>
      <p>
        The usual cause is that the ledger database is unreachable, or that DATABASE_URL is missing from
        dashboard/.env.local.
      </p>
      <pre>
        {error.message}
        {error.digest ? `\n(digest ${error.digest})` : ""}
      </pre>
      <button type="button" onClick={() => retry()}>
        Try again
      </button>
    </main>
  );
}
