"""What a DoD topic number says, and which solicitations and release a cycle's title names. Pure: no network, no ledger.

    topic = parse_topic_number("DAF27BZ02-DV023")   # Air Force, solicitation 27.BZ, Release 2, SBIR, Direct to Phase II
    topic.key                                        # ("27", "BZ", 2)
    cycle_keys("DOW SBIR SPECIFIC TOPIC 27.BZ & 27.BX Release 1")   # {("27", "BZ", 1), ("27", "BX", 1)}

Since the FY27 solicitations a topic number reads component, year, solicitation code, release, track and serial:
DAF 27 BZ 02 - DV 023. A solicitation code starting B is SBIR and T is STTR; a track starting D is Direct to Phase II
and N is Phase I. All 102 topics of 27.BZ, 27.BX and 27.TZ Releases 1 and 2 follow it (the 10 Nov 2026 screen).
Topics numbered the older way (HR0011SB20264-01, N252-089) do not, and take their details from SBIR.gov's page.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

TOPIC = re.compile(r"^([A-Z]{3})(\d{2})([A-Z]{2})(\d{2})-([A-Z]{2})(\d{3})$")
SOLICITATION = re.compile(r"\b(\d{2})\.([A-Z]{2})\b")
RELEASE = re.compile(r"(?i)\brelease\s+(\d{1,2})\b")
ID_PREFIX = "dsip-"

COMPONENTS = {
    "ARM": "Army",
    "CBD": "Chemical and Biological Defense",
    "DAF": "Department of the Air Force",
    "DHA": "Defense Health Agency",
    "DLA": "Defense Logistics Agency",
    "DMA": "Defense Microelectronics Activity",
    "DON": "Department of the Navy",
    "DPA": "DARPA",
    "DTR": "DTRA",
    "MDA": "Missile Defense Agency",
    "NGA": "National Geospatial-Intelligence Agency",
    "OSW": "Office of the Secretary of War",
    "SCO": "Strategic Capabilities Office",
    "SDA": "Space Development Agency",
    "SOC": "SOCOM",
}

Key = tuple[str, str, int]   # (year, solicitation code, release): ("27", "BZ", 2)


@dataclass(frozen=True)
class TopicNumber:
    text: str
    component: str
    year: str
    code: str
    release: int
    track: str

    @property
    def solicitation(self) -> str:
        return f"{self.year}.{self.code}"

    @property
    def program(self) -> str:
        return {"B": "SBIR", "T": "STTR"}.get(self.code[0], "SBIR/STTR")

    @property
    def phase(self) -> str:
        return "Direct to Phase II" if self.track.startswith("D") else "Phase I"

    @property
    def key(self) -> Key:
        return (self.year, self.code, self.release)


def parse_topic_number(text: str) -> TopicNumber | None:
    """The parts of a topic number written the FY27 way, or None for any other."""
    clean = (text or "").strip().upper()
    found = TOPIC.match(clean)
    if not found:
        return None
    component, year, code, release, track, _serial = found.groups()
    return TopicNumber(text=clean, component=component, year=year, code=code, release=int(release), track=track)


def call_id(topic: str) -> str:
    """dsip-<topic number in lower case>: the id the three topics added by hand on 10 Nov 2026 carry."""
    return f"{ID_PREFIX}{topic.strip().lower()}"


def component_name(code: str) -> str:
    """ "Department of the Navy (DON)" for a known component code; the code itself otherwise."""
    return f"{COMPONENTS[code]} ({code})" if code in COMPONENTS else code


def cycle_keys(title: str) -> set[Key]:
    """The solicitations and release a cycle's title names ("27.BZ & 27.BX Release 1"); empty when it names no release."""
    release = RELEASE.search(title or "")
    if not release:
        return set()
    return {(year, code, int(release.group(1))) for year, code in SOLICITATION.findall(title)}


def key_of_call(call_id_text: str, extra: dict) -> Key | None:
    """The release a stored DSIP call belongs to: from its dsip_topic, or from its id (topics added by hand have no extra)."""
    topic = parse_topic_number(str(extra.get("dsip_topic") or ""))
    if topic is None and call_id_text.startswith(ID_PREFIX):
        topic = parse_topic_number(call_id_text[len(ID_PREFIX):])
    return topic.key if topic else None
