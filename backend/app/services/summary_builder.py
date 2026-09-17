"""Assembles the patient summary from normalised resources.

Every section reports why it looks the way it does. An empty section distinguishes
"the bundle held nothing" from "everything was withheld", because a clinician reads
the first as a clinical fact and the second as a data problem.

All five sections run the same screen — does the subject resolve to this patient,
and does the status permit display — before any type-specific mapping. Keeping that
in one place means a section cannot silently skip it.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, List, Optional, Tuple

from app.core.logging import log_summary_built, log_withheld
from app.models.fhir import CodeableConcept, Quantity, Reference
from app.models.summary import (
    Allergy,
    CodedConcept,
    DataQuality,
    DataQualityNote,
    Demographics,
    EncounterSummary,
    Flag,
    FlagCode,
    IdentityResolution,
    Medication,
    MedicationSection,
    ObservationComponentValue,
    ObservationSummary,
    ObservationValue,
    PatientSummary,
    PrecisionDate,
    Problem,
    Section,
    SectionState,
)
from app.services.bundle_loader import LoadedBundle
from app.services.dates import compute_recency, parse_fhir_date
from app.services.normalize import merge_patients
from app.services.status import (
    Disposition,
    StatusVerdict,
    classify_allergy,
    classify_condition,
    classify_encounter,
    classify_medication,
    classify_observation,
)
from app.services.terminology import build_coded_concept, status_code

VITAL_SIGNS_CATEGORY = "vital-signs"

UNRESOLVED_SUBJECT = {"missing", "foreign"}


class Recorder:
    """Collects data-quality notes and logs every one of them.

    The UI panel and the log stream are fed from the same call so they cannot drift.
    Notes carry the record and the rule, never the withheld value.
    """

    def __init__(self) -> None:
        self.notes: List[DataQualityNote] = []

    def withhold(self, resource_type: str, resource_id: str, reason: str, section: Optional[str] = None) -> None:
        self.notes.append(DataQualityNote(resource_type=resource_type, resource_id=resource_id, reason=reason, section=section))
        log_withheld(resource_type, resource_id, reason, section)


@dataclass
class Screened:
    """Resources that survived screening, plus the counts each section needs."""

    kept: List[Tuple[Any, StatusVerdict, str]] = field(default_factory=list)
    total: int = 0
    withheld: int = 0

    def state(self, shown: int) -> SectionState:
        return _section_state(self.total, shown, self.withheld)


def _screen(
    resources: List[Any],
    resource_type: str,
    subject_of: Callable[[Any], Optional[Reference]],
    classify: Callable[[Any], StatusVerdict],
    section: str,
    merged: Any,
    recorder: Recorder,
    subject_label: str = "subject",
) -> Screened:
    result = Screened()

    for resource in resources:
        placement = _subject_of(subject_of(resource), merged)
        if placement in UNRESOLVED_SUBJECT:
            result.withheld += 1
            reason = f"{subject_label} reference does not resolve to this patient ({placement})"
            recorder.withhold(resource_type, resource.id, reason, section)
            continue

        result.total += 1
        verdict = classify(resource)
        if verdict.disposition is Disposition.EXCLUDE:
            result.withheld += 1
            recorder.withhold(resource_type, resource.id, verdict.reason or "withheld", section)
            continue

        result.kept.append((resource, verdict, placement))

    return result


def build_summary(loaded: LoadedBundle) -> PatientSummary:
    anchor_date = parse_fhir_date(loaded.timestamp) or PrecisionDate(
        raw="unknown", precision="unknown", display="date unknown"
    )
    anchor = anchor_date.sort_key

    recorder = Recorder()

    for failure in loaded.failures:
        recorder.withhold(failure.resource_type or "unknown", failure.resource_id or "unknown", failure.reason)

    merged = merge_patients(loaded.patients, anchor)
    if merged is None:
        recorder.withhold("Patient", "none", "bundle contained no Patient resource")
        return PatientSummary(
            as_of=anchor_date,
            patient=Demographics(identity=IdentityResolution(resolution="no-patient-record")),
            data_quality=DataQuality(notes=recorder.notes, unparsed_total=len(loaded.failures)),
        )

    for rejection in merged.rejected:
        for reason in rejection.reasons:
            recorder.withhold("Patient", rejection.patient_id, f"not merged with the primary record: {reason}", "patient")

    problems = _build_problems(loaded, merged, recorder)
    medications = _build_medications(loaded, merged, recorder)
    allergies = _build_allergies(loaded, merged, recorder)
    encounters = _build_encounters(loaded, merged, recorder, anchor)
    observations = _build_observations(loaded, merged, recorder, anchor)

    withheld = (
        problems.withheld_count
        + medications.withheld_count
        + allergies.withheld_count
        + encounters.withheld_count
        + observations.withheld_count
    )

    log_summary_built(merged.primary.id, withheld, len(loaded.failures), len(recorder.notes))

    return PatientSummary(
        as_of=anchor_date,
        patient=merged.demographics,
        problems=problems,
        medications=medications,
        allergies=allergies,
        encounters=encounters,
        observations=observations,
        data_quality=DataQuality(notes=recorder.notes, withheld_total=withheld, unparsed_total=len(loaded.failures)),
    )


def _subject_of(reference: Optional[Reference], merged) -> str:
    """Where a resource's subject points: the primary record, a merged duplicate, or elsewhere."""
    if reference is None or not reference.reference:
        return "missing"
    target = reference.reference.split("/")[-1]
    if target == merged.primary.id:
        return "primary"
    if target in merged.member_ids:
        return "duplicate"
    return "foreign"


