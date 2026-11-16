"use client";

import { MessageSquarePlus, Send, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from "react";
import { askGrokAction } from "@/app/actions";
import {
  ASK_MAX,
  ASK_MIN,
  askCookie,
  askWidthCookie,
  askWidthCss,
  callHref,
  fitAskWidth,
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
  if (!part.href) return part.strong ? <strong>{part.text}</strong> : <>{part.text}</>;
  return part.href.startsWith("/") ? (
    <Link href={part.href}>{part.text}</Link>   // the page changes beside the panel, which stays open
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
        {sources.calls.length || sources.facts.length || sources.requests.length ? (
          <div className="ask-sources">
            {sources.requests.map((r) => (
              <Link key={`r${r.id}`} className="badge tone-warn" href="/requests" title={`${r.summary}: waits for approval on the Requests page`}>
                Request #{r.id}
              </Link>
            ))}
            {sources.calls.map((c) => (
              <Link key={c.id} className="badge tone-info" href={callHref(c)} title={`${c.title}, ${c.portal}`}>
                {c.title.length > 48 ? `${c.title.slice(0, 46)}...` : c.title}
              </Link>
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
 * Ask Grok (David, 7 Nov 2026): a panel docked at the right of every page, opened and closed from the header's Ask Grok
 * button. Since 16 Nov it takes its own column: the page narrows beside it instead of lying under it, and below 960 px,
 * where there is no room, it lies over the page as before. It lives in the root layout, so changing page keeps it open
 * with its conversation, its unsent question and any answer on its way; a cookie (ASK_COOKIE) keeps it open across a
 * reload too. Its left edge drags wider or narrower (or the arrow keys move it once it has focus), and a double-click
 * puts back the usual width; the width is kept for the browser in ASK_WIDTH_COOKIE. A question goes to the ledger (askGrokAction); while it waits, the panel reads its thread from /api/ask
 * every two seconds, and the answer shows when run.py --assistant has written it. One conversation shows at a time, the
 * person's newest, until they start a new one.
 */
export function AskPanel({ viewer, initialOpen, initialWidth }: { viewer: string | null; initialOpen: boolean; initialWidth: number | null }) {
  const panel = useRef<HTMLElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  const moveFocus = useRef(false);   // only a person opening or closing the panel moves focus, never a page change
  const box = useRef<HTMLTextAreaElement>(null);
  const list = useRef<HTMLOListElement>(null);
  const pathname = usePathname();
  const [open, setOpen] = useState(initialOpen);
  const shown = open && !pathname.startsWith("/login");
  const [width, setWidth] = useState<number | null>(initialWidth);   // null: the usual width, from the window's
  const [measured, setMeasured] = useState<number | null>(initialWidth);
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

  const close = useCallback(() => {
    moveFocus.current = true;
    setOpen(false);
  }, []);

  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      const trigger = event.target instanceof Element ? event.target.closest<HTMLElement>("[data-opens='ask-grok']") : null;
      if (!trigger) return;
      opener.current = trigger;
      moveFocus.current = true;
      setOpen((was) => !was);
    };
    // Escape closes the panel from inside it; on the page it is left to the menus, tooltips and dialogs there.
    const onKey = (event: globalThis.KeyboardEvent) => {
      const here = panel.current;
      if (event.key !== "Escape" || !here || here.hidden || !here.contains(document.activeElement)) return;
      moveFocus.current = true;
      setOpen(false);
    };
    document.addEventListener("click", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("click", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, []);

  // Remembered for the next page load, and told to the top bar's button, which each page draws afresh.
  useEffect(() => {
    document.cookie = askCookie(open);
    for (const button of document.querySelectorAll<HTMLElement>("[data-opens='ask-grok']")) {
      button.setAttribute("aria-expanded", String(open));
    }
  }, [open, pathname]);

  // What the edge says its value is: the panel's width as drawn, which the window's own width can change.
  useEffect(() => {
    const here = panel.current;
    if (!here || typeof ResizeObserver === "undefined") return;
    const watch = new ResizeObserver(() => {
      const drawn = Math.round(here.getBoundingClientRect().width);
      if (drawn) setMeasured(drawn);
    });
    watch.observe(here);
    return () => watch.disconnect();
  }, []);

  const keepWidth = useCallback((next: number | null) => {
    document.cookie = askWidthCookie(next);
    setWidth(next);
  }, []);

  // A drag moves the edge through the custom property alone. Once the style element carries the new width, the drag's
  // value comes off, before the browser paints, so the panel never shows the old width in between.
  useLayoutEffect(() => {
    document.documentElement.style.removeProperty("--ask-width");
  }, [width]);

  function startDrag(event: ReactPointerEvent<HTMLDivElement>) {
    if (event.button !== 0 || !panel.current) return;
    event.preventDefault();
    const edge = event.currentTarget;
    const root = document.documentElement;
    const startX = event.clientX;
    const startWidth = panel.current.getBoundingClientRect().width;
    let latest = width;
    edge.setPointerCapture(event.pointerId);
    root.classList.add("ask-resizing");
    const move = (e: PointerEvent) => {
      latest = fitAskWidth(startWidth + startX - e.clientX, root.clientWidth);
      root.style.setProperty("--ask-width", `${latest}px`);
    };
    const end = () => {
      edge.removeEventListener("pointermove", move);
      edge.removeEventListener("pointerup", end);
      edge.removeEventListener("pointercancel", end);
      root.classList.remove("ask-resizing");
      if (latest === width) root.style.removeProperty("--ask-width");
      else keepWidth(latest);
    };
    edge.addEventListener("pointermove", move);
    edge.addEventListener("pointerup", end);
    edge.addEventListener("pointercancel", end);
  }

  function onEdgeKey(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    const now = measured ?? panel.current?.getBoundingClientRect().width ?? ASK_MIN;
    const step = (event.shiftKey ? 96 : 24) * (event.key === "ArrowLeft" ? 1 : -1);
    keepWidth(fitAskWidth(now + step, document.documentElement.clientWidth));
  }

  useEffect(() => {
    if (!moveFocus.current) return;
    moveFocus.current = false;
    if (open) {
      if (box.current && !box.current.disabled) box.current.focus();
      else panel.current?.querySelector<HTMLElement>(".ask-close")?.focus();
      return;
    }
    const back = opener.current?.isConnected ? opener.current : document.querySelector<HTMLElement>("[data-opens='ask-grok']");
    back?.focus();
  }, [open]);

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
    <>
      <style>{askWidthCss(width)}</style>
      <aside ref={panel} id="ask-grok" className="ask-panel" aria-labelledby="ask-grok-title" hidden={!shown}>
        <div
          className="ask-resize"
          role="separator"
          aria-orientation="vertical"
          aria-label="Ask Grok's width"
          aria-valuemin={ASK_MIN}
          aria-valuemax={ASK_MAX}
          aria-valuenow={measured ?? undefined}
          tabIndex={0}
          title="Drag to widen or narrow Ask Grok. Double-click for the usual width."
          onPointerDown={startDrag}
          onKeyDown={onEdgeKey}
          onDoubleClick={() => keepWidth(null)}
        />
        <div className="ask-head">
          <h2 id="ask-grok-title">Ask Grok</h2>
          <button type="button" className="btn ask-new" disabled={!viewer || sending}
            onClick={() => { setThread(newThread()); setMessages([]); setError(""); box.current?.focus(); }}>
            <MessageSquarePlus aria-hidden="true" />
            New conversation
          </button>
          <button type="button" className="ask-close" aria-label="Close Ask Grok" onClick={close}>
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
      </aside>
    </>
  );
}
