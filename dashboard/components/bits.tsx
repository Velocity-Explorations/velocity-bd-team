// Small presentational pieces shared by the pages.

const TONES: Record<string, string> = {
  yes: "good",
  maybe: "warn",
  no: "bad",
  pursue: "good",
  submitted: "info",
  not_relevant: "grey",
  dismissed: "grey",
  completed: "good",
  running: "info",
  skipped_timeout: "warn",
  error: "bad",
  kept: "good",
  rejected: "grey",
  pending: "info",
  won: "good",
  lost: "bad",
  shortlisted: "info",
  no_award: "grey",
  withdrawn: "grey",
};

const LABELS: Record<string, string> = {
  not_relevant: "not relevant",
  skipped_timeout: "timeout",
  no_award: "no award",
};

export function toneOf(value: string | null | undefined): string {
  return (value && TONES[value]) || "grey";
}

export function Badge({ value, empty = "none" }: { value: string | null | undefined; empty?: string }) {
  if (!value) return <span className="badge tone-none">{empty}</span>;
  return <span className={`badge tone-${toneOf(value)}`}>{LABELS[value] ?? value}</span>;
}

export function Flash({ notice, error }: { notice?: string; error?: string }) {
  if (error) {
    return (
      <p className="flash flash-error" role="alert">
        {error}
      </p>
    );
  }
  if (notice) {
    return (
      <p className="flash flash-ok" role="status">
        {notice}
      </p>
    );
  }
  return null;
}

export function TitleLink({ title, url, fallback }: { title: string | null; url: string | null; fallback: string }) {
  const text = title || fallback;
  return url ? (
    <a href={url} target="_blank" rel="noreferrer">
      {text}
    </a>
  ) : (
    <span>{text}</span>
  );
}
