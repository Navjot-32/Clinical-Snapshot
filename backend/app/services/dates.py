"""FHIR date handling. The single rule: never claim more precision than the source.

A value of "2019" must survive as the year 2019 and render as "2019" — not as
1 January. Ordering still needs a real datetime, so one is derived and kept
internal, never serialised.
"""

import re
from datetime import datetime, timezone
from typing import Optional

from app.models.summary import DatePrecision, PrecisionDate, Recency

# A measurement older than this is marked stale. Chosen so the November 2025
# encounter (~7 months before the bundle) reads as current while the 2020
# HbA1c does not.
STALE_AFTER_DAYS = 365

_YEAR = re.compile(r"^(\d{4})$")
_MONTH = re.compile(r"^(\d{4})-(\d{2})$")
_DAY = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_INSTANT = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?")

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def parse_fhir_date(raw: Optional[str]) -> Optional[PrecisionDate]:
    if raw is None:
        return None

    value = raw.strip()
    if not value:
        return None

    match = _YEAR.match(value)
    if match:
        year = int(match.group(1))
        stamp = _safe_datetime(year, 1, 1)
        if stamp is None:
            return _unknown(raw)
        return PrecisionDate(raw=raw, precision=DatePrecision.YEAR, display=str(year), sort_key=stamp)

    match = _MONTH.match(value)
    if match:
        year, month = int(match.group(1)), int(match.group(2))
        stamp = _safe_datetime(year, month, 1)
        if stamp is None:
            return _unknown(raw)
        return PrecisionDate(
            raw=raw, precision=DatePrecision.MONTH,
            display=f"{_month_name(month)} {year}", sort_key=stamp,
        )

    match = _DAY.match(value)
    if match:
        year, month, day = (int(g) for g in match.groups())
        stamp = _safe_datetime(year, month, day)
        if stamp is None:
            return _unknown(raw)
        return PrecisionDate(
            raw=raw, precision=DatePrecision.DAY,
            display=f"{day} {_month_name(month)} {year}", sort_key=stamp,
        )

    match = _INSTANT.match(value)
    if match:
        year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
        hour, minute = int(match.group(4)), int(match.group(5))
        second = int(match.group(6) or 0)
        stamp = _safe_datetime(year, month, day, hour, minute, second)
        if stamp is None:
            return _unknown(raw)

        # Exactly midnight is upstream padding of a plain date far more often than
        # it is a real clinical timestamp. Demoted to day, but deliberately no
        # further: demoting 1 January would destroy genuine New Year's Day events.
        if (hour, minute, second) == (0, 0, 0):
            return PrecisionDate(
                raw=raw, precision=DatePrecision.DAY,
                display=f"{day} {_month_name(month)} {year}", sort_key=stamp,
            )

        return PrecisionDate(
            raw=raw, precision=DatePrecision.INSTANT,
            display=f"{day} {_month_name(month)} {year}, {hour:02d}:{minute:02d} UTC",
            sort_key=stamp,
        )

    return _unknown(raw)


def _unknown(raw: str) -> PrecisionDate:
    """A value we cannot interpret is shown verbatim and never sorted."""
    return PrecisionDate(raw=raw, precision=DatePrecision.UNKNOWN, display=raw, sort_key=None)


def compute_recency(
    date: Optional[PrecisionDate],
    anchor: Optional[datetime],
    mark_stale: bool = False,
) -> Optional[Recency]:
    """Age of a value relative to the bundle timestamp.

    `mark_stale` is opt-in because staleness only means something for measurements.
    An onset or recorded date is a historical fact, not a reading that decays —
    flagging a 2021 hypertension onset as stale would wrongly imply the diagnosis
    is in doubt.
    """
    if date is None or date.sort_key is None or anchor is None:
        return None

    days = (anchor - date.sort_key).days
    if days < 0:
        return Recency(days_ago=days, display="dated after the bundle timestamp", is_stale=False)

    return Recency(
        days_ago=days,
        display=_relative(days, date.precision),
        is_stale=mark_stale and days > STALE_AFTER_DAYS,
    )


def _relative(days: int, precision: DatePrecision) -> str:
    # A year-only source cannot support "8 months ago" — say what it can support.
    if precision is DatePrecision.YEAR:
        years = days // 365
        return "this year" if years < 1 else f"about {years} year{'s' if years > 1 else ''} ago"
    if days == 0:
        return "today"
    if days < 31:
        return f"{days} day{'s' if days > 1 else ''} ago"
    if days < 365:
        months = days // 30
        return f"{months} month{'s' if months > 1 else ''} ago"
    years = days // 365
    return f"{years} year{'s' if years > 1 else ''} ago"


def _month_name(month: int) -> str:
    return _MONTHS[month - 1] if 1 <= month <= 12 else str(month)


def _safe_datetime(year: int, month: int, day: int, hour: int = 0, minute: int = 0, second: int = 0) -> Optional[datetime]:
    try:
        return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
    except ValueError:
        return None
