import type { Metadata } from "next";
import { ProposalsView } from "@/components/ProposalsView";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Results" };

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

/** Proposals, Results (P5, PRO-575): results recorded here and the Proposal Register, with win rate by portal (N4). */
export default async function ResultsPage({ searchParams }: { searchParams: SearchParams }) {
  return <ProposalsView view="results" sp={await searchParams} />;
}
