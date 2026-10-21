"""The drafting phases in order, with the names everything that reports progress uses."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Phase:
    id: str
    name: str
    label: str = ""      # what the reference called the model call, e.g. "drafting response"


PHASES: list[Phase] = [
    Phase("1", "Listing"),
    Phase("2", "Attachments"),
    Phase("3", "Past experience"),
    Phase("4", "Requirements", "analyzing requirements"),
    Phase("4.5", "Alignment", "assessing alignment"),
    Phase("5", "Outline", "building outline"),
    Phase("6", "Draft", "drafting response"),
    Phase("6.5", "Review ×4", "review pass"),
    Phase("6.75", "Compliance", "compliance check"),
    Phase("7", "Checklist", "building checklist"),
    Phase("7.5", "Polish", "formatting document"),
    Phase("7.6", "Opening", "framing the opening"),   # Velocity's addition (PRO-494): a person writes the opening
    Phase("7.7", "Slop check"),                        # Velocity's addition (PRO-510): ready or not ready
    Phase("8", "Deliver"),
]


def index(phase_id: str) -> int:
    """Position of a phase in PHASES. KeyError, with the valid ids, for an unknown one."""
    for i, p in enumerate(PHASES):
        if p.id == str(phase_id):
            return i
    raise KeyError(f"No phase {phase_id}. Phases: {', '.join(p.id for p in PHASES)}.")


def phase(phase_id: str) -> Phase:
    return PHASES[index(phase_id)]
