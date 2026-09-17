"""Status buckets, written against the FHIR value sets rather than the sample."""

import pytest

from app.services.status import (
    Disposition,
    classify_allergy,
    classify_condition,
    classify_encounter,
    classify_medication,
    classify_observation,
)


@pytest.mark.parametrize(
    "clinical,verification,expected",
    [
        ("active", "confirmed", Disposition.CURRENT),
        ("recurrence", "confirmed", Disposition.CURRENT),
        ("inactive", "confirmed", Disposition.HISTORICAL),
        ("resolved", "confirmed", Disposition.HISTORICAL),
        ("inactive", "entered-in-error", Disposition.EXCLUDE),
        # Not present in the bundle; a refuted diagnosis is disproven, not merely old.
        ("active", "refuted", Disposition.EXCLUDE),
    ],
)
def test_condition_buckets(clinical, verification, expected):
    assert classify_condition(clinical, verification).disposition is expected


@pytest.mark.parametrize(
    "status,intent,expected",
    [
        ("active", "order", Disposition.CURRENT),
        ("stopped", "order", Disposition.HISTORICAL),
        ("completed", "order", Disposition.HISTORICAL),
        ("entered-in-error", "order", Disposition.EXCLUDE),
        ("cancelled", "order", Disposition.EXCLUDE),
        ("draft", "order", Disposition.EXCLUDE),
        ("on-hold", "order", Disposition.CURRENT),
        # A proposal is not something the patient is taking.
        ("active", "plan", Disposition.EXCLUDE),
        ("active", "proposal", Disposition.EXCLUDE),
    ],
)
def test_medication_buckets(status, intent, expected):
    assert classify_medication(status, intent).disposition is expected


@pytest.mark.parametrize(
    "status,expected",
    [
        ("final", Disposition.CURRENT),
        ("amended", Disposition.CURRENT),
        ("corrected", Disposition.CURRENT),
        ("preliminary", Disposition.CURRENT),
        ("entered-in-error", Disposition.EXCLUDE),
        ("cancelled", Disposition.EXCLUDE),
        ("registered", Disposition.EXCLUDE),
    ],
)
def test_observation_buckets(status, expected):
    assert classify_observation(status).disposition is expected


@pytest.mark.parametrize(
    "status,expected",
    [
        ("finished", Disposition.HISTORICAL),
        ("in-progress", Disposition.CURRENT),
        ("entered-in-error", Disposition.EXCLUDE),
        ("cancelled", Disposition.EXCLUDE),
        ("planned", Disposition.EXCLUDE),
    ],
)
def test_encounter_buckets(status, expected):
    assert classify_encounter(status).disposition is expected


@pytest.mark.parametrize(
    "clinical,verification,expected",
    [
        ("active", "confirmed", Disposition.CURRENT),
        ("active", "unconfirmed", Disposition.CURRENT),
        ("resolved", "confirmed", Disposition.HISTORICAL),
        ("resolved", "entered-in-error", Disposition.EXCLUDE),
        ("active", "refuted", Disposition.EXCLUDE),
    ],
)
def test_allergy_buckets(clinical, verification, expected):
    assert classify_allergy(clinical, verification).disposition is expected


@pytest.mark.parametrize(
    "classify,args",
    [
        (classify_condition, ("wibble", None)),
        (classify_medication, ("wibble", "order")),
        (classify_observation, ("wibble",)),
    ],
)
def test_unrecognised_status_is_demoted_out_of_the_current_view(classify, args):
    verdict = classify(*args)
    assert verdict.disposition is not Disposition.CURRENT
    assert any(f.code.value == "unrecognised-status" for f in verdict.flags)


@pytest.mark.parametrize("clinical,verification", [("wibble", None), (None, None), (None, "confirmed")])
def test_allergy_fail_safe_inverts(clinical, verification):
    """Everywhere else an unintelligible status withholds the record. For allergies
    it must not: omitting an allergy is the dangerous direction."""
    verdict = classify_allergy(clinical, verification)
    assert verdict.disposition is Disposition.CURRENT
    assert any(f.code.value == "unrecognised-status" for f in verdict.flags)
