import { ViewCards } from "@/components/ViewCards";
import { formatTime } from "@/lib/format";
import { kindsLine } from "@/lib/home";
import { countRuns, judgeAgreement, lastCompletedRun, waitingRequests } from "@/lib/queries";
import { displayTimeZone } from "@/lib/settings";
import { automationCards, type AutomationPage } from "@/lib/views";

/** Automation's row of view cards (PRO-570): Agent update requests, Scans, Judges agree. */
export async function AutomationCards({ current }: { current: AutomationPage }) {
  const [requests, runs, latest, agreement] = await Promise.all([waitingRequests(), countRuns(), lastCompletedRun(), judgeAgreement()]);
  const finished = latest ? formatTime(latest.finished_at ?? latest.started_at, displayTimeZone()) : "";
  return (
    <ViewCards
      label="Automation views"
      cards={automationCards({
        current,
        waiting: requests.length,
        kinds: kindsLine(requests.map((r) => r.kind)),
        runs,
        lastRun: finished ? `last completed ${finished}` : "none completed yet",
        agree: agreement,
      })}
    />
  );
}
