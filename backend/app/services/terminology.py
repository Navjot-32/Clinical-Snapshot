"""Code system labelling and structural validation.

This module deliberately does not translate codes into clinical meaning. It names
the system a code belongs to and checks the code is shaped like a member of that
system. It never invents a display name: a wrong drug or diagnosis label rendered
as fact is more dangerous than an acknowledged gap.
"""

import re
from typing import List, Optional, Tuple

from app.models.fhir import CodeableConcept, Coding
from app.models.summary import CodedConcept

SYSTEM_LABELS = {
    "http://loinc.org": "LOINC",
    "http://snomed.info/sct": "SNOMED CT",
    "http://www.nlm.nih.gov/research/umls/rxnorm": "RxNorm",
    "http://hl7.org/fhir/sid/icd-10-cm": "ICD-10-CM",
    "http://hl7.org/fhir/sid/icd-10": "ICD-10",
    "http://unitsofmeasure.org": "UCUM",
    "http://hl7.org/fhir/sid/us-ssn": "US SSN",
    "urn:oid:2.16.840.1.113883.6.238": "CDC Race and Ethnicity",
    "http://terminology.hl7.org/CodeSystem/v3-ActCode": "HL7 ActCode",
    "http://terminology.hl7.org/CodeSystem/observation-category": "HL7 Observation Category",
    "http://terminology.hl7.org/CodeSystem/condition-clinical": "HL7 Condition Clinical Status",
    "http://terminology.hl7.org/CodeSystem/condition-ver-status": "HL7 Condition Verification Status",
    "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical": "HL7 Allergy Clinical Status",
    "http://terminology.hl7.org/CodeSystem/allergyintolerance-verification": "HL7 Allergy Verification Status",
}

# Structural shapes only — these say nothing about whether a code exists.
_SHAPES = {
    "http://snomed.info/sct": (re.compile(r"^\d{6,18}$"), "SNOMED CT codes are 6-18 digits with no punctuation"),
    "http://loinc.org": (re.compile(r"^\d{1,5}-\d$"), "LOINC codes are digits followed by a hyphen and a check digit"),
    "http://www.nlm.nih.gov/research/umls/rxnorm": (re.compile(r"^\d{1,8}$"), "RxNorm codes are digits only"),
    "http://hl7.org/fhir/sid/icd-10-cm": (
        re.compile(r"^[A-TV-Z]\d{2}(\.[A-Z0-9]{1,4})?$"),
        "ICD-10-CM codes are a letter, two digits, optionally a dot and up to four characters",
    ),
}


def system_label(uri: Optional[str]) -> Optional[str]:
    if not uri:
        return None
    return SYSTEM_LABELS.get(uri, uri)


def check_code_shape(system: Optional[str], code: Optional[str]) -> Optional[str]:
    """Return a warning if a code does not look like a member of its declared system."""
    if not system or not code:
        return None

    shape = _SHAPES.get(system)
    if shape is None:
        return None

    pattern, expectation = shape
    if pattern.match(code):
        return None

    warning = f"code '{code}' does not match its declared system ({system_label(system)}): {expectation}"

    # Naming the system it *does* look like is structural, not clinical, so it is safe.
    for other_system, (other_pattern, _) in _SHAPES.items():
        if other_system != system and other_pattern.match(code):
            warning += f"; it is shaped like {system_label(other_system)}"
            break

    return warning


def _pick_coding(concept: Optional[CodeableConcept]) -> Optional[Coding]:
    if concept is None or not concept.coding:
        return None
    for coding in concept.coding:
        if coding.display:
            return coding
    return concept.coding[0]


def build_coded_concept(concept: Optional[CodeableConcept]) -> Tuple[Optional[CodedConcept], List[str]]:
    """Build a displayable concept plus any structural warnings about it."""
    if concept is None:
        return None, []

    coding = _pick_coding(concept)
    if coding is None:
        # Free text with no coding at all is still better than nothing.
        if concept.text:
            return CodedConcept(display=concept.text, has_display=True), []
        return None, []

    display = coding.display or concept.text
    warnings = []

    warning = check_code_shape(coding.system, coding.code)
    if warning:
        warnings.append(warning)

    return (
        CodedConcept(
            display=display,
            code=coding.code,
            system_label=system_label(coding.system),
            system_uri=coding.system,
            has_display=display is not None,
        ),
        warnings,
    )


def status_code(concept: Optional[CodeableConcept]) -> Optional[str]:
    """FHIR status fields are CodeableConcepts; the code is what matters."""
    if concept is None or not concept.coding:
        return None
    for coding in concept.coding:
        if coding.code:
            return coding.code.lower()
    return None
