"""The dashboard's local servers listen on this PC only (PRO-565): `npm run dev` and `npm start` bind 127.0.0.1,
where Next's default is 0.0.0.0, every address the PC has. The team reaches the hosted container through the
tunnel instead. Reads files only."""
from __future__ import annotations

import json
from pathlib import Path

DASHBOARD = Path(__file__).resolve().parent.parent / "dashboard"


def _script(name: str) -> str:
    return json.loads((DASHBOARD / "package.json").read_text(encoding="utf-8"))["scripts"][name]


def test_the_local_servers_listen_on_loopback_only() -> None:
    for name in ("dev", "start"):
        assert "--hostname 127.0.0.1" in _script(name), name
