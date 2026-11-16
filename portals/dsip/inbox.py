"""DSIP's own topic DOCX files, downloaded by a person and dropped in data/dsip/inbox, as calls.

    counts = import_inbox(run_id)   # {"found", "scraped", "new", "failed"}

For a release SBIR.gov does not copy (the watch names it), a person opens DSIP's topic search, downloads each topic with
Download Topic Details as DOCX and saves the files in data/dsip/inbox. Each scan reads them: a topic becomes a call with
the same id SBIR.gov's copy would get, its dates from the AFWERX or SpaceWERX cycle that names its release. A file read
moves to data/dsip/imported, and one that is not a topic to data/dsip/unreadable, except on a dry run, which leaves every
file where it is.
"""
from __future__ import annotations

import io
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from ledger.db import in_dry_run
from ledger.queries import upsert_call
from portals.dsip.cycles import cycle_for, stored_cycles
from portals.dsip.records import from_docx, read_docx
from portals.dsip.topics import parse_topic_number

log = logging.getLogger("dsip.inbox")

REPO_ROOT = Path(__file__).resolve().parents[2]
FOLDER = REPO_ROOT / "data" / "dsip"
SHOWN = Path("data") / "dsip" / "inbox"   # how the watch and the notes name the drop folder
# Windows' extended-length prefix. DSIP names a file after its topic's title, up to 225 characters, and a path past
# 260 characters cannot be opened without it while long paths are off (as on the scan PC); 5 of the 102 files saved
# on 10 Nov 2026 failed for this until every read, listing and move went through long_path.
LONG_PREFIX = "\\\\?\\"


def long_path(path: Path) -> str:
    text = str(path.absolute())
    return LONG_PREFIX + text if os.name == "nt" and not text.startswith(LONG_PREFIX) else text


def docx_names(box: Path) -> list[str]:
    if not box.is_dir():
        return []
    with os.scandir(long_path(box)) as entries:
        return sorted(entry.name for entry in entries if entry.is_file() and entry.name.lower().endswith(".docx"))


def paragraphs_of(path: Path) -> list[str]:
    import docx

    with open(long_path(path), "rb") as handle:
        return [paragraph.text for paragraph in docx.Document(io.BytesIO(handle.read())).paragraphs]


def _move(path: Path, to: Path) -> None:
    if in_dry_run():
        return
    to.mkdir(parents=True, exist_ok=True)
    os.replace(long_path(path), long_path(to / path.name))


def import_inbox(run_id: int, folder: Path = FOLDER, now: datetime | None = None) -> dict[str, int]:
    now = now or datetime.now(timezone.utc)
    counts = {"found": 0, "scraped": 0, "new": 0, "failed": 0}
    box = folder / "inbox"
    if not in_dry_run():
        box.mkdir(parents=True, exist_ok=True)   # so people find where to drop the files
    files = [box / name for name in docx_names(box)]
    cycles = stored_cycles() if files else []
    for path in files:
        counts["found"] += 1
        try:
            fields = read_docx(paragraphs_of(path), path.name)
            topic = parse_topic_number(fields["topic"])
            record = from_docx(fields, cycle_for(topic.key, cycles) if topic else None, now)
        except Exception as exc:   # not a DSIP topic file, or not a Word file at all: set aside, never read again
            counts["failed"] += 1
            log.warning("DSIP inbox: %s is not a topic file (%s: %s); moved to unreadable", path.name, type(exc).__name__,
                        str(exc)[:120])
            _move(path, folder / "unreadable")
            continue
        counts["scraped"] += 1
        if upsert_call(record, run_id):
            counts["new"] += 1
        _move(path, folder / "imported")
    if files:
        log.info("DSIP inbox: %d file(s), %d topic(s) stored (%d new), %d unreadable", counts["found"], counts["scraped"],
                 counts["new"], counts["failed"])
    return counts
