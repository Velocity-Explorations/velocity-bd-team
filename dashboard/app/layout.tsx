import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./theme.css";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "BD Team", template: "%s | BD Team" },
  description: "Opportunity triage for Velocity Explorations, read straight from the ledger.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
