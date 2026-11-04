"""Each process the scheduled tasks and the docs start imports cleanly in a fresh interpreter. A circular import shows
only in the order a real start takes: on 4 Nov one stopped the worker while every other test passed."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("module", ["drafting.worker", "drafting.cli", "drafting.pipeline", "drafting.slop_gate", "drafting.scan", "run"])
def test_an_entry_point_imports_in_a_fresh_interpreter(module: str) -> None:
    done = subprocess.run([sys.executable, "-c", f"import {module}"], cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", timeout=180)
    assert done.returncode == 0, done.stderr[-2000:]
