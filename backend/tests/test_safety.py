"""Things that must never appear in the response, whatever else changes."""

import json

import pytest


@pytest.fixture(scope="module")
def payload(summary) -> str:
    return json.dumps(summary.model_dump(by_alias=True), default=str)


def test_erroneous_creatinine_value_is_absent(payload):
    """observation-004 is marked entered-in-error. 14.7 mg/dL is a critical-looking
    value that must not reach a clinician, not even inside a data-quality note."""
    assert "14.7" not in payload
    assert "Creatinine" not in payload


def test_ssn_never_leaves_the_backend(payload):
    assert "4471" not in payload
    assert "us-ssn" not in payload


def test_retracted_records_are_absent(payload):
    assert "Latex" not in payload        # allergyintolerance-002, entered-in-error
    assert "asthma" not in payload.lower()  # condition-002, entered-in-error


def test_internal_sort_key_is_never_serialised(payload):
    assert "sortKey" not in payload
    assert "sort_key" not in payload


def test_year_only_dates_are_not_expanded(payload, summary):
    """A source that said '2020' must not render as 1 January 2020."""
    a1c = next(o for o in summary.observations.items if o.concept.code == "4548-4")
    assert a1c.effective.raw == "2020"
    assert a1c.effective.display == "2020"
    assert a1c.effective.precision.value == "year"


def test_unmapped_codes_are_not_given_invented_names(summary):
    for item in summary.problems.items + summary.allergies.items:
        if not item.concept.has_display:
            assert item.concept.display is None
            assert item.concept.code
            assert any(f.code.value == "unmapped-code" for f in item.flags)


def test_blood_pressure_is_not_transposed(summary):
    bp = next(o for o in summary.observations.items if o.value and "/" in o.value.display)
    assert bp.value.display == "138/88 mmHg"
    systolic, diastolic = bp.value.components[0], bp.value.components[1]
    assert "Systolic" in systolic.label.display
    assert "Diastolic" in diastolic.label.display


def test_unconfirmed_allergy_is_shown_not_hidden(summary):
    allergy = next(a for a in summary.allergies.items if a.id == "allergyintolerance-003")
    assert any(f.code.value == "unconfirmed" for f in allergy.flags)
    assert any(f.code.value == "unmapped-code" for f in allergy.flags)


def test_duplicate_subject_medication_is_segregated(summary):
    assert [m.id for m in summary.medications.unverified_subject] == ["medicationrequest-003"]
    assert "medicationrequest-003" not in [m.id for m in summary.medications.active]
    flagged = summary.medications.unverified_subject[0]
    assert any(f.code.value == "unverified-subject" for f in flagged.flags)
