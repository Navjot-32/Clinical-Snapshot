"""Every resource in the bundle, and where it is allowed to end up.

This is the safety contract. If a resource moves between buckets, that is either a
deliberate change or a regression, and either way it should be visible in a diff.
"""

import json

import pytest

# resource id -> where it must appear in the summary
EXPECTED = {
    "encounter-001": "encounters",
    "encounter-002": "withheld",              # status entered-in-error
    "condition-001": "problems",
    "condition-002": "withheld",              # verification entered-in-error
    "condition-003": "problems",
    "observation-001": "observations",
    "observation-002": "observations",
    "observation-003": "observations",
    "observation-004": "withheld",            # status entered-in-error, creatinine 14.7
    "medicationrequest-001": "medications.active",
    "medicationrequest-002": "medications.historical",
    "medicationrequest-003": "medications.unverifiedSubject",
    "allergyintolerance-001": "allergies",
    "allergyintolerance-002": "withheld",     # verification entered-in-error
    "allergyintolerance-003": "allergies",    # active but unconfirmed: shown, flagged
}


def locate(summary, resource_id: str) -> str:
    buckets = {
        "problems": summary.problems.items,
        "allergies": summary.allergies.items,
        "encounters": summary.encounters.items,
        "observations": summary.observations.items,
        "medications.active": summary.medications.active,
        "medications.historical": summary.medications.historical,
        "medications.unverifiedSubject": summary.medications.unverified_subject,
    }
    for name, items in buckets.items():
        if any(item.id == resource_id for item in items):
            return name
    if any(note.resource_id == resource_id for note in summary.data_quality.notes):
        return "withheld"
    return "absent"


@pytest.mark.parametrize("resource_id,expected", sorted(EXPECTED.items()))
def test_resource_lands_in_expected_bucket(summary, resource_id, expected):
    assert locate(summary, resource_id) == expected


def test_every_withheld_resource_has_a_stated_reason(summary):
    for note in summary.data_quality.notes:
        assert note.reason, f"{note.resource_id} was withheld without a reason"
        assert note.resource_id, "a note must identify its resource"


def test_no_bundle_resource_disappears_silently(summary, raw_bundle):
    """Patients aside, every resource is either displayed or explained."""
    for entry in raw_bundle["entry"]:
        resource = entry["resource"]
        if resource["resourceType"] == "Patient":
            continue
        assert locate(summary, resource["id"]) != "absent", f"{resource['id']} vanished without a note"
