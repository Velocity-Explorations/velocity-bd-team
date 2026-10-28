// Small presentational pieces shared by the pages.

import { ExternalLink } from "lucide-react";
import { Notice } from "@/components/Notice";
import type { Detail } from "@/lib/details";

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
  cancelled_by_agency: "grey",
  proposed: "warn",
  approved: "info",
  applying: "info",
  applied: "good",
  failed: "bad",
};

const LABELS: Record<string, string> = {
  not_relevant: "not relevant",
  skipped_timeout: "timeout",
  no_award: "no award",
  cancelled_by_agency: "cancelled by the agency",
  proposed: "waiting",
};

export function toneOf(value: string | null | undefined): string {
  return (value && TONES[value]) || "grey";
}

export function Badge({ value, empty = "none" }: { value: string | null | undefined; empty?: string }) {
  if (!value) return <span className="badge tone-none">{empty}</span>;
  return <span className={`badge tone-${toneOf(value)}`}>{LABELS[value] ?? value}</span>;
}

/** What an action reports, as a notice: Refused for an error, Done for the rest. */
export function Flash({ notice, error, link }: { notice?: string; error?: string; link?: { href: string; label: string } | null }) {
  if (error) {
    return (
      <Notice key={error} tone="conflict">
        {error}
      </Notice>
    );
  }
  if (notice) {
    return (
      <Notice key={notice} tone="good">
        {notice}
        {link ? (
          <>
            {" "}
            <a href={link.href}>{link.label}</a>
          </>
        ) : null}
      </Notice>
    );
  }
  return null;
}

/** A call's title, linked to its page on the portal in a new tab, with the external-link icon. */
export function TitleLink({ title, url, fallback }: { title: string | null; url: string | null; fallback: string }) {
  const text = title || fallback;
  return url ? (
    <a href={url} target="_blank" rel="noreferrer" className="call-title">
      {text}
      <ExternalLink aria-hidden="true" />
    </a>
  ) : (
    <span className="call-title">{text}</span>
  );
}

/** Hover text on something that is not a link: focusable and dotted, so the keyboard reaches it too. */
function tip(title: string | undefined, className = ""): { title?: string; tabIndex?: number; className?: string } {
  if (!title) return className ? { className } : {};
  return { title, tabIndex: 0, className: `${className} tip`.trim() };
}

/** A call's portal details (lib/details.ts), after the portal name in a row's meta line. */
export function Details({ items }: { items: Detail[] }) {
  return (
    <>
      {items.map((item, i) =>
        item.tone ? (
          <span key={i} {...tip(item.title, `badge tone-${item.tone}`)}>
            {item.text}
          </span>
        ) : item.href ? (
          <a key={i} href={item.href} title={item.title} {...(item.href.startsWith("mailto:") ? {} : { target: "_blank", rel: "noreferrer" })}>
            {item.text}
          </a>
        ) : (
          <span key={i} {...tip(item.title)}>
            {item.text}
          </span>
        ),
      )}
    </>
  );
}