def _section_state(total: int, shown: int, withheld: int) -> SectionState:
    if total == 0:
        return SectionState.NONE_IN_SOURCE
    if shown == 0:
        return SectionState.ALL_WITHHELD
    if withheld > 0:
        return SectionState.PARTIALLY_WITHHELD
    return SectionState.POPULATED


def _concept_flags(concept: Optional[CodedConcept], warnings: List[str]) -> List[Flag]:
    flags: List[Flag] = []
    if concept is not None and not concept.has_display:
        label = concept.system_label or "unknown system"
        flags.append(Flag(code=FlagCode.UNMAPPED_CODE, detail=f"source gave {label} code '{concept.code}' with no display name"))
    for warning in warnings:
        flags.append(Flag(code=FlagCode.CODING_MISMATCH, detail=warning))
    return flags


def _date_flags(date: Optional[PrecisionDate]) -> List[Flag]:
    if date is None:
        return []
    if date.precision.value in {"year", "month"}:
        return [Flag(code=FlagCode.LOW_PRECISION_DATE, detail=f"source recorded only '{date.raw}'")]
    if date.precision.value == "unknown":
        return [Flag(code=FlagCode.LOW_PRECISION_DATE, detail=f"date '{date.raw}' could not be interpreted")]
    return []


def _reference_flag(reference: Optional[Reference], loaded: LoadedBundle, label: str) -> List[Flag]:
    if reference is None or not reference.reference:
        return []
    if loaded.resolve(reference.reference) is None:
        detail = f"{label} '{reference.reference}' is not present in the bundle"
        return [Flag(code=FlagCode.UNRESOLVED_REFERENCE, detail=detail)]
    return []


def _base_flags(
    verdict: StatusVerdict,
    concept: Optional[CodedConcept],
    warnings: List[str],
    date: Optional[PrecisionDate],
) -> List[Flag]:
    """Status, coding and date flags, in the order every section presents them."""
    return [*verdict.flags, *_concept_flags(concept, warnings), *_date_flags(date)]


def _duplicate_subject_flag(detail: str) -> Flag:
    return Flag(code=FlagCode.UNVERIFIED_SUBJECT, detail=detail)


def _unknown_concept() -> CodedConcept:
    return CodedConcept(display=None, code=None, has_display=False)


def _sort_key(date: Optional[PrecisionDate]) -> float:
    return -(date.sort_key.timestamp() if date and date.sort_key else 0)


def _build_problems(loaded: LoadedBundle, merged, recorder: Recorder) -> Section[Problem]:
    screened = _screen(
        loaded.conditions,
        "Condition",
        lambda c: c.subject,
        lambda c: classify_condition(status_code(c.clinicalStatus), status_code(c.verificationStatus)),
        "problems",
        merged,
        recorder,
    )

    items: List[Problem] = []
    for condition, verdict, placement in screened.kept:
        concept, warnings = build_coded_concept(condition.code)
        onset = parse_fhir_date(condition.onsetDateTime)

        flags = _base_flags(verdict, concept, warnings, onset)
        flags += _reference_flag(condition.encounter, loaded, "encounter")
        if placement == "duplicate":
            flags.append(_duplicate_subject_flag("recorded against a possible duplicate patient record"))

        items.append(
            Problem(
                id=condition.id,
                concept=concept or _unknown_concept(),
                clinical_status=status_code(condition.clinicalStatus),
                verification_status=status_code(condition.verificationStatus),
                onset=onset,
                is_historical=verdict.disposition is Disposition.HISTORICAL,
                flags=flags,
            )
        )

    items.sort(key=lambda p: (p.is_historical, _sort_key(p.onset)))
    return Section[Problem](state=screened.state(len(items)), items=items, withheld_count=screened.withheld)


