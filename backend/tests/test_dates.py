"""Date precision. The rule under test: never claim more precision than the source."""

from datetime import datetime, timezone

import pytest

from app.services.dates import compute_recency, parse_fhir_date

ANCHOR = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "raw,precision,display",
    [
        ("2019", "year", "2019"),
        ("1958", "year", "1958"),
        ("2019-06", "month", "Jun 2019"),
        ("1958-03-12", "day", "12 Mar 1958"),
        ("2025-11-04T14:15:00Z", "instant", "4 Nov 2025, 14:15 UTC"),
        # Exact midnight is upstream padding of a date, not a real clinical time.
        ("2021-06-02T00:00:00Z", "day", "2 Jun 2021"),
        # Deliberately NOT demoted to year: a real 1 January event must keep its day.
        ("2018-01-01T00:00:00Z", "day", "1 Jan 2018"),
    ],
)
def test_precision_is_preserved(raw, precision, display):
    parsed = parse_fhir_date(raw)
    assert parsed.precision.value == precision
    assert parsed.display == display
    assert parsed.raw == raw


@pytest.mark.parametrize("raw", ["2019-13-45", "2021-02-30", "2019-00-01", "garbage", "not-a-date"])
def test_impossible_dates_fall_back_to_unknown(raw):
    """A date that cannot exist must not be rendered as though it does."""
    parsed = parse_fhir_date(raw)
    assert parsed.precision.value == "unknown"
    assert parsed.display == raw
    assert parsed.sort_key is None


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_absent_dates_are_none(raw):
    assert parse_fhir_date(raw) is None


def test_staleness_is_opt_in():
    """Staleness applies to measurements, not to historical facts. Flagging a 2021
    onset as stale would wrongly imply the diagnosis itself is in doubt."""
    old = parse_fhir_date("2020")
    assert compute_recency(old, ANCHOR, mark_stale=True).is_stale is True
    assert compute_recency(old, ANCHOR, mark_stale=False).is_stale is False


def test_recent_measurement_is_not_stale():
    recent = parse_fhir_date("2025-11-04T14:15:00Z")
    assert compute_recency(recent, ANCHOR, mark_stale=True).is_stale is False


def test_year_only_recency_does_not_overstate_precision():
    """A source that said '2020' cannot support '8 months ago'."""
    assert "about" in compute_recency(parse_fhir_date("2020"), ANCHOR).display


def test_future_dates_are_reported_not_negative():
    future = compute_recency(parse_fhir_date("2027-01-01"), ANCHOR)
    assert future.is_stale is False
    assert "after the bundle" in future.display


def test_recency_without_anchor_is_none():
    assert compute_recency(parse_fhir_date("2020"), None) is None
