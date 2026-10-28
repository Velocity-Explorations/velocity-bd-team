"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { startDraftAction } from "@/app/actions";
import { FORMATS, folderName } from "@/lib/proposals";

type Chosen = { id: string; title: string; portal: string; due: string; format: string };

/**
 * Start the draft (P6, PRO-576), one dialog per page. Any button marked data-start-draft opens it for
 * its call, from the call's data attributes; so does `?start=<call id>` once the page has that call's
 * button (after Pursue and start the draft). Its Start button is the person's approval to spend.
 * Until the worker has run, it says Drafting is not set up yet (P8).
 */
export function StartDraftDialog({ people, owner, readiness, lastSeen }: {
  people: { name: string; label: string }[];
  owner: string | null;
  readiness: "ready" | "offline" | "not set up";
  lastSeen: string | null;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  const [call, setCall] = useState<Chosen | null>(null);
  const [returnTo, setReturnTo] = useState("/proposals");
  const search = useSearchParams();

  useEffect(() => {
    const open = (trigger: HTMLElement) => {
      const data = trigger.dataset;
      opener.current = trigger;
      const url = new URL(window.location.href);
      url.searchParams.delete("start");
      for (const key of ["notice", "error", "voted"]) url.searchParams.delete(key);
      setReturnTo(`${url.pathname}${url.search}`);
      setCall({ id: data.startDraft ?? "", title: data.title ?? "", portal: data.portal ?? "", due: data.due ?? "", format: data.format ?? FORMATS[0] });
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

  const close = () => dialog.current?.close();
  const today = new Date().toISOString().slice(0, 10);

  return (
    <dialog
      ref={dialog}
      id="start-draft"
      className="settings start-draft"
      aria-labelledby="start-draft-title"
      onClose={() => {
        setCall(null);
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

          <div className="draft-groups">
            <label className="field">
              <span className="field-label">Format</span>
              <select name="format" defaultValue={FORMATS.includes(call.format) ? call.format : FORMATS[0]}>
                {FORMATS.map((f) => (
                  <option key={f} value={f}>
                    {f}
                  </option>
                ))}
              </select>
            </label>

            <fieldset className="field">
              <legend className="field-label">User approval required</legend>
              <div className="radio-cards">
                <label className="radio-card">
                  <input type="radio" name="approval_mode" value="every_step" defaultChecked />
                  <span>
                    <strong>Every step</strong>
                    <span>You approve each step before the next starts</span>
                  </span>
                </label>
                <label className="radio-card">
                  <input type="radio" name="approval_mode" value="key_gates" />
                  <span>
                    <strong>Key gates only</strong>
                    <span>You decide Go or no-go, the Outline and Submit</span>
                  </span>
                </label>
              </div>
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
                      {p.label}
                    </label>
                  ))}
                </div>
              </fieldset>
            ) : null}

            <label className="field">
              <span className="field-label">Direction (optional)</span>
              <textarea name="direction" rows={3} maxLength={2000} placeholder="The angle you want, the past work to lead with, a partner to name" />
            </label>

            <p className="hint">
              Builds on: past work to build on can be chosen once the worker indexes the Proposal Library in Drive.
            </p>
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
