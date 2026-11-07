"use client";

import { MessageSquarePlus, Send, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from "react";
import { askGrokAction } from "@/app/actions";
import {
  callHref,
  costLine,
  MAX_QUESTION,
  parseAnswer,
  parseSources,
  POLL_MS,
  statusLine,
  type AskMessage,
  type Block,
  type Part,
} from "@/lib/ask";

function newThread(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `t-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

function PartView({ part }: { part: Part }) {
  if (!part.href) return <>{part.text}</>;
  return part.href.startsWith("/") ? (
    <a href={part.href}>{part.text}</a>
  ) : (
    <a href={part.href} target="_blank" rel="noreferrer">
      {part.text}
    </a>
  );
}

function AnswerView({ blocks }: { blocks: Block[] }) {
  return (
    <>
      {blocks.map((b, i) =>
        b.kind === "p" ? (
          <p key={i}>
            {b.lines.map((line, j) => (
              <span key={j}>
                {j ? <br /> : null}
                {line.map((part, k) => <PartView key={k} part={part} />)}
              </span>
            ))}
          </p>
        ) : (
          <ul key={i}>
            {b.items.map((item, j) => (
              <li key={j}>{item.map((part, k) => <PartView key={k} part={part} />)}</li>
            ))}
          </ul>
        ),
      )}
    </>
  );
}

function Message({ m, seenAt, now }: { m: AskMessage; seenAt: string | null; now: number }) {
  const sources = parseSources(m.sources);
  const waiting = statusLine(m.state, seenAt, now);
  let body: ReactNode;
  if (waiting) body = <p className="ask-wait" role="status">{waiting}</p>;
  else if (m.state === "failed") body = <p className="ask-failed">{m.answer || "Grok could not answer."}</p>;
  else body = <AnswerView blocks={parseAnswer(m.answer)} />;
  return (
    <li className="ask-exchange" data-state={m.state}>
      <p className="ask-question">{m.question}</p>
      <div className="ask-answer">
        {body}
        {sources.calls.length || sources.facts.length ? (
          <div className="ask-sources">
            {sources.calls.map((c) => (
              <a key={c.id} className="badge tone-info" href={callHref(c)} title={`${c.title}, ${c.portal}`}>
                {c.title.length > 48 ? `${c.title.slice(0, 46)}...` : c.title}
              </a>
            ))}
            {sources.facts.map((f) => (
              <span key={f} className="badge tone-grey" title="An id in 01 Company Reference">
                {f}
              </span>
            ))}
          </div>
        ) : null}
        {m.state === "done" ? <p className="meta">{costLine(m.model, m.tools, m.cost_usd)}</p> : null}
      </div>
    </li>
  );
}

/**
 * Ask Grok (David, 7 Nov 2026): a panel at the right edge of every page, opened from the header's Ask Grok button. The
 * page stays usable beside it. A question goes to the ledger (askGrokAction); while it waits, the panel reads its thread
 * from /api/ask every two seconds, and the answer shows when run.py --assistant has written it. One conversation shows at
 * a time, the person's newest, until they start a new one.
 */
export function AskPanel({ viewer }: { viewer: string | null }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  const box = useRef<HTMLTextAreaElement>(null);
  const list = useRef<HTMLOListElement>(null);
  const [open, setOpen] = useState(false);
  const [thread, setThread] = useState<string | null>(null);
  const [messages, setMessages] = useState<AskMessage[]>([]);
  const [seenAt, setSeenAt] = useState<string | null>(null);
  const [now, setNow] = useState(0);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);

  const load = useCallback(async (id: string | null) => {
    const res = await fetch(`/api/ask${id ? `?thread=${encodeURIComponent(id)}` : ""}`, { cache: "no-store" });
    if (!res.ok) return;
    const data = (await res.json()) as { thread: string | null; messages: AskMessage[]; seenAt: string | null; now: string };
    if (data.thread) setThread(data.thread);
    setMessages(data.messages ?? []);
    setSeenAt(data.seenAt ?? null);
    setNow(Date.parse(data.now) || Date.now());
  }, []);

  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      const trigger = event.target instanceof Element ? event.target.closest<HTMLElement>("[data-opens='ask-grok']") : null;
      if (!trigger || !dialog.current) return;
      if (dialog.current.open) {
        dialog.current.close();
        return;
      }
      opener.current = trigger;
      dialog.current.show();
      setOpen(true);
      if (box.current && !box.current.disabled) box.current.focus();
      else dialog.current.querySelector<HTMLElement>(".ask-close")?.focus();
    };
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape" && dialog.current?.open) dialog.current.close();
    };
    document.addEventListener("click", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("click", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, []);

  useEffect(() => {
    if (open && viewer) load(thread).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, viewer, load]);

  const waiting = messages.some((m) => m.state === "queued" || m.state === "working");
  useEffect(() => {
    if (!open || !waiting || !thread) return;
    const timer = window.setInterval(() => load(thread).catch(() => undefined), POLL_MS);
    return () => window.clearInterval(timer);
  }, [open, waiting, thread, load]);

  useEffect(() => {
    list.current?.lastElementChild?.scrollIntoView({ block: "end" });
  }, [messages]);

  async function send(event?: FormEvent) {
    event?.preventDefault();
    const question = draft.trim();
    if (!question || sending) return;
    const id = thread ?? newThread();
    setSending(true);
    setError("");
    try {
      const result = await askGrokAction({ question, thread: id, page: `${window.location.pathname}${window.location.search}` });
      if (!result.ok) {
        setError(result.reason);
        return;
      }
      setThread(result.thread);
      setDraft("");
      setNow(Date.now());
      setMessages((m) => [...m, { id: result.id, question, state: "queued", answer: null, sources: null, tools: null, model: null,
        cost_usd: null, asked_at: new Date().toISOString(), answered_at: null }]);
    } catch {
      setError("The question did not reach the ledger. Try again.");
    } finally {
      setSending(false);
    }
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      void send();
    }
  }

  return (
    <dialog
      ref={dialog}
      id="ask-grok"
      className="ask-panel"
      aria-labelledby="ask-grok-title"
      onClose={() => {
        setOpen(false);
        opener.current?.focus();
      }}
    >
      <div className="ask-head">
        <h2 id="ask-grok-title">Ask Grok</h2>
        <button type="button" className="btn ask-new" disabled={!viewer || sending}
          onClick={() => { setThread(newThread()); setMessages([]); setError(""); box.current?.focus(); }}>
          <MessageSquarePlus aria-hidden="true" />
          New conversation
        </button>
        <button type="button" className="ask-close" aria-label="Close Ask Grok" onClick={() => dialog.current?.close()}>
          <X aria-hidden="true" />
        </button>
      </div>
      <div className="ask-body">
        {messages.length ? (
          <ol ref={list} className="ask-thread" aria-label="This conversation">
            {messages.map((m) => <Message key={m.id} m={m} seenAt={seenAt} now={now} />)}
          </ol>
        ) : (
          <div className="ask-empty">
            <p>Ask about the calls the dashboard lists, Velocity&apos;s facts, or past bids. For example:</p>
            <ul>
              <li>Which open calls fit our C2 work, and when are they due?</li>
              <li>What past performance do we have with the Space Force?</li>
              <li>What did we bid to DARPA, and how did it go?</li>
            </ul>
            <p className="meta">Grok answers from the ledger and 01 Company Reference, citing ids, and cannot change anything.</p>
          </div>
        )}
      </div>
      <form className="ask-form" onSubmit={send}>
        {error ? <p className="error-text" role="alert">{error}</p> : null}
        <label className="sr-only" htmlFor="ask-grok-question">Your question</label>
        <textarea
          ref={box}
          id="ask-grok-question"
          value={draft}
          maxLength={MAX_QUESTION}
          rows={3}
          disabled={!viewer}
          placeholder={viewer ? "Ask Grok a question" : "Log in (top right) to ask Grok"}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={onKeyDown}
        />
        <div className="ask-actions">
          <span className="meta">Enter sends, Shift+Enter starts a new line. Don&apos;t paste CUI or passwords.</span>
          <button type="submit" className="btn-primary" disabled={!viewer || sending || !draft.trim() || waiting}>
            <Send aria-hidden="true" />
            Send
          </button>
        </div>
      </form>
    </dialog>
  );
}
