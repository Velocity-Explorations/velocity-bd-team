"""The fit score (PRO-487): how well a call suits Velocity, 0 to 100, from the team's rating of each tag, keyword and
NAICS code. The ratings come from the Call Fit Ratings page (run.py --load-fit-ratings) and live in the ledger, never in
this repo, which is public.

    fit = score_call(call, tags_by_source, main_work_by_judge, ratings)   # None until a judge has named the main work

Each part is worth what its rating is worth (VALUES), weighted by WEIGHTS, so main work counts most. Anything nobody
rated counts as neutral, and a call with nothing but neutral ratings scores 50. A Never rules a call out (score 0) only
on its main work, its type or its NAICS code, because a Never on one work tag among several would rule out calls the team
pursues: the judges tag every kind of work a call touches. On what the judges name, it takes all of them to agree.
"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from review.tags import tag_list

VALUES = {"core": 1.0, "good": 0.75, "neutral": 0.5, "poor": 0.25, "never": 0.0}
WEIGHTS = {"work": 0.45, "customer": 0.15, "type": 0.15, "naics": 0.10, "keyword": 0.10, "access": 0.05}
NEUTRAL = "neutral"
NEVER = "never"
STRONG = 70
POSSIBLE = 50
RULED_OUT = "ruled out"
BANDS = ("strong", "possible", "weak", RULED_OUT)
SECTOR_RANGES = ("31-33", "44-45", "48-49")   # NAICS sectors that span several first-two-digit codes


@dataclass(frozen=True)
class Fit:
    score: int
    band: str
    why: list[str]


def slug(text: str) -> str:
    """A name as the page keys it: "AI and ML" is ai-and-ml."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def sector_of(code: str) -> str:
    """The NAICS sector of a code: 236220 is 23, 325120 is 31-33."""
    two = code[:2]
    for name in SECTOR_RANGES:
        low, high = name.split("-")
        if low <= two <= high:
            return name
    return two


def band_of(score: int) -> str:
    return "strong" if score >= STRONG else "possible" if score >= POSSIBLE else "weak"


def _ruled_out(what: str) -> Fit:
    return Fit(0, RULED_OUT, [f"Ruled out: {what} is rated never"])


def _judged(names: Sequence[str], group: str, ratings: Mapping[str, str]) -> tuple[float, bool]:
    """(value, ruled out) of what the judges named: the lower rating, with a Never counting as poor unless all are Never."""
    rated = [ratings.get(f"{group}.{slug(name)}", NEUTRAL) for name in names]
    if all(rating == NEVER for rating in rated):
        return 0.0, True
    return min(VALUES["poor"] if rating == NEVER else VALUES[rating] for rating in rated), False


def _best(names: Sequence[str], group: str, ratings: Mapping[str, str]) -> tuple[float, str | None, str]:
    """(value, name, rating) of the best-rated of these tags; neutral when there are none."""
    best = (VALUES[NEUTRAL], None, NEUTRAL)
    for position, name in enumerate(names):
        rating = ratings.get(f"{group}.{slug(name)}", NEUTRAL)
        if position == 0 or VALUES[rating] > best[0]:
            best = (VALUES[rating], name, rating)
    return best


def _keywords(call: Mapping[str, Any], ratings: Mapping[str, str]) -> tuple[float, list[str]]:
    """The mean value of the rated keywords that stand as whole words in the call. The filter matches inside words, so
    "ai" also finds "available"; those matches count for nothing here. Neutral keywords add nothing either way."""
    try:
        matched = json.loads(call.get("matched_keywords") or "[]") or []
    except (TypeError, ValueError):
        matched = []
    text = f"{call.get('title') or ''} {call.get('description') or ''}".lower()
    counted = []
    for word in matched:
        rating = ratings.get(f"keyword.{slug(str(word))}", NEUTRAL)
        if rating != NEUTRAL and re.search(rf"(?<![a-z0-9]){re.escape(str(word).lower())}(?![a-z0-9])", text):
            counted.append((str(word), rating))
    if not counted:
        return VALUES[NEUTRAL], []
    return sum(VALUES[rating] for _, rating in counted) / len(counted), [f"Keyword {word}: {rating}" for word, rating in counted]


def score_call(call: Mapping[str, Any], tags_by_source: Mapping[str, Sequence[str]], main_work: Mapping[str, str | None],
               ratings: Mapping[str, str]) -> Fit | None:
    """The call's fit, or None while no judge has named its main work."""
    named = list(dict.fromkeys(name for name in main_work.values() if name))
    if not named:
        return None
    work, work_out = _judged(named, "work", ratings)
    if work_out:
        return _ruled_out(f"main work {' and '.join(named)}")
    why = [f"Main work {named[0]}: {ratings.get(f'work.{slug(named[0])}', NEUTRAL)}" if len(named) == 1
           else f"Main work {' or '.join(named)}: judges differ"]

    code = str(call.get("naics_code") or "").strip()
    naics = NEUTRAL
    if code:
        naics = ratings.get(f"naics.{code}") or ratings.get(f"naics-sector.{sector_of(code)}") or NEUTRAL
        if naics == NEVER:
            return _ruled_out(f"NAICS {code}")

    tags = tag_list()
    by_group: dict[str, dict[str, list[str]]] = {}
    for source, names in tags_by_source.items():
        for name in names:
            group = tags.group_of(name)
            if group:
                by_group.setdefault(group, {}).setdefault(source, []).append(name)

    types = by_group.get("type", {})
    picked = types.get("rule") or [names[0] for source, names in types.items() if source != "rule"]
    kind = VALUES[NEUTRAL]
    if picked:
        kind, type_out = _judged(list(dict.fromkeys(picked)), "type", ratings)
        if type_out:
            return _ruled_out(f"type {picked[0]}")
        rating = ratings.get(f"type.{slug(picked[0])}", NEUTRAL)
        if len(set(picked)) == 1 and rating != NEUTRAL:
            why.append(f"Type {picked[0]}: {rating}")
    notice = ratings.get(f"notice.{slug(str(call.get('type') or ''))}", NEUTRAL)
    if notice != NEUTRAL:
        kind = (kind + VALUES[notice]) / 2
        why.append(f"Notice {call.get('type')}: {notice}")

    def tagged(group: str) -> list[str]:
        return list(dict.fromkeys(name for names in by_group.get(group, {}).values() for name in names))

    customer, customer_name, customer_rating = _best(tagged("customer"), "customer", ratings)
    if customer_rating != NEUTRAL:
        why.append(f"Customer {customer_name}: {customer_rating}")
    access, access_name, access_rating = _best(tagged("access"), "access", ratings)
    if access_rating != NEUTRAL:
        why.append(f"Access {access_name}: {access_rating}")
    if naics != NEUTRAL:
        why.append(f"NAICS {code}: {naics}")
    keyword, keyword_why = _keywords(call, ratings)
    why += keyword_why

    total = (WEIGHTS["work"] * work + WEIGHTS["customer"] * customer + WEIGHTS["type"] * kind
             + WEIGHTS["naics"] * VALUES[naics] + WEIGHTS["keyword"] * keyword + WEIGHTS["access"] * access)
    score = int(100 * total + 0.5 + 1e-9)
    return Fit(score, band_of(score), why)
