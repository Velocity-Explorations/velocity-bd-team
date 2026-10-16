"""Fetch the Vulcan SOF one-time code from the OTP mailbox.

    code = get_otp(sent_after=time.time())   # polls up to 90 s, returns "123456" or None

Mail access is one of two backends, picked at call time:

- gog CLI (preferred, see AGENTS.md): ``gog gmail search`` then ``gog gmail read``.
- Gmail IMAP (fallback when gog is absent): needs VELOCITY_GMAIL_APP_PASSWORD, a Google
  app password for the mailbox. Standard library only.

Both expose the same shape: ``fetch(mailbox) -> list[OtpMessage]`` newest first. Every
mailbox call has its own 15 s timeout, and every failure logs and keeps polling.
Logging the six-digit code is acceptable; nothing else from the mailbox is logged.
"""
from __future__ import annotations

import email
import email.utils
import imaplib
import logging
import re
import shutil
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import Message
from html import unescape

from config import ConfigError, get, require

log = logging.getLogger("vulcan_sof.otp")

OTP_SENDER = "notifications@vulcan-sof.com"
OTP_SUBJECT = "Vulcan - OTP Code"
CODE_RE = re.compile(r"YOUR AUTHENTICATION CODE:\s*(\d{6})")
CALL_TIMEOUT_S = 15
POLL_SECONDS = 5
CLOCK_SKEW_S = 30   # mail timestamps are whole seconds and the sender's clock is not ours
IMAP_HOST = "imap.gmail.com"


@dataclass
class OtpMessage:
    """One candidate mail. received_at is epoch seconds; day_precision means the source
    only told us the date, so staleness is judged by calendar day."""

    body: str
    received_at: float | None = None
    day_precision: bool = False


Fetcher = Callable[[str], list[OtpMessage]]


def extract_code(text: str) -> str | None:
    """The last six-digit authentication code in the text, or None."""
    found = CODE_RE.findall(text or "")
    return found[-1] if found else None


def is_stale(msg: OtpMessage, sent_after: float) -> bool:
    if msg.received_at is None:
        return False
    if msg.day_precision:
        received_day = datetime.fromtimestamp(msg.received_at, tz=timezone.utc).date()
        trigger_day = datetime.fromtimestamp(sent_after, tz=timezone.utc).date()
        return received_day < trigger_day
    return msg.received_at < sent_after - CLOCK_SKEW_S


