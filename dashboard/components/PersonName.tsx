import type { ReactNode } from "react";
import { Avatar } from "@/components/Avatar";
import { faceLookup } from "@/lib/me";

/**
 * A person's name with their picture before it, or their initials while they have none (David, 9 Nov 2026): on votes,
 * notes, Changed by lines and Working with. `by` is the name as the ledger records it, a Slack id included; the
 * children are the name as shown. Server only: it reads the faces once per request.
 */
export async function PersonName({ by, children }: { by: string | null | undefined; children?: ReactNode }) {
  const face = (await faceLookup())(by);
  if (!face) return <>{children}</>;
  return (
    <span className="person">
      <Avatar initials={face.initials} picture={face.picture} size="tiny" />
      <span>{children ?? by}</span>
    </span>
  );
}
