"use client";

import { Sparkles } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { startDraftAction, suggestDraftAction } from "@/app/actions";
import { Avatar } from "@/components/Avatar";
import { POLL_MS } from "@/lib/ask";
import { FORMATS, folderName } from "@/lib/proposals";
import { parseSuggestion, suggestStatus, withSuggestedFirst, type Suggestion, type SuggestionRow } from "@/lib/suggest";

type Chosen = { id: string; title: string; portal: string; due: string; format: string };
type Approval = "every_step" | "key_gates";
const GIVE_UP_MS = 3 * 60 * 1000;   // stop waiting on a suggestion after three minutes

/**
 * Start the draft (P6, PRO-576), one dialog per page. Any button marked data-start-draft opens it for
 * its call, from the call's data attributes; so does `?start=<call id>` once the page has that call's
 * button (after Pursue and start the draft). Its Start button is the person's approval to spend.
 * Until the worker has run, it says Drafting is not set up yet (P8).
 *
 * With `suggests` (migration 017; David, 7 Nov 2026), Suggest what to include asks Claude, through run.py --assistant,
 * for the format, the approval mode, a Direction and the past work to build on, and fills them in for the person to
 * change. The newest suggestion for the call fills the dialog in when it opens.
 */
export function StartDraftDialog({ people, owner, readiness, lastSeen, pastWork, indexed, suggests = false }: {
  people: { name: string; label: string; initials?: string; picture?: string | null }[];
  owner: string | null;
  readiness: "ready" | "offline" | "not set up";
  lastSeen: string | null;
  pastWork: { title: string; items: { id: string; label: string }[] }[];
  indexed: string | null;
  suggests?: boolean;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  const [call, setCall] = useState<Chosen | null>(null);
  const [returnTo, setReturnTo] = useState("/proposals");
  const [format, setFormat] = useState(FORMATS[0]);
  const [approval, setApproval] = useState<Approval>("every_step");
  const [direction, setDirection] = useState("");
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [suggestion, setSuggestion] = useState<Suggestion | null>(null);
  const [suggestedAt, setSuggestedAt] = useState<string | null>(null);
  const [waiting, setWaiting] = useState<{ state: string; seenAt: string | null; now: number; since: number } | null>(null);
  const [suggestError, setSuggestError] = useState("");
  const search = useSearchParams();

  useEffect(() => {
    const open = (trigger: HTMLElement) => {
      const data = trigger.dataset;
      opener.current = trigger;
      const url = new URL(window.location.href);
      url.searchParams.delete("start");
      for (const key of ["notice", "error", "voted"]) url.searchParams.delete(key);
      setReturnTo(`${url.pathname}${url.search}`);
      const chosen = { id: data.startDraft ?? "", title: data.title ?? "", portal: data.portal ?? "", due: data.due ?? "", format: data.format ?? FORMATS[0] };
      setFormat(FORMATS.includes(chosen.format) ? chosen.format : FORMATS[0]);
      setApproval("every_step");
      setDirection("");
      setPicked(new Set());
      setSuggestion(null);
      setSuggestedAt(null);
      setWaiting(null);
      setSuggestError("");
      setCall(chosen);
    };
    const onClick = (event: MouseEvent) => {
      const trigger = event.target instanceof Element ? event.target.closest<HTMLElement>("[data-start-draft]") : null;
      if (trigger) open(trigger);
    };
    document.addEventListener("click", onClick);
    const start = search.get("start");
    if (start) {
      const trigger = document.querySelector<HTMLElement>(`[data-start-draft="${CSS.escape(start)}"]`);
      if (trigger) open(trigger);
    }
    return () => document.removeEventListener("click", onClick);
  }, [search]);

  useEffect(() => {
    if (call && dialog.current && !dialog.current.open) dialog.current.showModal();
  }, [call]);

  const itemIds = new Set(pastWork.flatMap((g) => g.items.map((i) => i.id)));
  const itemKey = [...itemIds].join("|");

  const apply = useCallback((s: Suggestion) => {
    if (s.format) setFormat(s.format);
    if (s.approvalMode) setApproval(s.approvalMode);
    if (s.direction) setDirection(s.direction.slice(0, 2000));
    if (s.buildsOn.length) setPicked(new Set(s.buildsOn.map((b) => b.id)));
    setSuggestion(s);
  }, []);

  /** Read the call's newest suggestion: fill the dialog in when it is done, keep waiting while it is on its way. */
  const read = useCallback(async (callId: string, fill: boolean): Promise<string> => {
    const res = await fetch(`/api/suggestion?call=${encodeURIComponent(callId)}`, { cache: "no-store" });
    if (!res.ok) return "";
    const data = (await res.json()) as { row: SuggestionRow | null; seenAt: string | null; now: string };
    const row = data.row;
    if (!row) return "";
    if (row.state === "done") {
      const s = parseSuggestion(row.suggestion, FORMATS, new Set(itemKey ? itemKey.split("|") : []));
      if (s && fill) {
        apply(s);
        setSuggestedAt(row.answered_at);
      }
      setWaiting(null);
    } else if (row.state === "failed") {
      if (fill) setSuggestError(row.note || "Claude could not make a suggestion.");
      setWaiting(null);
    } else {
      setWaiting((w) => ({ state: row.state, seenAt: data.seenAt, now: Date.parse(data.now) || Date.now(), since: w?.since ?? Date.now() }));
    }
    return row.state;
  }, [apply, itemKey]);

  useEffect(() => {
    if (call && suggests) read(call.id, true).catch(() => undefined);
  }, [call, suggests, read]);

  useEffect(() => {
    if (!call || !waiting) return;
    if (Date.now() - waiting.since > GIVE_UP_MS) {
      setWaiting(null);
      setSuggestError("No suggestion yet. It will fill in the next time you open this dialog, or ask again.");
      return;
    }
    const timer = window.setTimeout(() => read(call.id, true).catch(() => undefined), POLL_MS);
    return () => window.clearTimeout(timer);
  }, [call, waiting, read]);

  async function askForSuggestion() {
    if (!call) return;
    setSuggestError("");
    const result = await suggestDraftAction({ callId: call.id });
    if (!result.ok) {
      setSuggestError(result.reason);
      return;
    }
    setWaiting({ state: "queued", seenAt: null, now: Date.now(), since: Date.now() });
    await read(call.id, true).catch(() => undefined);
  }

  const close = () => dialog.current?.close();
  const today = new Date().toISOString().slice(0, 10);
  const why = new Map((suggestion?.buildsOn ?? []).map((b) => [b.id, b.why]));
  const groups = withSuggestedFirst(pastWork, suggestion ? suggestion.buildsOn.map((b) => b.id) : []);
  const toggle = (id: string, on: boolean) =>
    setPicked((current) => {
      const next = new Set(current);
      if (on) next.add(id);
      else next.delete(id);
      return next;
    });

  return (
    <dialog
      ref={dialog}
      id="start-draft"
      className="settings start-draft"
      aria-labelledby="start-draft-title"
      onClose={() => {
        setCall(null);
        setWaiting(null);
        opener.current?.focus();
      }}
    >
      {call ? (
        <form action={startDraftAction}>
          <input type="hidden" name="call_id" value={call.id} />
          <input type="hidden" name="return_to" value={returnTo} />
          <h2 id="start-draft-title">Start the draft</h2>
          <p className="lead">
            <strong>{call.title}</strong>
            <br />
            {call.portal}
            {call.due ? `, due ${call.due}` : ""}
          </p>

          {suggests ? (
            <div className="suggest-bar">
              <button type="button" className="btn" onClick={() => void askForSuggestion()} disabled={Boolean(waiting) || !owner}>
                <Sparkles aria-hidden="true" />
                {suggestion ? "Suggest again" : "Suggest what to include"}
              </button>
              <span className="hint" role="status">
                {waiting
                  ? suggestStatus(waiting.state, waiting.seenAt, waiting.now)
                  : suggestion
                    ? `Filled in from Claude's suggestion${suggestedAt ? ` of ${suggestedAt.slice(0, 16).replace("T", " ")} UTC` : ""}. Change anything before you start.`
                    : "Claude can recommend the format, how to approve, a direction and the past work to build on."}
              </span>
              {suggestError ? <p className="error-text">{suggestError}</p> : null}
            </div>
          ) : null}

          <div className="draft-groups">
            <label className="field">
              <span className="field-label">Format</span>
              <select name="format" value={format} onChange={(e) => setFormat(e.target.value)}>
                {FORMATS.map((f) => (
                  <option key={f} value={f}>
                    {f}
                  </option>
                ))}
              </select>
              {suggestion?.formatWhy ? <span className="suggest-why">Claude: {suggestion.formatWhy}</span> : null}
            </label>

            <fieldset className="field">
              <legend className="field-label">User approval required</legend>
              <div className="radio-cards">
                <label className="radio-card">
                  <input type="radio" name="approval_mode" value="every_step" checked={approval === "every_step"} onChange={() => setApproval("every_step")} />
                  <span>
                    <strong>Every step</strong>
                    <span>You approve each step before the next starts</span>
                  </span>
                </label>
                <label className="radio-card">
                  <input type="radio" name="approval_mode" value="key_gates" checked={approval === "key_gates"} onChange={() => setApproval("key_gates")} />
                  <span>
                    <strong>Key gates only</strong>
                    <span>You decide Go or no-go, the Outline and Submit</span>
                  </span>
                </label>
              </div>
              {suggestion?.approvalWhy ? <span className="suggest-why">Claude: {suggestion.approvalWhy}</span> : null}
            </fieldset>

            <p className="draft-facts">
              <span>
                <span className="field-label">Owner</span> {owner ?? "Log in first"}
              </span>
              <span>
                <span className="field-label">Deadline</span> {call.due || "none given"}
              </span>
            </p>

            {people.length ? (
              <fieldset className="field">
                <legend className="field-label">Working with (optional)</legend>
                <div className="chip-checks">
                  {people.map((p) => (
                    <label key={p.name} className="chip-check">
                      <input type="checkbox" name="with" value={p.name} />
                      <span className="person">
                        <Avatar initials={p.initials ?? "?"} picture={p.picture} size="tiny" />
                        <span>{p.label}</span>
                      </span>
                    </label>
                  ))}
                </div>
              </fieldset>
            ) : null}

            <label className="field">
              <span className="field-label">Direction (optional)</span>
              <textarea name="direction" rows={direction ? 6 : 3} maxLength={2000} value={direction} onChange={(e) => setDirection(e.target.value)}
                placeholder="The angle you want, the past work to lead with, a partner to name" />
            </label>

            {groups.length ? (
              <fieldset className="field">
                <legend className="field-label">Builds on (optional)</legend>
                <div className="past-work">
                  {groups.map((group) => (
                    <div key={group.title}>
                      <p className="past-work-group">{group.title}</p>
                      {group.items.map((item) => (
                        <label key={item.id} className="past-work-item">
                          <input type="checkbox" name="builds_on" value={item.id} checked={picked.has(item.id)}
                            onChange={(e) => toggle(item.id, e.target.checked)} />
                          <span>
                            {item.label}
                            {why.get(item.id) ? <span className="suggest-why">{why.get(item.id)}</span> : null}
                          </span>
                        </label>
                      ))}
                    </div>
                  ))}
                </div>
                <p className="hint">From the Proposal Library in Drive{indexed ? `, as the worker last saw it at ${indexed}` : ""}.</p>
              </fieldset>
            ) : (
              <p className="hint">
                Builds on: the Proposal Library has not been indexed yet. The worker indexes it once it runs with Drive set up.
              </p>
            )}
            <p className="draft-folder">
              Creates <code>{folderName(today, call.portal, call.title)}</code> in Google Drive.
            </p>
            {readiness === "offline" ? (
              <p className="hint">The worker was last seen {lastSeen ?? "a while ago"}; Discovery starts when it is back.</p>
            ) : null}
            {readiness === "not set up" ? <p className="error-text">Drafting is not set up yet.</p> : null}
          </div>

          <div className="settings-actions">
            <span />
            <button type="button" onClick={close}>
              Cancel
            </button>
            <button type="submit" className="btn-primary fn-approve" disabled={readiness === "not set up" || !owner}>
              Start the draft
            </button>
          </div>
        </form>
      ) : null}
    </dialog>
  );
}
