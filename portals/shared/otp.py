"""Read a portal's emailed sign-in code from the mailbox it is sent to.

    VULCAN_OTP = OtpSource(portal="Vulcan SOF", sender="notifications@vulcan-sof.com",
                           subject="Vulcan - OTP Code",
                           pattern=re.compile(r"YOUR AUTHENTICATION CODE:\\s*(\\d{6})"),
                           mailbox_key="VULCAN_OTP_MAILBOX")
    code = get_otp(VULCAN_OTP, sent_after=time.time())   # polls up to 90 s; "123456" or None

Each portal describes its code mail once, as an OtpSource; everything else is shared.
Mail access is one of two backends, picked at call time:

- gog CLI (preferred, see AGENTS.md): ``gog gmail search`` then ``gog gmail read``.
- Gmail IMAP (when gog is absent): logs in as VELOCITY_GMAIL_APP_USERNAME with
  VELOCITY_GMAIL_APP_PASSWORD, a Google app password. Standard library only.

Both expose the same shape: ``fetch(mailbox) -> list[OtpMessage]`` newest first. Every
mailbox call has its own 15 s timeout, and every failure logs and keeps polling.
Logging the code itself is acceptable; nothing else from the mailbox is logged.
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
from functools import partial
from html import unescape

from config import ConfigError, get, require

log = logging.getLogger("portals.otp")

CALL_TIMEOUT_S = 15
POLL_SECONDS = 5
CLOCK_SKEW_S = 30   # mail timestamps are whole seconds and the sender's clock is not ours
IMAP_HOST = "imap.gmail.com"


@dataclass(frozen=True)
class OtpSource:
    """Where one portal's sign-in code arrives and how to find it in the mail."""

    portal: str                # for log lines, e.g. "Vulcan SOF"
    sender: str                # From address of the code mail
    subject: str               # its subject line
    pattern: re.Pattern[str]   # group(1) is the code
    mailbox_key: str           # setting that names the mailbox the code is sent to


@dataclass
class OtpMessage:
    """One candidate mail. received_at is epoch seconds; day_precision means the source
    only told us the date, so staleness is judged by calendar day."""

    body: str
    received_at: float | None = None
    day_precision: bool = False


Fetcher = Callable[[str], list[OtpMessage]]


def extract_code(text: str, pattern: re.Pattern[str]) -> str | None:
    """The last code the pattern finds in the text, or None."""
    found = pattern.findall(text or "")
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
    source: OtpSource,
    sent_after: float,
    max_wait: int = 90,
    mailbox: str | None = None,
    fetch: Fetcher | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> str | None:
    """Poll the mailbox until a code newer than ``sent_after`` appears, or ``max_wait`` passes."""
    mailbox = mailbox or require(source.mailbox_key)
    fetch = fetch or default_fetcher(source)
    deadline = time.time() + max_wait
    log.info("Waiting for the %s sign-in code (max %ds, poll every %ds)", source.portal, max_wait, POLL_SECONDS)
    while time.time() < deadline:
        sleep(POLL_SECONDS)
        remaining = int(deadline - time.time())
        try:
            messages = fetch(mailbox)
        except Exception as exc:   # tool missing, timeout, non-zero exit, parse error
            log.warning("Mailbox fetch failed (%s: %s); retrying, %ds left", type(exc).__name__, str(exc)[:120], remaining)
            continue
        if not messages:
            log.info("No code mail yet, %ds left", remaining)
            continue
        for msg in messages:
            if is_stale(msg, sent_after):
                log.info("Skipping code mail received before login was triggered")
                continue
            code = extract_code(msg.body, source.pattern)
            if code:
                log.info("Got %s code %s", source.portal, code)
                return code
            log.info("Code mail found but no code in body; retrying, %ds left", remaining)
    log.warning("Code timeout: no %s code within %ds", source.portal, max_wait)
    return None


# ------------------------------------------------------------------ backend selection

def default_fetcher(source: OtpSource) -> Fetcher:
    if shutil.which("gog"):
        log.info("Code mail backend: gog CLI")
        return partial(fetch_via_gog, source)
    if get("VELOCITY_GMAIL_APP_PASSWORD"):
        log.info("Code mail backend: Gmail IMAP")
        return partial(fetch_via_imap, source)
    raise ConfigError(
        "No mailbox access for sign-in codes: install the gog CLI (AGENTS.md) or set "
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


def fetch_via_gog(source: OtpSource, mailbox: str) -> list[OtpMessage]:
    query = f"from:{source.sender} subject:'{source.subject}' newer_than:5m"
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


def fetch_via_imap(source: OtpSource, mailbox: str) -> list[OtpMessage]:
    account = get("VELOCITY_GMAIL_APP_USERNAME") or mailbox
    password = re.sub(r"\s+", "", require("VELOCITY_GMAIL_APP_PASSWORD"))   # Google shows it in spaced groups
    since = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%d-%b-%Y")
    conn = imaplib.IMAP4_SSL(IMAP_HOST, timeout=CALL_TIMEOUT_S)
    try:
        conn.login(account, password)
        conn.select("INBOX", readonly=True)
        status, data = conn.search(None, "FROM", f'"{source.sender}"', "SUBJECT", f'"{source.subject}"', "SINCE", since)
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
