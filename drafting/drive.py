"""The proposal workspace's Google Drive (phase 6b), through the worker's service account.

    found = client()                                   # None until GOOGLE_SERVICE_ACCOUNT_FILE is set
    folder = pursuit_folder(found, library_id(), folder_name(day, portal, title), taken)
    saved = upload(found, folder["id"], path)          # into its 02_working/; {"id", "link"}
    rows = index_library(found, library_id())          # drive_items, for Builds on

Each pursuit gets Submissions/<YYYY-MM-DD_portal_short-title>/ in the BD Proposal Library, with the four folders
docs/LIBRARY_CONVENTIONS.md names; the date is the day the draft started, as Start the draft says. The service
account is a member of the library folder on a shared drive: it can list, create, move and trash there but never
delete for good, so nothing here deletes. Every failure is a DriveError; the worker logs it and keeps the files on
the PC, so a step never fails for Drive.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Protocol

from config import get

FOLDER_MIME = "application/vnd.google-apps.folder"
SUBMISSIONS = "Submissions"
SUBFOLDERS = ("00_solicitation", "01_submitted", "02_working", "03_outcome")
WORKING = "02_working"
NO_GO = "_no-go"
COMPANY_REFERENCE = "01 Company Reference"
MIME_TYPES = {".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
              ".md": "text/markdown", ".pdf": "application/pdf", ".json": "application/json"}
SCOPES = ["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/spreadsheets"]


class DriveError(RuntimeError):
    """Drive refused or failed a call; the message says how, never with a file's content."""


class Drive(Protocol):
    """The calls the worker makes; GoogleDrive makes them for real, tests use a fake."""

    def get(self, item_id: str, fields: str = ...) -> dict[str, Any]: ...
    def children(self, parent_id: str) -> list[dict[str, Any]]: ...
    def find(self, parent_id: str, name: str, folder: bool) -> dict[str, Any] | None: ...
    def make_folder(self, parent_id: str, name: str) -> dict[str, Any]: ...
    def upload(self, parent_id: str, path: Path, name: str, mime: str) -> dict[str, Any]: ...
    def move(self, item_id: str, to_parent: str) -> None: ...


FIELDS = "id, name, mimeType, parents, webViewLink, modifiedTime"


class GoogleDrive:
    """Drive v3 through the service account's key file. Every call names supportsAllDrives."""

    def __init__(self, key_file: Path) -> None:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        credentials = service_account.Credentials.from_service_account_file(str(key_file), scopes=SCOPES)
        self.api = build("drive", "v3", credentials=credentials, cache_discovery=False)

    def _run(self, request: Any) -> Any:
        from googleapiclient.errors import HttpError

        try:
            return request.execute(num_retries=2)
        except HttpError as exc:
            raise DriveError(f"Drive answered {exc.status_code}") from exc
        except OSError as exc:
            raise DriveError(f"Drive could not be reached: {type(exc).__name__}") from exc

    def get(self, item_id: str, fields: str = FIELDS) -> dict[str, Any]:
        return self._run(self.api.files().get(fileId=item_id, supportsAllDrives=True, fields=fields))

    def children(self, parent_id: str) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        token = None
        while True:
            page = self._run(self.api.files().list(q=f"'{parent_id}' in parents and trashed = false", pageSize=200, pageToken=token,
                                                   supportsAllDrives=True, includeItemsFromAllDrives=True,
                                                   fields=f"nextPageToken, files({FIELDS})"))
            found += page.get("files", [])
            token = page.get("nextPageToken")
            if not token:
                return found

    def find(self, parent_id: str, name: str, folder: bool) -> dict[str, Any] | None:
        return next((i for i in self.children(parent_id) if i["name"] == name and (i["mimeType"] == FOLDER_MIME) == folder), None)

    def make_folder(self, parent_id: str, name: str) -> dict[str, Any]:
        return self._run(self.api.files().create(body={"name": name, "parents": [parent_id], "mimeType": FOLDER_MIME},
                                                 supportsAllDrives=True, fields=FIELDS))

    def upload(self, parent_id: str, path: Path, name: str, mime: str) -> dict[str, Any]:
        from googleapiclient.http import MediaFileUpload

        media = MediaFileUpload(str(path), mimetype=mime, resumable=False)
        found = self.find(parent_id, name, folder=False)
        if found:   # a new version of the same file, so its link stays
            return self._run(self.api.files().update(fileId=found["id"], media_body=media, supportsAllDrives=True, fields=FIELDS))
        return self._run(self.api.files().create(body={"name": name, "parents": [parent_id]}, media_body=media,
                                                 supportsAllDrives=True, fields=FIELDS))

    def move(self, item_id: str, to_parent: str) -> None:
        now = self.get(item_id, fields="parents")
        self._run(self.api.files().update(fileId=item_id, addParents=to_parent, removeParents=",".join(now.get("parents", [])),
                                          supportsAllDrives=True, fields="id"))


def key_file() -> Path | None:
    raw = (get("GOOGLE_SERVICE_ACCOUNT_FILE") or "").strip().strip('"')
    return Path(raw) if raw and Path(raw).is_file() else None


