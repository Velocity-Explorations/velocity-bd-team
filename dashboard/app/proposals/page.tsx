import type { Metadata } from "next";
import { ProposalsView } from "@/components/ProposalsView";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Proposals" };

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

/** Proposals (PRO-575): To draft, or Closing in 14 days and Drafting by their `view`. */
export default async function ProposalsPage({ searchParams }: { searchParams: SearchParams }) {
  const sp = await searchParams;
  const view = sp.view === "closing" ? "closing" : sp.view === "drafting" ? "drafting" : "to-draft";
  return <ProposalsView view={view} sp={sp} />;
}
