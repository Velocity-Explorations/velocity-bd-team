import type { Metadata } from "next";
import { Shell } from "@/components/Shell";
import { TitleLink } from "@/components/bits";
import { agreementText, JUDGES } from "@/lib/judges";
import { displayPerson } from "@/lib/people";
import { judgeAgreement, judgeRecords, scoreboardRows } from "@/lib/queries";
import { judgedMisses, peopleAgreement, personRecords } from "@/lib/scoreboard";
import { allowlist } from "@/lib/viewer";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Judges" };

const JUDGE_KEYS = JUDGES.map((j) => j.key);
const LABEL: Record<string, string> = Object.fromEntries(JUDGES.map((j) => [j.key, j.label]));

function pct(part: number, whole: number): string {
  return whole ? `${Math.round((100 * part) / whole)}%` : "n/a";
}

function count(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`;
}

export default async function JudgesPage() {
  const [records, rows, agreement] = await Promise.all([judgeRecords(), scoreboardRows(), judgeAgreement()]);
  const users = allowlist();
  const name = (by: string) => displayPerson(by, users);

  return (
    <Shell current="judges">
      <div className="page-head">
        <div>
          <h1>Judges</h1>
          <p className="muted">
            How Claude and Grok compare with your decisions. Pursue and submitted count as yes, not relevant and
            dismissed as no. A verdict counts only if the judge gave it before anyone decided the call, because decided
            calls become examples in the judges&apos; prompt.
            {agreement && agreement.both ? ` ${agreementText(agreement.both, agreement.agree)}` : ""}
          </p>
        </div>
      </div>

      {records === null || rows === null ? (
        <div className="empty">
          <p className="title">The scoreboard needs migration 004.</p>
          <p className="muted">
            Run <code>python -m ledger.migrate</code> against the live database, then reload this page.
          </p>
        </div>
      ) : (
        <Scoreboard records={records} rows={rows} name={name} />
      )}
    </Shell>
  );
}

function Scoreboard({
  records,
  rows,
  name,
}: {
  records: NonNullable<Awaited<ReturnType<typeof judgeRecords>>>;
  rows: NonNullable<Awaited<ReturnType<typeof scoreboardRows>>>;
  name: (by: string) => string;
}) {
  const people = personRecords(rows.decisions, rows.judgments, JUDGE_KEYS, name);
  const pairs = peopleAgreement(rows.decisions, name);
  const misses = new Map<string, { title: string | null; url: string | null; judges: string[] }>();
  for (const m of judgedMisses(rows.calls, rows.judgments, JUDGE_KEYS)) {
    const entry = misses.get(m.id) ?? { title: m.title, url: m.url, judges: [] };
    entry.judges.push(LABEL[m.judge] ?? m.judge);
    misses.set(m.id, entry);
  }

  return (
    <>
      <h2>Against the team&apos;s decisions</h2>
      {records.length === 0 ? (
        <p className="muted">No decided call has a verdict from before its decision yet.</p>
      ) : (
        <div className="tiles">
          {records.map((r) => {
            const maybe = r.decided - r.matches - r.misses - r.false_alarms;
            return (
              <div className="tile" key={r.judge}>
                <div className="label">{LABEL[r.judge] ?? r.judge}</div>
                <div className="value num">{pct(r.matches, r.decided)}</div>
                <div className="muted num">
                  matched {r.matches} of {r.decided}; {count(r.misses, "miss", "misses")},{" "}
                  {count(r.false_alarms, "false alarm", "false alarms")}, {maybe} maybe
                </div>
              </div>
            );
          })}
        </div>
      )}
      <p className="muted">
        A miss is a no on a call the team pursued. A false alarm is a yes on a call the team passed on.
      </p>

      <h2>By person</h2>
      {people.length === 0 ? (
        <p className="muted">Nobody has decided a call yet.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Person</th>
                <th>Calls decided</th>
                {JUDGES.map((j) => (
                  <th key={j.key}>{j.label} matched</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {people.map((p) => (
                <tr key={p.person}>
                  <td>{p.person}</td>
                  <td className="num">{p.decided}</td>
                  {JUDGES.map((j) => {
                    const s = p.withJudge[j.key];
                    return (
                      <td key={j.key} className="num">
                        {s.judged ? `${s.matches} of ${s.judged} (${pct(s.matches, s.judged)})` : "none judged in time"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2>Between people</h2>
      {people.length < 2 ? (
        <p className="muted">
          Only one person has decided calls so far. Everyone listed in DASHBOARD_USERS keeps their own decisions, and
          they are compared here once two people have decided the same call.
        </p>
      ) : pairs.length === 0 ? (
        <p className="muted">
          No call has decisions from two people yet. On All calls, use &quot;add yours&quot; on a call someone else
          decided.
        </p>
      ) : (
        <ul>
          {pairs.map((p) => (
            <li key={`${p.a}|${p.b}`}>
              {p.a} and {p.b} both decided {count(p.shared, "call", "calls")} and agree on {p.agree} ({pct(p.agree, p.shared)}).
            </li>
          ))}
        </ul>
      )}

      <h2>Pursued calls a judge said no to</h2>
      {misses.size === 0 ? (
        <p className="muted">None so far.</p>
      ) : (
        <ul>
          {[...misses].map(([id, m]) => (
            <li key={id}>
              <TitleLink title={m.title} url={m.url} fallback={id} />{" "}
              <span className="muted">({m.judges.join(" and ")} said no)</span>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