def library_id() -> str | None:
    return (get("LIBRARY_DRIVE_FOLDER_ID") or "").strip() or None


def client() -> Drive | None:
    """The worker's Drive, or None until the key file and the library folder are set (docs/RUNBOOK.md)."""
    found = key_file()
    if found is None or library_id() is None:
        return None
    return GoogleDrive(found)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def folder_name(day: str, portal: str, title: str | None) -> str:
    """YYYY-MM-DD_portal_short-title, as lib/proposals.ts folderName and the library's conventions have it."""
    short = slug(" ".join((title or "").split()[:3])) or "untitled"
    return f"{day}_{slug(portal)}_{short}"


def _folder(found: Drive, parent_id: str, name: str) -> dict[str, Any]:
    return found.find(parent_id, name, folder=True) or found.make_folder(parent_id, name)


def pursuit_folder(found: Drive, library: str, name: str, taken: set[str]) -> dict[str, Any]:
    """The pursuit's folder under Submissions/ with its four folders, made once. A folder of that name that another
    pursuit already has gets a number added; one nobody has is this pursuit's, made before the worker last stopped."""
    submissions = _folder(found, library, SUBMISSIONS)
    for n in range(1, 50):
        candidate = name if n == 1 else f"{name}-{n}"
        existing = found.find(submissions["id"], candidate, folder=True)
        if existing and existing["id"] in taken:
            continue
        folder = existing or found.make_folder(submissions["id"], candidate)
        for part in SUBFOLDERS:
            _folder(found, folder["id"], part)
        return {"id": folder["id"], "name": candidate, "path": f"{SUBMISSIONS}/{candidate}"}
    raise DriveError("too many folders with that name")


def upload(found: Drive, folder_id: str, path: Path) -> dict[str, str]:
    """A file into the pursuit's 02_working/, replacing an earlier version of the same name."""
    working = _folder(found, folder_id, WORKING)
    saved = found.upload(working["id"], path, path.name, MIME_TYPES.get(path.suffix.lower(), "application/octet-stream"))
    return {"id": saved["id"], "link": saved.get("webViewLink") or f"https://drive.google.com/file/d/{saved['id']}/view"}


def move_to_no_go(found: Drive, library: str, folder_id: str) -> None:
    """A stopped pursuit's folder into Submissions/_no-go/, so the library's submissions stay real ones."""
    submissions = _folder(found, library, SUBMISSIONS)
    found.move(folder_id, _folder(found, submissions["id"], NO_GO)["id"])


def _row(item: dict[str, Any], path: str, parent: str, now: str) -> dict[str, Any]:
    return {"id": item["id"], "name": item["name"], "mime": item.get("mimeType"), "path": path, "parent_id": parent,
            "web_link": item.get("webViewLink"), "modified_at": item.get("modifiedTime"), "indexed_at": now}


def index_library(found: Drive, library: str, now: str = "") -> list[dict[str, Any]]:
    """The past work Builds on offers: each submission's folder and what went in (its 01_submitted/), and the files
    in 01 Company Reference/, two folders deep. No-go folders and working files are left out."""
    from ledger.db import now_iso

    now = now or now_iso()
    rows: list[dict[str, Any]] = []
    top = {i["name"]: i for i in found.children(library) if i["mimeType"] == FOLDER_MIME}
    if SUBMISSIONS in top:
        for folder in found.children(top[SUBMISSIONS]["id"]):
            if folder["mimeType"] != FOLDER_MIME or folder["name"] == NO_GO:
                continue
            path = f"{SUBMISSIONS}/{folder['name']}"
            rows.append(_row(folder, path, top[SUBMISSIONS]["id"], now))
            submitted = found.find(folder["id"], "01_submitted", folder=True)
            for item in found.children(submitted["id"]) if submitted else []:
                if item["mimeType"] != FOLDER_MIME:
                    rows.append(_row(item, f"{path}/01_submitted/{item['name']}", submitted["id"], now))
    if COMPANY_REFERENCE in top:
        queue = [(top[COMPANY_REFERENCE]["id"], COMPANY_REFERENCE, 0)]
        while queue:
            parent, path, depth = queue.pop(0)
            for item in found.children(parent):
                if item["mimeType"] == FOLDER_MIME:
                    if depth < 1:
                        queue.append((item["id"], f"{path}/{item['name']}", depth + 1))
                else:
                    rows.append(_row(item, f"{path}/{item['name']}", parent, now))
    return rows


def check(found: Drive, library: str) -> list[str]:
    """What --drive-check prints: whether the library folder can be read and what it holds. It only reads."""
    try:
        items = found.children(library)
    except DriveError as exc:
        return [f"can see the library folder: no ({exc})"]
    name = found.get(library, fields="name")["name"]
    folders = sum(1 for i in items if i["mimeType"] == FOLDER_MIME)
    return [f"can see the library folder: yes, {name!r}", f"items inside: {len(items)}, {folders} of them folders",
            f"{SUBMISSIONS}/ found: {'yes' if any(i['name'] == SUBMISSIONS for i in items) else 'no'}"]
