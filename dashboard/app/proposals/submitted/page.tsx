import type { Metadata } from "next";
import { ProposalsView } from "@/components/ProposalsView";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Submitted and waiting" };

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

/** Proposals, Submitted and waiting (P4, PRO-575): its own address, kept from before the views (N4). */
export default async function SubmittedPage({ searchParams }: { searchParams: SearchParams }) {
  return <ProposalsView view="submitted" sp={await searchParams} />;
}
