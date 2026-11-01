"""The past bids nearest a pursued call, read from the Proposal Library on Drive for the Outline and the First draft
(PRO-565): what each sent in (01_submitted) and what came back (03_outcome).

    found = read(record)    # the nearest Register rows that have files, and their text, capped
    found.text              # the prompt section: how to use them, then each bid
    found.line              # the step card's line: which bids were read

The rows come ranked by inputs.gather: the same agency, an exemplar, a win, its strength, and the words its title
and themes share with the call. A past bid lends its language, structure and lessons only; Velocity's facts still
come from 01 Company Reference. Cost files are left out, being numbers rather than language. Drive trouble is no
step's failure: the section says what could not be read.
"""
from __future__ import annotations

import html
import io
import logging
import re
import zipfile
from dataclasses import dataclass
from typing import Any

from drafting import drive
from drafting.inputs import CallRecord
from drafting.steps import fix_dashes

LIMIT = 3              # bids read for a call
FILE_CHARS = 12_000    # of each file
BID_CHARS = 20_000     # of each bid
FOLDERS = ("01_submitted", "03_outcome")
NUMBERS = re.compile(r"(?<![a-z])(cost|budget|price|pricing|invoice|rates?)(?![a-z])", re.I)   # figures, not language
# Paperwork in 01_submitted, whose words are a form's, not the bid's (in 03_outcome a letter is the outcome itself):
PAPERWORK = re.compile(r"(?<![a-z])(cover|foreign|affiliations?|commitment|letters?|memo|memorandum|certifications?|"
                       r"registration|disclosures?|assurances?|signatures?|forms?|fraud|eligibility|agreements?|dd\d{3,4})"
                       r"(?![a-z])", re.I)
# What a bid argues, read first so the room goes to it: its volumes and papers, then its slides.
VOLUMES = re.compile(r"(?<![a-z])(technical|proposal|white|whitepaper|volume|vol|narrative|response|abstract|approach|"
                     r"summary)(?![a-z])", re.I)
SLIDES = re.compile(r"(?<![a-z])(briefing|quad|pitch|slides|deck)(?![a-z])", re.I)
PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
EXPORTS = {"application/vnd.google-apps.document": "text/plain", "application/vnd.google-apps.presentation": "text/plain"}
HEADER = ("PAST BIDS NEAREST THIS CALL, FROM THE PROPOSAL LIBRARY\n"
          "Reuse what won and avoid what cost a loss: their language, structure and lessons only. Take every fact about "
          "the company from VELOCITY FACTS, never from these texts, which may be out of date, and carry no figure, price "
          "or name from a past bid into this one.")


@dataclass
class PastBids:
    text: str              # the prompt section
    read: list[str]        # the submission ids read, nearest first
    line: str              # the step card's line


def _pdf(data: bytes) -> str:
    import pypdf

    logging.getLogger("pypdf").setLevel(logging.ERROR)   # a malformed but readable PDF is not worth a log line
    text = ""
    for page in pypdf.PdfReader(io.BytesIO(data)).pages:   # page by page, only as far as the cap needs
        text += (page.extract_text() or "") + "\n"
        if len(text) > FILE_CHARS:
            break
    return text


def _docx(data: bytes) -> str:
    import docx

    return "\n".join(p.text for p in docx.Document(io.BytesIO(data)).paragraphs)


