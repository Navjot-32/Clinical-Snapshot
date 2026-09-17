"""Patient identity resolution.

The bundle carries two Patient resources for what appears to be one person. This
module decides whether they are the same person and, if so, combines them by union
rather than precedence — taking the more complete record as the base but never
letting it overwrite data only the other record holds.

A lower-precision value that agrees is treated as corroboration, not conflict:
a birth date of "1958" does not contradict "1958-03-12".
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set

from app.models.fhir import Address, Patient
from app.models.summary import (
    ContactPoint,
    Demographics,
    IdentityResolution,
    PrecisionDate,
    SourceRecord,
    Sourced,
)
from app.services.dates import parse_fhir_date

SSN_SYSTEM = "http://hl7.org/fhir/sid/us-ssn"
MRN_SYSTEM = "http://centaurihealth.example.org/mrn"

RACE_EXT = "http://hl7.org/fhir/us/core/StructureDefinition/us-core-race"
ETHNICITY_EXT = "http://hl7.org/fhir/us/core/StructureDefinition/us-core-ethnicity"

_STREET_SUFFIXES = {
    "street": "st", "st": "st", "road": "rd", "rd": "rd", "lane": "ln", "ln": "ln",
    "avenue": "ave", "ave": "ave", "drive": "dr", "dr": "dr", "court": "ct", "ct": "ct",
    "boulevard": "blvd", "blvd": "blvd", "place": "pl", "pl": "pl",
}


@dataclass
class MatchAssessment:
    matched: bool
    evidence: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    # Fields that identify a person rather than a household. Name, gender and
    # address are all shared by relatives at one address; birth date and medical
    # record number are not.
    identity_signals: int = 0


@dataclass
class RejectedMatch:
    patient_id: str
    reasons: List[str]


@dataclass
class MergedPatient:
    primary: Patient
    duplicates: List[Patient] = field(default_factory=list)
    member_ids: Set[str] = field(default_factory=set)
    demographics: Optional[Demographics] = None
    # Patient records judged to be a different person. Recorded rather than
    # dropped: silently discarding a Patient resource hides the decision.
    rejected: List[RejectedMatch] = field(default_factory=list)


def merge_patients(patients: List[Patient], anchor: Optional[datetime]) -> Optional[MergedPatient]:
    if not patients:
        return None

    primary = max(patients, key=_completeness)
    others = [p for p in patients if p.id != primary.id]

    duplicates: List[Patient] = []
    rejected: List[RejectedMatch] = []
    evidence: List[str] = []

    for candidate in others:
        assessment = _compare(primary, candidate)
        if assessment.matched:
            duplicates.append(candidate)
            evidence.extend(assessment.evidence)
        else:
            reasons = assessment.conflicts or [_rejection_reason(assessment)]
            rejected.append(RejectedMatch(patient_id=candidate.id, reasons=reasons))

    merged = MergedPatient(
        primary=primary,
        duplicates=duplicates,
        member_ids={primary.id} | {d.id for d in duplicates},
        rejected=rejected,
    )
    merged.demographics = _build_demographics(primary, duplicates, evidence, anchor)
    return merged


def _rejection_reason(assessment: MatchAssessment) -> str:
    if assessment.identity_signals == 0:
        return (
            "no identifying field agrees (birth date or medical record number); "
            "name, gender and address are shared by relatives at one address"
        )
    return f"only {len(assessment.evidence)} corroborating field(s); at least 2 required to merge"


def _completeness(patient: Patient) -> int:
    score = 0
    for value in (patient.identifier, patient.name, patient.telecom, patient.address, patient.extension):
        score += len(value)
    if patient.birthDate:
        score += len(patient.birthDate)  # a full date is worth more than a bare year
    if patient.gender:
        score += 1
    return score


def _compare(a: Patient, b: Patient) -> MatchAssessment:
    """Decide whether two Patient records describe the same person."""
    evidence: List[str] = []
    conflicts: List[str] = []
    identity_signals = 0

    name_a, name_b = _name_key(a), _name_key(b)
    if name_a and name_b:
        if name_a == name_b:
            evidence.append(f"name matches ({_display_name(a)})")
        elif _family(a) == _family(b) and _given_overlap(a, b):
            evidence.append(f"family name and at least one given name match ({_display_name(a)})")
        else:
            conflicts.append(f"names differ: '{_display_name(a)}' vs '{_display_name(b)}'")

    date_a, date_b = parse_fhir_date(a.birthDate), parse_fhir_date(b.birthDate)
    if date_a and date_b:
        if _dates_consistent(date_a, date_b):
            identity_signals += 1
            if date_a.precision != date_b.precision:
                evidence.append(
                    f"birth dates agree at the lower precision available "
                    f"('{date_b.raw}' is consistent with '{date_a.raw}')"
                )
            else:
                evidence.append(f"birth dates match ({date_a.display})")
        else:
            conflicts.append(f"birth dates differ: '{date_a.raw}' vs '{date_b.raw}'")

    if a.gender and b.gender:
        if a.gender == b.gender:
            evidence.append(f"gender matches ({a.gender})")
        else:
            conflicts.append(f"gender differs: '{a.gender}' vs '{b.gender}'")

    addr_a, addr_b = _address_key(a), _address_key(b)
    if addr_a and addr_b:
        if addr_a == addr_b:
            evidence.append("address matches after normalising abbreviations")
        else:
            conflicts.append("addresses differ")

    mrn_a, mrn_b = _mrn(a), _mrn(b)
    if mrn_a and mrn_b and mrn_a != mrn_b and _same_mrn_root(mrn_a, mrn_b):
        identity_signals += 1
        evidence.append(f"medical record numbers share a root ('{mrn_a}' and '{mrn_b}')")

    # At least one field that identifies a *person* must agree. Counting fields
    # without weighting them merges relatives who share a surname and an address:
    # name, gender and address together are three agreements and still describe a
    # household rather than an individual.
    #
    # A contradiction blocks the merge outright, so a merged identity never carries
    # conflicts — they are reported against the rejected record instead.
    matched = identity_signals >= 1 and len(evidence) >= 2 and not conflicts
    return MatchAssessment(matched=matched, evidence=evidence, conflicts=conflicts, identity_signals=identity_signals)


def _dates_consistent(a: PrecisionDate, b: PrecisionDate) -> bool:
    if a.sort_key is None or b.sort_key is None:
        return a.raw == b.raw
    order = ["year", "month", "day", "instant"]
    coarser = order[min(order.index(a.precision.value), order.index(b.precision.value))]
    if coarser == "year":
        return a.sort_key.year == b.sort_key.year
    if coarser == "month":
        return (a.sort_key.year, a.sort_key.month) == (b.sort_key.year, b.sort_key.month)
    return a.sort_key.date() == b.sort_key.date()


def _family(p: Patient) -> str:
    return (p.name[0].family or "").strip().lower() if p.name else ""


def _given_overlap(a: Patient, b: Patient) -> bool:
    ga = {g.strip().lower() for g in (a.name[0].given if a.name else [])}
    gb = {g.strip().lower() for g in (b.name[0].given if b.name else [])}
    return bool(ga & gb)


def _name_key(p: Patient) -> str:
    if not p.name:
        return ""
    given = " ".join(g.strip().lower() for g in p.name[0].given)
    return f"{_family(p)}|{given}".strip("|")


def _display_name(p: Patient) -> str:
    if not p.name:
        return "(unnamed)"
    return " ".join([*p.name[0].given, p.name[0].family or ""]).strip()


def _address_key(p: Patient) -> str:
    if not p.address:
        return ""
    return _normalise_address(p.address[0])


def _normalise_address(address: Address) -> str:
    parts = []
    for line in address.line:
        tokens = re.findall(r"[a-z0-9]+", line.lower())
        parts.extend(_STREET_SUFFIXES.get(t, t) for t in tokens)
    for extra in (address.city, address.state, address.postalCode):
        if extra:
            parts.extend(re.findall(r"[a-z0-9]+", extra.lower()))
    return " ".join(parts)


def _mrn(p: Patient) -> Optional[str]:
    for identifier in p.identifier:
        if identifier.system == MRN_SYSTEM:
            return identifier.value
    return None


def _same_mrn_root(a: str, b: str) -> bool:
    root = re.compile(r"^([A-Za-z0-9]+?-?\d+)")
    ma, mb = root.match(a), root.match(b)
    return bool(ma and mb and ma.group(1) == mb.group(1))


def _build_demographics(
    primary: Patient,
    duplicates: List[Patient],
    evidence: List[str],
    anchor: Optional[datetime],
) -> Demographics:
    records = [primary, *duplicates]

    source_records = [SourceRecord(id=primary.id, mrn=_mrn(primary), role="primary")]
    source_records += [SourceRecord(id=d.id, mrn=_mrn(d), role="merged-duplicate") for d in duplicates]

    identity = IdentityResolution(
        resolution="merged-probable-duplicate" if duplicates else "single-record",
        source_records=source_records,
        match_evidence=evidence,
    )

    demographics = Demographics(identity=identity)

    name_sources = [r.id for r in records if _display_name(r) == _display_name(primary)]
    demographics.name = Sourced(value=_display_name(primary), sources=name_sources)

    birth = _best_birth_date(records)
    if birth:
        date, sources, note = birth
        demographics.birth_date = Sourced(value=date, sources=sources, note=note)
        age = _age(date, anchor)
        if age:
            demographics.age = Sourced(value=age, sources=sources)

    genders = {r.gender for r in records if r.gender}
    if genders:
        value = primary.gender or next(iter(genders))
        demographics.gender = Sourced(value=value, sources=[r.id for r in records if r.gender == value])

    demographics.telecom = _union_telecom(records)
    demographics.identifiers = _union_identifiers(records)

    address_record = max(records, key=lambda r: len(r.address[0].model_dump_json()) if r.address else 0)
    if address_record.address:
        rendered = _render_address(address_record.address[0])
        sources = [r.id for r in records if r.address and _normalise_address(r.address[0]) == _normalise_address(address_record.address[0])]
        demographics.address = Sourced(value=rendered, sources=sources)

    race = _us_core_text(records, RACE_EXT)
    if race:
        demographics.race = race
    ethnicity = _us_core_text(records, ETHNICITY_EXT)
    if ethnicity:
        demographics.ethnicity = ethnicity

    return demographics


def _best_birth_date(records: List[Patient]):
    order = {"instant": 3, "day": 2, "month": 1, "year": 0, "unknown": -1}
    parsed = [(r.id, parse_fhir_date(r.birthDate)) for r in records if r.birthDate]
    parsed = [(rid, d) for rid, d in parsed if d]
    if not parsed:
        return None

    rid, best = max(parsed, key=lambda item: order.get(item[1].precision.value, -1))
    sources = [rid]
    note = None

    lesser = [(other_id, d) for other_id, d in parsed if other_id != rid]
    for other_id, other in lesser:
        if other.precision != best.precision:
            note = f"{other_id} records '{other.raw}', consistent at lower precision"
        sources.append(other_id)

    return best, sources, note


def _age(date: PrecisionDate, anchor: Optional[datetime]) -> Optional[str]:
    if date.sort_key is None or anchor is None:
        return None
    years = anchor.year - date.sort_key.year
    if (anchor.month, anchor.day) < (date.sort_key.month, date.sort_key.day):
        years -= 1
    if date.precision.value == "year":
        return f"about {years} years"
    return f"{years} years"


def _union_telecom(records: List[Patient]) -> List[Sourced[ContactPoint]]:
    seen: Dict[tuple, Sourced[ContactPoint]] = {}
    for record in records:
        for contact in record.telecom:
            if not contact.value:
                continue
            key = (contact.system, contact.use, contact.value)
            if key in seen:
                seen[key].sources.append(record.id)
            else:
                seen[key] = Sourced(
                    value=ContactPoint(system=contact.system, use=contact.use, value=contact.value),
                    sources=[record.id],
                )
    return list(seen.values())


def _union_identifiers(records: List[Patient]) -> List[Sourced[str]]:
    seen: Dict[str, Sourced[str]] = {}
    for record in records:
        for identifier in record.identifier:
            # The SSN is dropped here and has no field in the response at all.
            if identifier.system == SSN_SYSTEM or not identifier.value:
                continue
            if identifier.value in seen:
                seen[identifier.value].sources.append(record.id)
            else:
                seen[identifier.value] = Sourced(value=identifier.value, sources=[record.id])
    return list(seen.values())


def _render_address(address: Address) -> str:
    line = ", ".join(address.line)
    tail = " ".join(x for x in (address.city, address.state, address.postalCode) if x)
    return ", ".join(x for x in (line, tail, address.country) if x)


def _us_core_text(records: List[Patient], url: str) -> Optional[Sourced[str]]:
    for record in records:
        for extension in record.extension:
            if extension.url != url:
                continue
            for inner in extension.extension:
                if inner.url == "text" and inner.valueString:
                    return Sourced(value=inner.valueString, sources=[record.id])
            for inner in extension.extension:
                if inner.url == "ombCategory" and inner.valueCoding and inner.valueCoding.display:
                    return Sourced(value=inner.valueCoding.display, sources=[record.id])
    return None
