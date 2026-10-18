"""The Writer's command line.

    python -m drafting.cli dev --inputs tests/fixtures/sample_inputs.json --out data/drafting/sample/
    python -m drafting.cli dev --inputs ... --out ... --from-phase 6.5 --to-phase 6.5   # only the review passes
    python -m drafting.cli dev --inputs ... --out ... --model claude-haiku-5-5

`dev` runs the pipeline from an inputs JSON file into a local folder, with progress on
stdout and a per-phase timing table at the end. It writes the inputs it used to
<out>/source/inputs.json so a run can be repeated. Later phases add subcommands that work
from the ledger (W1 `dev --call-id`, W2a `request`, `run`, `status`).
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
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
    return 1 if any(s["status"] == "failed" for s in outputs.phases.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
