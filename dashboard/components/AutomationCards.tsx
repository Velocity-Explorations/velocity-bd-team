import { ViewCards } from "@/components/ViewCards";
import { formatTime } from "@/lib/format";
import { kindsLine } from "@/lib/home";
import { countDecidedRequests, countProblemRuns, countRuns, judgeAgreement, lastCompletedRun, waitingRequests } from "@/lib/queries";
import { timeZone } from "@/lib/me";
import { automationCards, type AutomationPage } from "@/lib/views";

/** Automation's row of view cards (PRO-570, PRO-573): Agent update requests, Decided requests, Scans, Scan problems, Judges agree. */
export async function AutomationCards({ current }: { current: AutomationPage }) {
  const [requests, decided, runs, problems, latest, agreement] = await Promise.all([
    waitingRequests(),
    countDecidedRequests(),
    countRuns(),
    countProblemRuns(),
    lastCompletedRun(),
    judgeAgreement(),
  ]);
  const finished = latest ? formatTime(latest.finished_at ?? latest.started_at, await timeZone()) : "";
  return (
    <ViewCards
      label="Automation views"
      cards={automationCards({
        current,
        waiting: requests.length,
        kinds: kindsLine(requests.map((r) => r.kind)),
        decided,
        runs,
        problems,
        lastRun: finished ? `last completed ${finished}` : "none completed yet",
        agree: agreement,
      })}
    />
  );
}
