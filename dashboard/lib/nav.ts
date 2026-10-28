// The top bar's four sections and the account button's initials (PRO-570). No imports, so
// `node --test` can load it directly.

export type Section = "home" | "calls" | "proposals" | "automation";

/** The sections in the bar's order. Automation opens on Agent update requests (N1). */
export const SECTIONS: { key: Section; label: string; href: string }[] = [
  { key: "home", label: "Home", href: "/" },
  { key: "calls", label: "Calls", href: "/review" },
  { key: "proposals", label: "Proposals", href: "/proposals" },
  { key: "automation", label: "Automation", href: "/requests" },
];

/** What a section's count chip counts, read aloud in place of the bare number (N3). */
export function countLabel(section: Exclude<Section, "home">, n: number): string {
  if (section === "calls") return `${n} waiting for you`;
  if (section === "proposals") return `${n} to draft, ready for you or overdue`;
  return `${n} ${n === 1 ? "request" : "requests"} waiting`;
}

/** "David Wood" -> "DW"; one name gives its first two letters. */
export function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[words.length - 1][0]).toUpperCase();
}
