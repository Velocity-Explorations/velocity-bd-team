"""scripts/install-schedule.ps1: tasks open no window, and approved requests run twice a day."""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = (REPO / "scripts" / "install-schedule.ps1").read_text(encoding="utf-8")


def request_times() -> list[str]:
    match = re.search(r"\[string\[\]\]\$RequestsAt\s*=\s*@\(([^)]*)\)", SCRIPT)
    assert match, "install-schedule.ps1 has no [string[]]$RequestsAt parameter"
    return re.findall(r'"(\d\d:\d\d)"', match.group(1))


def test_every_task_starts_python_in_a_headless_console() -> None:
    actions = re.findall(r"New-ScheduledTaskAction\s+(.*)", SCRIPT)
    assert len(actions) >= 2
    for action in actions:
        assert action.startswith("-Execute $conhost -Argument (Headless "), action
    assert re.search(r'\$conhost\s*=\s*Join-Path \$env:SystemRoot "System32\\conhost\.exe"', SCRIPT)
    helper = re.search(r"function Headless\(\[string\]\$Arguments\)\s*\{([^}]*)\}", SCRIPT)
    assert helper, "no Headless helper"
    assert "--headless" in helper.group(1) and "$python" in helper.group(1)


def test_approved_requests_run_at_most_twice_a_day() -> None:
    times = request_times()
    assert 1 <= len(times) <= 2
    assert "RepetitionInterval" not in SCRIPT
    assert "New-ScheduledTaskTrigger -Daily -At $_" in SCRIPT


def test_people_are_told_the_same_request_times() -> None:
    told = " or ".join(request_times())
    for path in (REPO / "assistant" / "requests.py", REPO / "dashboard" / "lib" / "requests.ts"):
        assert told in path.read_text(encoding="utf-8"), path.name


def test_docs_no_longer_promise_fifteen_minutes() -> None:
    for name in ("ASSISTANT.md", "DASHBOARD.md", "RUNBOOK.md", "STATUS.md"):
        assert "15 minutes" not in (REPO / "docs" / name).read_text(encoding="utf-8"), name


def test_weekly_scan_runs_sunday_night_and_may_wake_the_pc() -> None:
    assert '[string]$Day = "Sunday"' in SCRIPT and '[string]$At = "22:00"' in SCRIPT
    pipeline_settings = SCRIPT.split("$settings = New-ScheduledTaskSettingsSet `", 1)[1].split("Register-ScheduledTask", 1)[0]
    assert "-WakeToRun" in pipeline_settings
