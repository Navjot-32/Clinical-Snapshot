"""Degrade, don't crash. Production data of uncertain provenance means one bad
resource must never take down the summary."""

import pytest

from app.services.bundle_loader import load_bundle
from app.services.summary_builder import build_summary


def test_malformed_resource_is_dropped_and_reported(bundle_file, raw_bundle):
    payload = dict(raw_bundle)
    payload["entry"] = [dict(e) for e in raw_bundle["entry"]]
    payload["entry"].append({"resource": {"resourceType": "Observation", "id": "bad", "valueQuantity": {"value": "abc"}}})

    loaded = load_bundle(bundle_file(payload))
    assert any(f.resource_id == "bad" for f in loaded.failures)
    assert len(loaded.observations) == 4  # the good ones survive

    summary = build_summary(loaded)
    assert any(n.resource_id == "bad" for n in summary.data_quality.notes)


def test_summary_still_builds_when_many_resources_are_broken(bundle_file, raw_bundle):
    payload = {"resourceType": "Bundle", "timestamp": raw_bundle["timestamp"], "entry": [
        raw_bundle["entry"][0],                                   # patient-001, intact
        {"resource": {"resourceType": "Condition"}},              # no id
        {"resource": {"resourceType": "Nonsense", "id": "x"}},    # unknown type
        {"fullUrl": "urn:uuid:nothing"},                          # no resource
        {"resource": {"resourceType": "Observation", "id": "o", "component": "not-a-list"}},
    ]}
    summary = build_summary(load_bundle(bundle_file(payload)))
    assert summary.patient.name.value == "Dorothy M Whitfield"
    assert summary.data_quality.unparsed_total == 4


def test_empty_bundle_reports_none_in_source_not_a_clinical_claim(bundle_file):
    """An empty allergies section must not be readable as 'no known allergies'."""
    summary = build_summary(load_bundle(bundle_file({"resourceType": "Bundle", "entry": []})))
    assert summary.patient.identity.resolution == "no-patient-record"


def test_patient_with_no_clinical_resources(bundle_file, raw_bundle):
    payload = {"resourceType": "Bundle", "timestamp": raw_bundle["timestamp"], "entry": [raw_bundle["entry"][0]]}
    summary = build_summary(load_bundle(bundle_file(payload)))
    for section in (summary.problems, summary.allergies, summary.encounters, summary.observations):
        assert section.state.value == "none-in-source"
    assert summary.medications.state.value == "none-in-source"


def test_all_withheld_is_distinguishable_from_none_in_source(bundle_file, raw_bundle):
    """The safety-critical distinction: records existed but none are displayable."""
    entries = [raw_bundle["entry"][0]]
    entries += [e for e in raw_bundle["entry"] if e["resource"]["resourceType"] == "AllergyIntolerance"
                and e["resource"]["id"] == "allergyintolerance-002"]
    summary = build_summary(load_bundle(bundle_file({"resourceType": "Bundle", "timestamp": raw_bundle["timestamp"], "entry": entries})))
    assert summary.allergies.state.value == "all-withheld"
    assert summary.allergies.items == []
    assert summary.allergies.withheld_count == 1


def test_unreadable_file_does_not_raise(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    loaded = load_bundle(bad)
    assert loaded.failures
    assert build_summary(loaded) is not None


def test_missing_file_does_not_raise(tmp_path):
    loaded = load_bundle(tmp_path / "nope.json")
    assert loaded.failures
    assert build_summary(loaded) is not None
