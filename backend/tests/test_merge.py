"""Patient identity resolution.

A false-positive merge shows one patient's data under another's name, which is the
most dangerous failure available in this dataset. These tests weight refusal to
merge at least as heavily as successful merging.
"""

from datetime import datetime, timezone

import pytest

from app.models.fhir import Patient
from app.services.normalize import merge_patients

ANCHOR = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)


def patient(pid, family="Whitfield", given=("Dorothy",), birth="1958-03-12",
            mrn="MRN-48213", gender="female", line="482 Larkspur Lane", city="Springvale"):
    return Patient.model_validate({
        "resourceType": "Patient", "id": pid,
        "name": [{"use": "official", "family": family, "given": list(given)}],
        "birthDate": birth, "gender": gender,
        "identifier": [{"system": "http://centaurihealth.example.org/mrn", "value": mrn}],
        "address": [{"line": [line], "city": city, "state": "OH", "postalCode": "44011"}],
    })


def test_the_bundles_duplicate_pair_is_merged(summary):
    identity = summary.patient.identity
    assert identity.resolution == "merged-probable-duplicate"
    assert {r.id for r in identity.source_records} == {"patient-001", "patient-002"}
    assert len(identity.match_evidence) >= 2


def test_lower_precision_birth_date_is_corroboration_not_conflict(summary):
    """'1958' does not contradict '1958-03-12' — it is the same date, less precisely."""
    assert not [n for n in summary.data_quality.notes if n.section == "patient"]
    assert any("lower precision" in e for e in summary.patient.identity.match_evidence)
    assert summary.patient.birth_date.value.raw == "1958-03-12"
    assert "1958" in summary.patient.birth_date.note


def test_merge_unions_contact_points_rather_than_overwriting(summary):
    """The records hold a home number and a mobile number in different slots.
    Field precedence would silently discard one."""
    by_use = {t.value.use: t for t in summary.patient.telecom}
    assert by_use["home"].value.value == "555-014-2231"
    assert by_use["mobile"].value.value == "555-014-9987"
    assert by_use["home"].sources == ["patient-001"]
    assert by_use["mobile"].sources == ["patient-002"]


def test_both_identifiers_are_retained(summary):
    values = {i.value for i in summary.patient.identifiers}
    assert values == {"MRN-48213", "MRN-48213-A"}


def test_ssn_is_dropped_during_merge(summary):
    assert all("4471" not in i.value for i in summary.patient.identifiers)


def test_us_core_extensions_are_surfaced(summary):
    assert summary.patient.race.value == "White"
    assert summary.patient.ethnicity.value == "Not Hispanic or Latino"


def test_age_is_anchored_to_the_bundle_not_wall_clock(summary):
    """Anchoring to now() would make this value drift and the test flaky."""
    assert summary.patient.age.value == "68 years"


@pytest.mark.parametrize(
    "other,reason",
    [
        (patient("p2", birth="1959", mrn="MRN-48213-A"), "birth dates differ"),
        (patient("p2", family="Hartley", mrn="MRN-99999"), "names differ"),
        (patient("p2", gender="male", mrn="MRN-48213-A"), "gender differs"),
        (patient("p2", line="9 Elm Street", city="Toledo", mrn="MRN-99999"), "addresses differ"),
    ],
)
def test_contradictory_records_are_never_merged(other, reason):
    merged = merge_patients([patient("patient-001", given=("Dorothy", "M")), other], ANCHOR)
    assert merged.duplicates == []
    assert any(reason in r for rejection in merged.rejected for r in rejection.reasons)


def test_thin_records_are_not_merged_on_a_name_alone():
    thin = Patient.model_validate({"resourceType": "Patient", "id": "p2",
                                   "name": [{"family": "Whitfield", "given": ["Dorothy"]}]})
    merged = merge_patients([patient("patient-001"), thin], ANCHOR)
    assert merged.duplicates == []


def test_rejected_matches_are_explained_not_discarded():
    """A second patient who is a different person must not vanish silently."""
    merged = merge_patients([patient("patient-001"), patient("p2", family="Hartley", mrn="MRN-9")], ANCHOR)
    assert merged.rejected and merged.rejected[0].patient_id == "p2"
    assert merged.rejected[0].reasons


def test_street_suffix_abbreviations_are_normalised():
    merged = merge_patients(
        [patient("patient-001", line="482 Larkspur Lane"),
         patient("p2", line="482 Larkspur Ln", birth="1958", mrn="MRN-48213-A")],
        ANCHOR,
    )
    assert [d.id for d in merged.duplicates] == ["p2"]


def test_single_patient_bundle_reports_single_record():
    merged = merge_patients([patient("patient-001")], ANCHOR)
    assert merged.demographics.identity.resolution == "single-record"
    assert merged.duplicates == []


def test_no_patient_at_all():
    assert merge_patients([], ANCHOR) is None


def test_relatives_at_one_address_are_not_merged():
    """Name, gender and address are household facts, not identity. Three of them
    agreeing describes a family, not a person — counting fields without weighting
    them merged a mother and daughter into one patient."""
    mother = patient("mother", birth="1958-03-12", mrn=None)
    daughter = Patient.model_validate({
        "resourceType": "Patient", "id": "daughter", "gender": "female",
        "name": [{"family": "Whitfield", "given": ["Dorothy"]}],
        "address": [{"line": ["482 Larkspur Lane"], "city": "Springvale", "state": "OH", "postalCode": "44011"}],
    })

    merged = merge_patients([mother, daughter], ANCHOR)
    assert merged.duplicates == []
    assert "no identifying field agrees" in merged.rejected[0].reasons[0]


def test_an_agreeing_birth_date_is_enough_to_identify():
    merged = merge_patients(
        [patient("a", birth="1958-03-12", mrn=None), patient("b", birth="1958", mrn=None)], ANCHOR
    )
    assert [d.id for d in merged.duplicates] == ["b"]


def test_a_shared_mrn_root_is_enough_to_identify():
    thin_a = Patient.model_validate({
        "resourceType": "Patient", "id": "a",
        "name": [{"family": "Whitfield", "given": ["Dorothy"]}],
        "identifier": [{"system": "http://centaurihealth.example.org/mrn", "value": "MRN-48213"}],
    })
    thin_b = Patient.model_validate({
        "resourceType": "Patient", "id": "b",
        "name": [{"family": "Whitfield", "given": ["Dorothy"]}],
        "identifier": [{"system": "http://centaurihealth.example.org/mrn", "value": "MRN-48213-A"}],
    })
    merged = merge_patients([thin_a, thin_b], ANCHOR)
    assert [d.id for d in merged.duplicates] == ["b"]


def test_the_bundles_merge_rests_on_two_identity_signals(summary):
    """Regression guard: the real pair must still merge on birth date and MRN root,
    not on the household fields alone."""
    evidence = summary.patient.identity.match_evidence
    assert any("birth dates agree" in e for e in evidence)
    assert any("medical record numbers share a root" in e for e in evidence)
