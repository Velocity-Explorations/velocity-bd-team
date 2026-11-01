"""The past bids nearest a pursued call: what each sent in (01_submitted) and what came back (03_outcome), read from
the Proposal Library for the Outline and the First draft (PRO-565). A fake Drive stands in, and the bids are made up."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Any

import docx
import pytest

from drafting import drive, inputs, past_bids, steps, write
from ledger import queries as lq
from tests.test_drafting_drive import DOCX, FOLDER, FakeDrive
from tests.test_drafting_write import EARLIER, Model, _context

PDF = "application/pdf"
PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
GDOC = "application/vnd.google-apps.document"


def tiny_pdf(text: str) -> bytes:
    """A one-page PDF that says text."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
               b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream"]
    out, offsets = b"%PDF-1.4\n", []
    for n, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % n + body + b"\nendobj\n"
    table = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offsets)
    return out + b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, table)


def docx_bytes(*paragraphs: str) -> bytes:
    document = docx.Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    out = io.BytesIO()
    document.save(out)
    return out.getvalue()


def pptx_bytes(*slides: str) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for n, text in enumerate(slides, start=1):
            z.writestr(f"ppt/slides/slide{n}.xml", f"<p:sld><p:txBody><a:t>{text}</a:t></p:txBody></p:sld>")
    return out.getvalue()


def bid(fake: FakeDrive, submission_id: str, submitted: dict[str, tuple[str, bytes]],
        outcome: dict[str, tuple[str, bytes]] | None = None) -> None:
    folder = fake.add(submission_id, FOLDER, fake.submissions)["id"]
    for sub, files in (("01_submitted", submitted), ("03_outcome", outcome or {})):
        parent = fake.add(sub, FOLDER, folder)["id"]
        for name, (mime, content) in files.items():
            fake.add(name, mime, parent)["content"] = content


def row(submission_id: str, **values: Any) -> dict[str, Any]:
    return {"submission_id": submission_id, "title": submission_id.split("_")[-1].replace("-", " "), **values}


def record(*rows: dict[str, Any]) -> inputs.CallRecord:
    return inputs.CallRecord(pursuit={"id": 1, "owner": "David Wood"}, call={"id": "sam-1", "title": "Edge speech"},
                             judges={}, decisions=[], past_work=list(rows))


@pytest.fixture
def library(monkeypatch: pytest.MonkeyPatch) -> FakeDrive:
    fake = FakeDrive()
    monkeypatch.setattr(drive, "client", lambda: fake)
    monkeypatch.setattr(drive, "library_id", lambda: fake.library)
    return fake


def test_the_nearest_bids_with_files_are_read_in_order_with_what_came_back(library: FakeDrive) -> None:
    bid(library, "2026-01-15_dsip_edge-speech", {
        "technical-volume.pdf": (PDF, tiny_pdf("Our edge speech approach won on its test plan")),
        "quad-chart.pptx": (PPTX, pptx_bytes("Hear every net", "Offline at the edge")),
        "cost-volume.xlsx": (XLSX, b"rates"), "budget-notes.docx": (DOCX, docx_bytes("Rate 1"))},
        {"debrief.docx": (DOCX, docx_bytes("Evaluators praised the field results", "Weakness: no transition partner"))})
    bid(library, "2025-02-03_apfit_example-support", {"white-paper": (GDOC, b"The decision support white paper text")})
    bid(library, "2025-06-01_sam-gov_empty", {})
    bid(library, "2025-01-02_diu_ops", {"proposal.docx": (DOCX, docx_bytes("Ops proposal text"))})
    bid(library, "2024-12-01_diu_fourth", {"proposal.docx": (DOCX, docx_bytes("A fourth bid, past the limit"))})
    found = past_bids.read(record(row("2026-05-01_other_no-folder"),
                                  row("2026-01-15_dsip_edge-speech", outcome="won", strength_rating=4, why_won_or_lost="Field data"),
                                  row("2025-02-03_apfit_example-support", outcome="lost"), row("2025-06-01_sam-gov_empty"),
                                  row("2025-01-02_diu_ops"), row("2024-12-01_diu_fourth")))
    assert found.read == ["2026-01-15_dsip_edge-speech", "2025-02-03_apfit_example-support", "2025-01-02_diu_ops"]
    text = found.text
    assert text.startswith("PAST BIDS NEAREST THIS CALL") and "never from these texts" in text
    assert "=== 2026-01-15_dsip_edge-speech: edge speech (outcome won, strength 4/5)" in text and "Why it won or lost: Field data" in text
    for expected in ("--- 01_submitted/technical-volume.pdf", "Our edge speech approach won on its test plan",
                     "--- 01_submitted/quad-chart.pptx", "Hear every net", "--- 03_outcome/debrief.docx",
                     "Weakness: no transition partner", "The decision support white paper text", "Ops proposal text"):
        assert expected in text, expected
    assert "cost-volume" not in text and "budget-notes" not in text and "A fourth bid" not in text   # numbers, and the limit
    assert found.line == ("Past bids read: 3, nearest first (2026-01-15_dsip_edge-speech, 2025-02-03_apfit_example-support, "
                          "2025-01-02_diu_ops)")


