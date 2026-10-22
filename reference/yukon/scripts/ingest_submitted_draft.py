#!/usr/bin/env python3
"""
Ingest submitted draft documents from Google Drive into ChromaDB.
Triggered when a user marks a draft as "submitted" — downloads the most recently
modified documents from the opp's Drive folder and embeds them for future RAG.

Usage:
  python scanner/scripts/ingest_submitted_draft.py \
    --drive-folder-id FOLDER_ID \
    --profile velocity \
    --opp-title "AI/ML Support for JADC2" \
    --opp-id 123
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scanner.text_extract import extract_text, infer_doc_type, make_slug, chunk_text, embed, EXTRACTORS

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

GOG = "/opt/homebrew/bin/gog"
CHROMA_PATH = str(Path(__file__).parent.parent / "data" / "chroma")
MAX_FILES = 5


def list_drive_files(folder_id: str, account: str) -> list:
    result = subprocess.run(
        [GOG, "drive", "ls", "--parent", folder_id, "-a", account, "-j",
         "--results-only", "--max", "20"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        log.error(f"gog drive ls failed: {result.stderr[:200]}")
        return []

    try:
        files = json.loads(result.stdout)
        if isinstance(files, dict):
            files = files.get("files", [])
        if not isinstance(files, list):
            return []
        return files
    except json.JSONDecodeError:
        log.error(f"Failed to parse gog output: {result.stdout[:200]}")
        return []


def download_drive_file(file_id: str, dest: Path, account: str,
                        mime_type: str = "") -> bool:
    cmd = [GOG, "drive", "download", file_id, "-a", account,
           "--out", str(dest)]

    if mime_type.startswith("application/vnd.google-apps"):
        cmd.extend(["--format", "docx"])

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        log.error(f"Download failed for {file_id}: {result.stderr[:200]}")
        return False
    return True


def ingest_from_drive(folder_id: str, profile: str, opp_title: str,
                      opp_id: int, account: str):
    import chromadb

    files = list_drive_files(folder_id, account)
    if not files:
        log.warning(f"No files found in Drive folder {folder_id}")
        return

    sortable = []
    for f in files:
        name = f.get("name", "")
        mime = f.get("mimeType", "")
        file_id = f.get("id", "")
        modified = f.get("modifiedTime", "") or f.get("modifiedDate", "")

        is_google_doc = mime.startswith("application/vnd.google-apps")
        ext = Path(name).suffix.lower()
        supported = ext in EXTRACTORS or is_google_doc

        if not supported and not is_google_doc:
            continue

        sortable.append({
            "id": file_id,
            "name": name,
            "mime": mime,
            "modified": modified,
            "is_google_doc": is_google_doc,
        })

    sortable.sort(key=lambda x: x["modified"], reverse=True)
    to_process = sortable[:MAX_FILES]

    log.info(f"Found {len(sortable)} supported files, processing top {len(to_process)} by recency")

    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_or_create_collection(
        "bd_documents",
        metadata={"description": "Velocity past BD submissions and capability documents"},
    )

    total_chunks = 0
    processed_files = []

    with tempfile.TemporaryDirectory() as tmpdir:
        for f in to_process:
            dest_name = f["name"]
            if f["is_google_doc"]:
                dest_name = f"{Path(f['name']).stem}.docx"

            dest = Path(tmpdir) / dest_name
            log.info(f"Downloading: {f['name']} → {dest_name}")

            if not download_drive_file(f["id"], dest, account, f["mime"]):
                continue

            actual_path = dest
            if not actual_path.exists():
                candidates = list(Path(tmpdir).glob(f"{Path(f['name']).stem}*"))
                if candidates:
                    actual_path = candidates[0]
                else:
                    log.warning(f"Downloaded file not found at {dest}")
                    continue

            try:
                text = extract_text(actual_path)
                if not text.strip():
                    log.warning(f"Empty text: {f['name']}")
                    continue

                chunks = chunk_text(text)
                slug = make_slug(f["name"])
                doc_type = infer_doc_type(f["name"])

                all_ids = []
                all_docs = []
                all_embeddings = []
                all_metadatas = []

                for i, chunk in enumerate(chunks):
                    doc_id = f"submitted_{profile}_{opp_id}_{slug}_{i}"
                    emb = embed(chunk)
                    meta = {
                        "filename": f["name"],
                        "doc_type": doc_type,
                        "source": f"submitted_draft_opp_{opp_id}",
                        "source_type": "submitted_draft",
                        "profile": profile,
                        "opportunity_title": opp_title[:200],
                        "opportunity_id": str(opp_id),
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                    }
                    all_ids.append(doc_id)
                    all_docs.append(chunk)
                    all_embeddings.append(emb)
                    all_metadatas.append(meta)

                batch_size = 100
                for j in range(0, len(all_ids), batch_size):
                    end = min(j + batch_size, len(all_ids))
                    collection.upsert(
                        ids=all_ids[j:end],
                        documents=all_docs[j:end],
                        embeddings=all_embeddings[j:end],
                        metadatas=all_metadatas[j:end],
                    )

                total_chunks += len(chunks)
                processed_files.append(f["name"])
                log.info(f"  → {len(chunks)} chunks embedded ({doc_type})")

            except Exception as e:
                log.error(f"Failed to process {f['name']}: {e}")

    log.info(f"Ingestion complete: {len(processed_files)} files, {total_chunks} chunks. "
             f"Collection now has {collection.count()} items")


def main():
    parser = argparse.ArgumentParser(description="Ingest submitted draft from Google Drive into ChromaDB")
    parser.add_argument("--drive-folder-id", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--opp-title", required=True)
    parser.add_argument("--opp-id", type=int, required=True)
    parser.add_argument("--account", help="Google Drive account email (overrides profile config)")
    args = parser.parse_args()

    account = args.account
    if not account:
        from scanner.profile import load_profile
        profile = load_profile(args.profile)
        account = profile.google_drive_account
        if not account:
            log.error("No Google Drive account configured for this profile")
            sys.exit(1)

    ingest_from_drive(
        folder_id=args.drive_folder_id,
        profile=args.profile,
        opp_title=args.opp_title,
        opp_id=args.opp_id,
        account=account,
    )


if __name__ == "__main__":
    main()
