"""AFWERX's and SpaceWERX's SBIR and STTR cycles, as stored in the ledger, for DSIP: a dropped DOCX topic takes its dates
from the cycle that names its release, and the watch alerts on an open cycle with no topics.

    cycles = stored_cycles()
    cycle = cycle_for(("27", "BZ", 1), cycles)   # "DOW SBIR SPECIFIC TOPIC 27.BZ & 27.BX Release 1"
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Any

from ledger.queries import calls_on
from portals.dsip.records import Cycle
from portals.dsip.topics import Key, cycle_keys
from portals.shared.funding_list import CYCLES

CYCLE_PORTALS = ("AFWERX", "SpaceWERX")


def _day(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def cycles_of(calls: Iterable[dict[str, Any]]) -> list[Cycle]:
    """The SBIR and STTR cycles among these calls whose titles name a release; their dates from the adapters' extra keys
    (<prefix>_pre_release, <prefix>_open, <prefix>_closed) and the close date from due_date."""
    found: list[Cycle] = []
    for call in calls:
        keys = cycle_keys(str(call.get("title") or ""))
        if call.get("type") not in CYCLES or not keys:
            continue
        extra = call.get("extra") or {}

        def ending(suffix: str, extra: dict[str, Any] = extra) -> Any:
            return next((value for key, value in extra.items() if key.endswith(suffix)), None)

        found.append(Cycle(portal=str(call.get("portal") or ""), title=str(call.get("title") or ""), keys=frozenset(keys),
                           pre_release=_day(ending("_pre_release")), open=_day(ending("_open")),
                           close=_day(call.get("due_date")), closed=bool(ending("_closed"))))
    return found


def stored_cycles() -> list[Cycle]:
    return cycles_of(calls_on(CYCLE_PORTALS))


def cycle_for(key: Key, cycles: list[Cycle]) -> Cycle | None:
    """The cycle naming this release, an open one first."""
    named = [cycle for cycle in cycles if key in cycle.keys]
    return next((cycle for cycle in named if not cycle.closed), named[0] if named else None)