def get_otp(
    sent_after: float,
    max_wait: int = 90,
    mailbox: str | None = None,
    fetch: Fetcher | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> str | None:
    """Poll the mailbox until a code newer than ``sent_after`` appears, or ``max_wait`` passes."""
    mailbox = mailbox or require("VULCAN_OTP_MAILBOX")
    fetch = fetch or default_fetcher()
    deadline = time.time() + max_wait
    log.info("Waiting for OTP in mailbox (max %ds, poll every %ds)", max_wait, POLL_SECONDS)
    while time.time() < deadline:
        sleep(POLL_SECONDS)
        remaining = int(deadline - time.time())
        try:
            messages = fetch(mailbox)
        except Exception as exc:   # tool missing, timeout, non-zero exit, parse error
            log.warning("Mailbox fetch failed (%s: %s); retrying, %ds left", type(exc).__name__, str(exc)[:120], remaining)
            continue
        if not messages:
            log.info("No OTP mail yet, %ds left", remaining)
            continue
        for msg in messages:
            if is_stale(msg, sent_after):
                log.info("Skipping OTP mail received before login was triggered")
                continue
            code = extract_code(msg.body)
            if code:
                log.info("Got OTP %s", code)
                return code
            log.info("OTP mail found but no code in body; retrying, %ds left", remaining)
    log.warning("OTP timeout: no code within %ds", max_wait)
    return None


# ------------------------------------------------------------------ backend selection

def default_fetcher() -> Fetcher:
    if shutil.which("gog"):
        log.info("OTP backend: gog CLI")
        return fetch_via_gog
    if get("VELOCITY_GMAIL_APP_PASSWORD"):
        log.info("OTP backend: Gmail IMAP")
        return fetch_via_imap
    raise ConfigError(
        "No mailbox access for the OTP: install the gog CLI (AGENTS.md) or set "
        "VELOCITY_GMAIL_APP_PASSWORD in .env for Gmail IMAP."
    )


# ---------------------------------------------------------------------------- gog CLI

def _run_gog(args: list[str]) -> str:
    result = subprocess.run(["gog", *args], capture_output=True, text=True, timeout=CALL_TIMEOUT_S)
    if result.returncode != 0:
        raise RuntimeError(f"gog exited {result.returncode}: {result.stderr.strip()[:120]}")
    return result.stdout


def parse_gog_search(stdout: str) -> list[tuple[str, float | None]]:
    """(thread_id, received_at epoch or None) per result line. Date precision is one day."""
    out: list[tuple[str, float | None]] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.upper().startswith("ID"):
            continue
        parts = line.split()
        received: float | None = None
        for token in parts[1:]:
            try:
                received = datetime.strptime(token[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()
                break
            except ValueError:
                continue
        out.append((parts[0], received))
    return out


def fetch_via_gog(mailbox: str) -> list[OtpMessage]:
    query = f"from:{OTP_SENDER} subject:'{OTP_SUBJECT}' newer_than:5m"
    stdout = _run_gog(["gmail", "search", query, "--max", "3", "--account", mailbox])
    messages: list[OtpMessage] = []
    for thread_id, received in parse_gog_search(stdout):
        body = _run_gog(["gmail", "read", thread_id, "--account", mailbox])
        messages.append(OtpMessage(body=body, received_at=received, day_precision=True))
    return messages


# ------------------------------------------------------------------------- Gmail IMAP

def message_text(msg: Message) -> str:
    """Plain text of a parsed mail: text/plain parts first, else de-tagged HTML."""
    plain: list[str] = []
    html: list[str] = []
    parts = msg.walk() if msg.is_multipart() else [msg]
    for part in parts:
        ctype = part.get_content_type()
        if ctype not in ("text/plain", "text/html"):
            continue
        payload = part.get_payload(decode=True)
        if payload is None:
            continue
        text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        (plain if ctype == "text/plain" else html).append(text)
    if plain:
        return "\n".join(plain)
    stripped = re.sub(r"<[^>]+>", " ", "\n".join(html))
    return unescape(stripped)


def fetch_via_imap(mailbox: str) -> list[OtpMessage]:
    account = get("VELOCITY_GMAIL_APP_USERNAME") or mailbox
    password = re.sub(r"\s+", "", require("VELOCITY_GMAIL_APP_PASSWORD"))   # Google shows it in spaced groups
    since = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%d-%b-%Y")
    conn = imaplib.IMAP4_SSL(IMAP_HOST, timeout=CALL_TIMEOUT_S)
    try:
        conn.login(account, password)
        conn.select("INBOX", readonly=True)
        status, data = conn.search(None, "FROM", f'"{OTP_SENDER}"', "SUBJECT", f'"{OTP_SUBJECT}"', "SINCE", since)
        if status != "OK":
            raise RuntimeError(f"IMAP search returned {status}")
        ids = data[0].split()[-3:]
        messages: list[OtpMessage] = []
        for msg_id in ids:
            status, payload = conn.fetch(msg_id, "(RFC822)")
            if status != "OK" or not payload or not isinstance(payload[0], tuple):
                continue
            parsed = email.message_from_bytes(payload[0][1])
            received: float | None = None
            try:
                received = email.utils.parsedate_to_datetime(parsed.get("Date", "")).timestamp()
            except (TypeError, ValueError):
                pass
            messages.append(OtpMessage(body=message_text(parsed), received_at=received))
        messages.sort(key=lambda m: m.received_at or 0, reverse=True)
        return messages
    finally:
        try:
            conn.logout()
        except Exception:
            pass
