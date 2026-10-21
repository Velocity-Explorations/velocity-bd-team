"""The Writer's command line.

    python -m drafting.cli dev --inputs tests/fixtures/sample_inputs.json --out data/drafting/sample/
    python -m drafting.cli dev --inputs ... --out ... --from-phase 6.5 --to-phase 6.5   # only the review passes
    python -m drafting.cli dev --inputs ... --out ... --model claude-haiku-5-5

`dev` runs the pipeline from an inputs JSON file into a local folder, with progress on
stdout and a per-phase timing table at the end. Phase 7.6 leaves the draft's opening for a
person to write (PRO-494); phase 7.7 runs the slop check (PRO-510), and the last lines say how
many places are marked PERSON WRITES and whether the draft is ready.

    python -m drafting.cli check --draft data/drafting/sample/draft_final.md

`check` reruns the slop check after someone edits a draft, rewrites slop_report.md beside it,
and exits 0 when the draft is ready, 1 when it is not, 2 when it cannot check. It writes the inputs it used to
<out>/source/inputs.json so a run can be repeated. Later phases add subcommands that work
from the ledger (W1 `dev --call-id`, W2a `request`, `run`, `status`).
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from drafting import slop_gate
from drafting.phases import phase
from drafting.pipeline import DraftInputs, DraftOutputs, PrintHooks, run_pipeline


def _table(outputs: DraftOutputs) -> list[str]:
    lines = [f"{'phase':>6}  {'name':16s} {'status':10s} {'seconds':>8} {'chars in':>10} {'chars out':>10} "
             f"{'tokens in':>10} {'tokens out':>10}"]
    total = 0.0
    for phase_id, stats in outputs.phases.items():
        calls = stats.get("calls", [])
        seconds = float(stats.get("seconds", 0) or 0)
        total += seconds
        lines.append(f"{phase_id:>6}  {phase(phase_id).name:16s} {stats['status']:10s} {seconds:8.1f} "
                     f"{stats.get('chars_in', 0):10,d} {stats.get('chars_out', 0):10,d} "
                     f"{sum(c['input_tokens'] for c in calls):10,d} {sum(c['output_tokens'] for c in calls):10,d}")
    lines.append(f"{'':>6}  {'total':16s} {'':10s} {total:8.1f}")
    return lines


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m drafting.cli", description="The Writer's drafting pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    dev = sub.add_parser("dev", help="run the pipeline from an inputs JSON file into a local folder")
    dev.add_argument("--inputs", required=True, type=Path, help="inputs JSON (see tests/fixtures/sample_inputs.json)")
    dev.add_argument("--out", required=True, type=Path, help="folder for the phase files")
    dev.add_argument("--from-phase", help="start here; earlier phases load their saved files")
    dev.add_argument("--to-phase", help="stop after this phase")
    dev.add_argument("--model", help="model id for every call (default claude-sonnet-5-5)")
    dev.add_argument("--debug", action="store_true", help="log full prompts (DEBUG)")
    check = sub.add_parser("check", help="rerun the slop check on a draft after it was edited")
    check.add_argument("--draft", required=True, type=Path, help="the draft to check, such as draft_final.md")
    check.add_argument("--inputs", type=Path, help="inputs JSON for the solicitation text (default: source/inputs.json beside the draft)")
    return parser


def check_draft(draft: Path, inputs_path: Path | None) -> int:
    """The slop check on one draft, with its verdict printed. 0 ready, 1 not ready, 2 cannot check."""
    if not draft.exists():
        print(f"No draft at {draft}")
        return 2
    inputs_path = inputs_path or draft.parent / "source" / "inputs.json"
    solicitation = None
    if inputs_path.exists():
        text = slop_gate.solicitation_text(DraftInputs.load(inputs_path))
        if text:
            solicitation = draft.parent / "source" / "solicitation.txt"
            solicitation.parent.mkdir(parents=True, exist_ok=True)
            solicitation.write_text(text, encoding="utf-8")
    try:
        report = slop_gate.run_scan(draft, solicitation)
    except slop_gate.ScanError as exc:
        print(exc)
        return 2
    gate = slop_gate.summarize(report)
    (draft.parent / "slop_report.md").write_text(slop_gate.render_report(gate, draft), encoding="utf-8")
    print(slop_gate.verdict(gate))
    return 0 if gate.ready else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "check":
        return check_draft(args.draft, args.inputs)
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    for noisy in ("httpx", "httpcore", "httpx2", "httpcore2", "anthropic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    try:
        for phase_id in (args.from_phase, args.to_phase):
            if phase_id:
                phase(phase_id)
    except KeyError as exc:
        print(exc.args[0])
        return 2
    inputs = DraftInputs.load(args.inputs)
    inputs.save(args.out / "source" / "inputs.json")
    outputs = run_pipeline(inputs, args.out, PrintHooks(), args.from_phase, args.to_phase, model=args.model)
    print()
    for line in _table(outputs):
        print(line)
    print(f"\nFinal draft: {outputs.final_draft or 'none'}")
    held = outputs.phases.get("7.6", {}).get("person_writes")
    if held:
        print(f"{held} place{'s' if held > 1 else ''} for a person to write, marked PERSON WRITES in the draft")
    checked = outputs.phases.get("7.7", {})
    print(checked.get("verdict") or f"Slop check not run: {checked.get('note') or checked.get('status', 'not run')}")
    return 1 if any(s["status"] == "failed" for s in outputs.phases.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
