# Hidden windows for the scheduled tasks

**Decision (2026-10-19, PR #6):** every Task Scheduler action runs
`conhost.exe --headless "<venv>\python.exe" run.py ...`. No console window opens for python
or for any program it starts.

**Problem:** the tasks ran `python.exe` with an interactive logon, so each run opened a
console window on the desktop. The approved-requests job ran every 15 minutes, so a window
appeared every few minutes. That job now runs twice a day, at 12:07 and 17:07.

| Option | Result |
|---|---|
| `conhost.exe --headless` (chosen) | No window for python or its children (git, gh, powershell, tasklist): they share the hidden console. Tested 2026-10-19: a child `cmd` ran and wrote its output. |
| `pythonw.exe` | No window for python itself, but each console child it starts opens its own window unless every `subprocess.run` passes `CREATE_NO_WINDOW` (run.py, portals/shared/browser.py, portals/shared/otp.py). |
| "Run whether user is logged on or not" (S4U) | No window, but an S4U logon carries no password, so Windows Credential Manager (the gh login fallback, git pushes) is likely out of reach. Not tested. |
| VBScript `WScript.Shell.Run cmd, 0` | Hides the tree and keeps the exit code, but Windows is retiring VBScript. |

**Cost of the choice:** conhost returns 0 whatever python's exit code (tested: python exited
3, conhost reported 0). Task Scheduler's Last Run Result therefore always reads 0, so
failures are found in the Slack alerts and data\logs (docs/RUNBOOK.md).

**Revisit when:** a run fails silently, or the dashboard is hosted and the tasks move off
David's PC.