def test_the_narrative_comes_first_and_the_paperwork_stays_out(library: FakeDrive) -> None:
    """A live check on 1 Nov spent a bid's room on a 12,000-character cover sheet before its full proposal."""
    bid(library, "2025-08-01_dsip_example-bid", {
        "cover-sheet.pdf": (PDF, tiny_pdf("DSIP cover sheet")), "foreign-affiliations.pdf": (PDF, tiny_pdf("None")),
        "letter-of-commitment.docx": (DOCX, docx_bytes("We commit")), "full-proposal.pdf": (PDF, tiny_pdf("The full proposal")),
        "a-safety-report.docx": (DOCX, docx_bytes("Safety findings")), "briefing.pptx": (PPTX, pptx_bytes("Brief")),
        "dd2345-technical-data-agreement.pdf": (PDF, tiny_pdf("Form DD2345"))},
        {"award-letter.pdf": (PDF, tiny_pdf("Selected for award"))})
    text = past_bids.read(record(row("2025-08-01_dsip_example-bid"))).text
    order = [text.index(f"--- 01_submitted/{name}") for name in ("full-proposal.pdf", "briefing.pptx", "a-safety-report.docx")]
    assert order == sorted(order)                                  # volumes, then slides, then the rest
    assert "cover sheet" not in text and "foreign-affiliations" not in text and "We commit" not in text
    assert "Form DD2345" not in text
    assert "Selected for award" in text   # in 03_outcome a letter is the outcome itself


def test_a_long_file_is_cut_and_says_where(library: FakeDrive, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(past_bids, "FILE_CHARS", 20)
    bid(library, "2026-01-15_dsip_edge-speech", {"technical-volume.docx": (DOCX, docx_bytes("A" * 50))})
    text = past_bids.read(record(row("2026-01-15_dsip_edge-speech"))).text
    assert "--- 01_submitted/technical-volume.docx (its first 20 characters)" in text and "A" * 21 not in text


def test_no_dash_from_a_past_bid_reaches_a_prompt(library: FakeDrive) -> None:
    bid(library, "2026-01-15_dsip_edge-speech", {"white-paper.docx": (DOCX, docx_bytes(f"Echo {chr(0x2014)} offline, pages 3{chr(0x2013)}5"))})
    text = past_bids.read(record(row("2026-01-15_dsip_edge-speech"))).text
    assert steps.count_dashes(text) == 0 and "Echo, offline, pages 3 to 5" in text


def test_drive_trouble_or_no_drive_leaves_a_note_and_no_bids(library: FakeDrive, monkeypatch: pytest.MonkeyPatch) -> None:
    library.fail = True
    found = past_bids.read(record(row("2026-01-15_dsip_edge-speech")))
    assert found.read == [] and "could not be read" in found.text and found.line.startswith("Past bids read: none")
    monkeypatch.setattr(drive, "client", lambda: None)
    assert "Drive is not set up" in past_bids.read(record(row("2026-01-15_dsip_edge-speech"))).text


def test_themes_the_call_shares_bring_a_past_bid_nearer(ledger_db: str) -> None:
    run_id = lq.start_run("sam_gov")
    lq.upsert_call({"id": "sam-1", "portal": "SAM.gov", "title": "Speech for operators", "department": "AIR FORCE",
                    "description": "Real-time transcription and translation of radio nets."}, run_id)
    lq.set_human("sam-1", "pursue", "David Wood")
    lq.upsert_proposal({"submission_id": "2025-01-01_diu_logistics", "title": "Logistics", "agency": "AIR FORCE"})
    lq.upsert_proposal({"submission_id": "2025-02-01_diu_nets", "title": "Nets", "agency": "AIR FORCE",
                        "themes": ["transcription", "translation"]})
    record = inputs.gather(lq.start_pursuit("sam-1", "David Wood"))
    assert [p["submission_id"] for p in record.past_work] == ["2025-02-01_diu_nets", "2025-01-01_diu_logistics"]


def test_the_outline_and_the_first_draft_read_the_nearest_past_bids(ledger_db: str, tmp_path: Path, library: FakeDrive) -> None:
    lq.upsert_proposal({"submission_id": "2026-01-15_dsip_edge-speech", "title": "Edge speech", "outcome": "won"})
    bid(library, "2026-01-15_dsip_edge-speech", {"white-paper.docx": (DOCX, docx_bytes("The winning white paper said this"))})
    model = Model()
    ctx = _context(tmp_path, model, "outline", EARLIER)
    outlined = write.outline(ctx)
    drafted = write.draft(ctx)
    for label in ("building outline", "drafting response"):
        assert "The winning white paper said this" in model.prompt(label).user, label
    for result in (outlined, drafted):
        assert "Past bids read" in [f["name"] for f in result.files]
        assert "- Past bids read: 1, nearest first (2026-01-15_dsip_edge-speech)" in result.summary.splitlines()
    assert (ctx.work_dir / "past_bids.md").read_text(encoding="utf-8").startswith("PAST BIDS NEAREST THIS CALL")
