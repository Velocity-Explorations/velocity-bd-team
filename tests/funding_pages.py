"""Made-up Get Funded pages shaped like AFWERX's and SpaceWERX's, which share one site template.

Each listing appears twice, as a grid row (badges, title, three dates) and as a labelled block
for small screens. Used by the tests of portals/shared/funding_list.py and of both adapters.
"""
from __future__ import annotations

import urllib.error
from typing import Any

DSIP_LOGIN = "https://www.dodsbirsttr.mil/submissions/login"
TACFI_LINK = "https://spacewerx.us/accelerate/stratfi-tacfi/#:~:text=21%20Space%20TACFI-,Resources,-PY26.1%20SBIR/STTR"


def badge_divs(badges: list[str]) -> str:
    return "".join(f'<div class="brxe-b1 brxe-block"><div class="brxe-b2 brxe-text-basic '
                   f'afw-v2-funding-opps__icon-text">{badge}</div></div>' for badge in badges)


def grid_row(badges: list[str], title: str, pre: str, opens: str, closes: str, link: str = DSIP_LOGIN) -> str:
    cells = "".join(f'<div class="brxe-d1 brxe-block"><div class="brxe-d2 brxe-text-basic">{d}</div></div>'
                    for d in (pre, opens, closes))
    return (f'<div class="brxe-r1 brxe-block" data-brx-loop-start="r1">{badge_divs(badges)}'
            f'<div class="brxe-t1 brxe-block"><a class="brxe-t2 brxe-text-basic" href="{link}">{title}</a></div>'
            f'{cells}</div><div class="brx-query-trail" data-query-element-id="r1"></div>')


def labelled(badges: list[str], title: str, pre: str, opens: str, closes: str, link: str = DSIP_LOGIN) -> str:
    return (f'<div class="brxe-m1 brxe-block" data-brx-loop-start="m1">{badge_divs(badges)}'
            f'<div class="brxe-m2 brxe-block"><a class="brxe-m3 brxe-text-basic" href="{link}">'
            f'<strong>SOLICITATION</strong>: {title}</a><div class="brxe-m4 brxe-text">'
            f'<p><strong>PRE-RELEASE</strong>: {pre}<br /><strong>OPEN</strong>: {opens}<br />'
            f'<strong>CLOSE</strong>: {closes}</p> </div></div></div>'
            '<div class="brx-query-trail" data-query-element-id="m1"></div>')


def top(site: str = "AFWERX") -> str:
    return ('<html><head><style>.afw-v2-funding-opps__icon-text {color: #fff}</style></head><body>'
            '<h2 class="brxe-heading">Who can apply</h2><p>500 or fewer employees</p>'
            '<h2 class="brxe-heading">Open Funding Opportunities</h2>'
            f'<div class="brxe-text"><p>Discover how your small business can partner with {site}.</p></div>'
            '<div class="brxe-block brx-grid"><div class="brxe-text-basic">Upcoming<br>Solicitations</div>'
            '<div class="brxe-text-basic">Pre-Release</div><div class="brxe-text-basic">Open</div>'
            '<div class="brxe-text-basic">Close</div></div>')


END = ('<script>\nSOLICITATION : DOW SBIR SPECIFIC TOPIC 99.ZZ\n</script>'   # never read as a listing
       '<div class="brxe-block"><div class="brxe-text"><p>Dates subject to change</p>'
       '<p><strong>AF</strong> &#8211; Solicitation includes U.S. Air Force topics<br />'
       '<strong>SF</strong> &#8211; Solicitation includes U.S. Space Force topics</p></div>'
       '<a class="brxe-button" href="https://www.dodsbirsttr.mil/submissions/solicitation-documents/active-solicitations">'
       'View All DoW Active Solicitations</a></div>'
       '<h2>Funding Avenues by Phase of Development</h2><p><strong>KEY DETAILS</strong>: Up to six months</p>'
       '<p>7 Oct 26</p></body></html>')   # a date below the list, outside it


def page(entries: str, site: str = "AFWERX") -> str:
    return top(site) + entries + END


AFWERX_CYCLES = [
    (["AF"], "DOW SBIR SPECIFIC TOPIC 27.BZ &#038; 27.BX Release 1", "7 Oct 26", "28 Oct 26", "25 Nov 26"),
    (["AF", "SF"], "DOW  STTR SPECIFIC TOPIC 27.TZ Release 1", "7 Oct 26", "28 Oct 26", "25 Nov 26"),
    (["SF"], "DOD SBIR SPECIFIC TOPIC 26.BZ Release 2", "N/A", "13 APRIL 26", "13 MAY 26"),
    (["AF / SF"], "STRATFI/TACFI 27.1", "TBD", "TBD", "TBD"),
]
AFWERX_PAGE = page("".join(grid_row(*c) + labelled(*c) for c in AFWERX_CYCLES))

TACFI = ([], "PY26.2 TACFI Notice of Opportunity", "N/A", "5 JUN 26", "Accepting Submissions on a Continuous Basis")
SPACEWERX_PAGE = page(grid_row(*TACFI, link=TACFI_LINK) + labelled(*TACFI, link=TACFI_LINK), site="SpaceWERX")


class Reply:
    def __init__(self, body: str) -> None:
        self.body = body.encode("utf-8")

    def __enter__(self) -> "Reply":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def read(self) -> bytes:
        return self.body


class FakeSite:
    """Answers with one page, after failing `failures` times."""

    def __init__(self, page: str = AFWERX_PAGE, failures: int = 0) -> None:
        self.page = page
        self.failures = failures
        self.requests: list[str] = []

    def __call__(self, request: Any, timeout: float) -> Reply:
        assert timeout >= 10
        self.requests.append(request.full_url)
        if len(self.requests) <= self.failures:
            raise urllib.error.URLError("timed out")
        return Reply(self.page)