def _build_medications(loaded: LoadedBundle, merged, recorder: Recorder) -> MedicationSection:
    screened = _screen(
        loaded.medications,
        "MedicationRequest",
        lambda m: m.subject,
        lambda m: classify_medication(m.status, m.intent),
        "medications",
        merged,
        recorder,
    )

    active: List[Medication] = []
    historical: List[Medication] = []
    unverified: List[Medication] = []

    for request, verdict, placement in screened.kept:
        concept, warnings = build_coded_concept(request.medicationCodeableConcept)
        authored = parse_fhir_date(request.authoredOn)

        flags = _base_flags(verdict, concept, warnings, authored)
        flags += _reference_flag(request.encounter, loaded, "encounter")

        source_record = None
        if placement == "duplicate":
            source_record = _mrn_for(merged, request.subject)
            flags.append(_duplicate_subject_flag("prescribed against a possible duplicate patient record; identity not verified"))

        medication = Medication(
            id=request.id,
            concept=concept or _unknown_concept(),
            dosage=request.dosageInstruction[0].text if request.dosageInstruction else None,
            status=request.status,
            authored_on=authored,
            source_record=source_record,
            flags=flags,
        )

        if placement == "duplicate":
            unverified.append(medication)
        elif verdict.disposition is Disposition.CURRENT:
            active.append(medication)
        else:
            historical.append(medication)

    shown = len(active) + len(historical) + len(unverified)
    return MedicationSection(
        state=screened.state(shown),
        active=active,
        historical=historical,
        unverified_subject=unverified,
        withheld_count=screened.withheld,
    )


def _mrn_for(merged, reference: Optional[Reference]) -> Optional[str]:
    if reference is None or not reference.reference:
        return None
    target = reference.reference.split("/")[-1]
    for record in merged.demographics.identity.source_records:
        if record.id == target:
            return record.mrn
    return None


def _build_allergies(loaded: LoadedBundle, merged, recorder: Recorder) -> Section[Allergy]:
    screened = _screen(
        loaded.allergies,
        "AllergyIntolerance",
        lambda a: a.patient,
        lambda a: classify_allergy(status_code(a.clinicalStatus), status_code(a.verificationStatus)),
        "allergies",
        merged,
        recorder,
        subject_label="patient",
    )

    items: List[Allergy] = []
    for allergy, verdict, placement in screened.kept:
        concept, warnings = build_coded_concept(allergy.code)
        recorded = parse_fhir_date(allergy.recordedDate)

        flags = _base_flags(verdict, concept, warnings, recorded)
        if placement == "duplicate":
            flags.append(_duplicate_subject_flag("recorded against a possible duplicate patient record"))

        items.append(
            Allergy(
                id=allergy.id,
                concept=concept or _unknown_concept(),
                criticality=allergy.criticality,
                clinical_status=status_code(allergy.clinicalStatus),
                verification_status=status_code(allergy.verificationStatus),
                recorded_date=recorded,
                is_historical=verdict.disposition is Disposition.HISTORICAL,
                flags=flags,
            )
        )

    # High criticality first, then anything still unconfirmed, so the riskiest is never below the fold.
    items.sort(key=lambda a: (a.is_historical, a.criticality != "high"))
    return Section[Allergy](state=screened.state(len(items)), items=items, withheld_count=screened.withheld)


def _build_encounters(loaded: LoadedBundle, merged, recorder: Recorder, anchor: Optional[datetime]) -> Section[EncounterSummary]:
    screened = _screen(
        loaded.encounters,
        "Encounter",
        lambda e: e.subject,
        lambda e: classify_encounter(e.status),
        "encounters",
        merged,
        recorder,
    )

    items: List[EncounterSummary] = []
    for encounter, verdict, placement in screened.kept:
        concept, warnings = build_coded_concept(encounter.type[0] if encounter.type else None)
        start = parse_fhir_date(encounter.period.start if encounter.period else None)
        end = parse_fhir_date(encounter.period.end if encounter.period else None)

        flags = _base_flags(verdict, concept, warnings, start)
        if encounter.period and encounter.period.start and not encounter.period.end:
            flags.append(Flag(code=FlagCode.UNCONFIRMED, detail="encounter has no recorded end time"))
        if placement == "duplicate":
            flags.append(_duplicate_subject_flag("recorded against a possible duplicate patient record"))

        items.append(
            EncounterSummary(
                id=encounter.id,
                type=concept,
                class_display=encounter.class_.display if encounter.class_ else None,
                status=encounter.status,
                start=start,
                end=end,
                recency=compute_recency(start, anchor, mark_stale=True),
                flags=flags,
            )
        )

    items.sort(key=lambda e: _sort_key(e.start))
    return Section[EncounterSummary](state=screened.state(len(items)), items=items, withheld_count=screened.withheld)