def _pptx(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        slides = sorted((n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
                        key=lambda n: int(re.findall(r"\d+", n)[0]))
        return "\n".join(" ".join(html.unescape(t) for t in re.findall(r"<a:t>([^<]*)</a:t>", z.read(n).decode("utf-8")))
                         for n in slides)


READERS = {PDF: _pdf, DOCX: _docx, PPTX: _pptx}


def _text(found: drive.Drive, item: dict[str, Any]) -> str:
    """A file's words, or nothing for a kind that holds none (a spreadsheet, an image, a zip)."""
    mime = item.get("mimeType", "")
    if mime in EXPORTS:
        return found.export(item["id"], EXPORTS[mime])
    reader = READERS.get(mime)
    if reader is None:
        return ""
    data = found.download(item["id"])
    try:
        return reader(data)
    except Exception:   # noqa: BLE001 (a file that will not parse, such as a scanned or locked PDF, is skipped)
        return ""


def _files(found: drive.Drive, folder: dict[str, Any]) -> list[tuple[str, str]]:
    """Each readable file in a bid's 01_submitted/ (its narrative first, its figures and paperwork left out) and
    03_outcome/, by path, with its text."""
    texts = []
    for name in FOLDERS:
        sub = found.find(folder["id"], name, folder=True)
        items = sorted(found.children(sub["id"]) if sub else [],
                       key=lambda i: (0 if VOLUMES.search(i["name"]) else 1 if SLIDES.search(i["name"]) else 2, i["name"]))
        for item in items:
            sent = name == "01_submitted"
            if item["mimeType"] == drive.FOLDER_MIME or (sent and (NUMBERS.search(item["name"]) or PAPERWORK.search(item["name"]))):
                continue
            text = re.sub(r"\n\s*\n+", "\n\n", _text(found, item)).strip()
            if text:
                texts.append((f"{name}/{item['name']}", text))
    return texts


def _bid(row: dict[str, Any], files: list[tuple[str, str]]) -> str:
    bits = [row.get("type"), row.get("agency"), f"outcome {row['outcome']}" if row.get("outcome") else None,
            f"strength {row['strength_rating']}/5" if row.get("strength_rating") else None]
    lines = [f"=== {row['submission_id']}: {row.get('title') or ''}" + (f" ({', '.join(b for b in bits if b)})" if any(bits) else "")]
    lines += [f"{label}: {row[key]}" for key, label in (("why_won_or_lost", "Why it won or lost"),
                                                        ("strength_reason", "Its strength")) if row.get(key)]
    room = BID_CHARS
    for path, text in files:
        if room <= 0:
            break
        cap = min(FILE_CHARS, room)
        lines += [f"--- {path}" + (f" (its first {cap:,} characters)" if len(text) > cap else ""), text[:cap]]
        room -= min(len(text), cap)
    return "\n".join(lines)


def _done(parts: list[str], read: list[str], why: str = "") -> PastBids:
    if read:
        line = f"Past bids read: {len(read)}, nearest first ({', '.join(read)})"
    else:
        why = why or "none of the nearest Register rows has files in 01_submitted or 03_outcome yet"
        line = f"Past bids read: none ({why})"
        parts = [*parts, f"({why[:1].upper()}{why[1:]}.)"]
    return PastBids(fix_dashes("\n\n".join([HEADER, *parts])), read, line)


def read(record: CallRecord) -> PastBids:
    """The nearest past bids that have files, up to LIMIT, read live from the Proposal Library."""
    found, library = drive.client(), drive.library_id()
    if found is None or library is None:
        return _done([], [], "Drive is not set up on this PC")
    try:
        submissions = found.find(library, drive.SUBMISSIONS, folder=True)
        folders = {c["name"]: c for c in found.children(submissions["id"]) if c["mimeType"] == drive.FOLDER_MIME} if submissions else {}
    except drive.DriveError as exc:
        return _done([], [], f"the Proposal Library could not be read: {exc}")
    parts: list[str] = []
    read_ids: list[str] = []
    for row in record.past_work:
        if len(read_ids) >= LIMIT:
            break
        folder = folders.get(row["submission_id"])
        if folder is None:
            continue
        try:
            files = _files(found, folder)
        except drive.DriveError as exc:
            parts.append(f"=== {row['submission_id']}: its files could not be read ({exc})")
            continue
        if files:
            read_ids.append(row["submission_id"])
            parts.append(_bid(row, files))
    return _done(parts, read_ids)
