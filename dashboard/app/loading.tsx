import { FileText, House, Inbox, Workflow, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { SECTIONS, type Section } from "@/lib/nav";

const ICONS: Record<Section, LucideIcon> = { home: House, calls: Inbox, proposals: FileText, automation: Workflow };

/**
 * What a page shows while its data loads: the frame without its counts, and a few placeholder rows. A page takes a
 * second or so to read the ledger, and without this a click changed nothing on screen until it was done. Plain divs,
 * not header and main: React keeps this beside the arriving page for up to 300 ms, and it must not read as a second
 * page's landmarks.
 */
export default function Loading() {
  return (
    <>
      <div className="topbar">
        <Link href="/" className="brand">
          <img src="/velocity-mark-white.png" alt="" width={21} height={16} />
          BD Team
        </Link>
        <nav aria-label="Sections">
          {SECTIONS.map(({ key, label, href }) => {
            const Icon = ICONS[key];
            return (
              <Link key={key} href={href}>
                <Icon aria-hidden="true" />
                {label}
              </Link>
            );
          })}
        </nav>
      </div>
      <div className="loading-page" role="status" aria-live="polite">
        <p className="loading-word">Loading</p>
        {[0, 1, 2, 3, 4, 5].map((n) => (
          <div key={n} className="loading-bar" />
        ))}
      </div>
    </>
  );
}