def _build_observations(loaded: LoadedBundle, merged, recorder: Recorder, anchor: Optional[datetime]) -> Section[ObservationSummary]:
    screened = _screen(
        loaded.observations,
        "Observation",
        lambda o: o.subject,
        lambda o: classify_observation(o.status),
        "observations",
        merged,
        recorder,
    )

    items: List[ObservationSummary] = []
    for observation, verdict, placement in screened.kept:
        concept, warnings = build_coded_concept(observation.code)
        effective = parse_fhir_date(observation.effectiveDateTime)
        value = _observation_value(observation)

        flags = _base_flags(verdict, concept, warnings, effective)
        flags += _reference_flag(observation.encounter, loaded, "encounter")
        for performer in observation.performer:
            flags += _reference_flag(performer, loaded, "performer")
        if value is None:
            flags.append(Flag(code=FlagCode.UNCONFIRMED, detail="observation has no recorded value"))
        if placement == "duplicate":
            flags.append(_duplicate_subject_flag("recorded against a possible duplicate patient record"))

        recency = compute_recency(effective, anchor, mark_stale=True)
        if recency and recency.is_stale:
            flags.append(Flag(code=FlagCode.STALE, detail=f"measured {recency.display}"))

        items.append(
            ObservationSummary(
                id=observation.id,
                concept=concept or _unknown_concept(),
                value=value,
                effective=effective,
                recency=recency,
                is_vital_sign=_is_vital_sign(observation.category),
                flags=flags,
            )
        )

    items.sort(key=lambda o: _sort_key(o.effective))
    return Section[ObservationSummary](state=screened.state(len(items)), items=items, withheld_count=screened.withheld)


def _is_vital_sign(categories: List[CodeableConcept]) -> bool:
    # Taken only from an explicit category. Inferring vital-sign status from the
    # LOINC code would be guessing at clinical meaning.
    for category in categories:
        for coding in category.coding:
            if coding.code == VITAL_SIGNS_CATEGORY:
                return True
    return False


def _format_quantity(quantity: Optional[Quantity]) -> Optional[str]:
    if quantity is None or quantity.value is None:
        return None
    number = quantity.value
    rendered = str(int(number)) if float(number).is_integer() else str(number)
    # Display the human unit; the UCUM code is retained on the source resource.
    return f"{rendered} {quantity.unit}".strip() if quantity.unit else rendered


def _observation_value(observation) -> Optional[ObservationValue]:
    direct = _format_quantity(observation.valueQuantity)
    if direct:
        return ObservationValue(display=direct)

    if not observation.component:
        return None

    parts: List[Tuple[Optional[str], str, Optional[str]]] = []
    for component in observation.component:
        concept, _ = build_coded_concept(component.code)
        rendered = _format_quantity(component.valueQuantity)
        if rendered is None:
            continue
        label = concept.display if concept else None
        parts.append((label, rendered, component.valueQuantity.unit if component.valueQuantity else None))

    if not parts:
        return None

    components = [
        ObservationComponentValue(
            label=CodedConcept(display=label, has_display=label is not None),
            display=rendered,
        )
        for label, rendered, _ in parts
    ]

    ordered = _order_blood_pressure(parts)
    units = {unit for _, _, unit in ordered if unit}
    if len(ordered) > 1 and len(units) == 1:
        unit = next(iter(units))
        numbers = [rendered.replace(f" {unit}", "") for _, rendered, _ in ordered]
        return ObservationValue(display=f"{'/'.join(numbers)} {unit}", components=components)

    return ObservationValue(display="; ".join(rendered for _, rendered, _ in ordered), components=components)


def _order_blood_pressure(parts):
    """Order by the source's own display text; fall back to the order given.

    Never derived from code values — the labels are what the bundle actually says.
    """

    def rank(item):
        label = (item[0] or "").lower()
        if "systolic" in label:
            return 0
        if "diastolic" in label:
            return 1
        return 2

    if any(rank(p) < 2 for p in parts):
        return sorted(parts, key=rank)
    return parts
