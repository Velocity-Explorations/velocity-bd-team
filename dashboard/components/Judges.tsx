import { Badge } from "@/components/bits";
import { JUDGES, judgesDisagree, type Verdicts } from "@/lib/judges";

/**
 * How Claude and Grok each judged a call, flagged when they disagree. `reasonsFor` names the
 * judges whose reason shows behind a toggle (the queue already has a column for Claude's).
 */
export function JudgeVerdicts({ verdicts, reasonsFor = [] }: { verdicts: Verdicts; reasonsFor?: string[] }) {
  return (
    <div className="judges">
      {JUDGES.map(({ key, label }) => {
        const judgment = verdicts[key];
        return (
          <div key={key} className="judge">
            <span className="who">{label}</span>
            <Badge value={judgment?.verdict} empty={key === "grok" ? "not yet" : "not reviewed"} />
            {reasonsFor.includes(key) && judgment?.reasoning ? (
              <details>
                <summary>why</summary>
                <p>{judgment.reasoning}</p>
              </details>
            ) : null}
          </div>
        );
      })}
      {judgesDisagree(verdicts) ? <span className="badge tone-warn">judges disagree</span> : null}
    </div>
  );
}
