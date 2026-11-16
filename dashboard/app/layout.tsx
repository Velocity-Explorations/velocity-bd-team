import type { Metadata } from "next";
import { cookies } from "next/headers";
import { Suspense, type ReactNode } from "react";
import { AskPanel } from "@/components/AskPanel";
import { ASK_COOKIE, askLeftOpen } from "@/lib/ask";
import { me } from "@/lib/me";
import { hasChat } from "@/lib/queries";
import "./theme.css";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "BD Team", template: "%s | BD Team" },
  description: "Opportunity triage for Velocity Explorations, read straight from the ledger.",
};

/** Ask Grok's panel, once migration 016 is applied. */
async function Ask({ open }: { open: boolean }) {
  if (!(await hasChat().catch(() => false))) return null;
  const { viewer } = await me().catch(() => ({ viewer: null }));
  return <AskPanel viewer={viewer} initialOpen={open} />;
}

/**
 * Every page, and Ask Grok's panel beside it (David, 16 Nov 2026). The panel sits here rather than in each page's Shell,
 * because a layout stays mounted as the page changes: the panel stays open, in place, with its conversation. Left open,
 * an empty panel holds its room while the real one loads, so the page does not jump sideways when it arrives.
 */
export default async function RootLayout({ children }: { children: ReactNode }) {
  const open = askLeftOpen((await cookies()).get(ASK_COOKIE)?.value);
  return (
    <html lang="en">
      <body>
        {children}
        <Suspense fallback={open ? <aside className="ask-panel" aria-hidden="true" /> : null}>
          <Ask open={open} />
        </Suspense>
      </body>
    </html>
  );
}
