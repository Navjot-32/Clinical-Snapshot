"""Input models: what the bundle actually contains, not what we wish it contained.

Deliberately narrow — only fields the snapshot consumes. Two rules hold throughout:
status/code fields are plain `str` so an unrecognised value is classified downstream
rather than failing validation, and dates stay raw strings until normalization can
attach a precision to them.
"""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class FHIRModel(BaseModel):
    # Unmodelled fields are dropped by choice, not by Pydantic's silent default.
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class Coding(FHIRModel):
    system: Optional[str] = None
    code: Optional[str] = None
    display: Optional[str] = None


class CodeableConcept(FHIRModel):
    coding: List[Coding] = Field(default_factory=list)
    text: Optional[str] = None


class Reference(FHIRModel):
    reference: Optional[str] = None


class Quantity(FHIRModel):
    value: Optional[float] = None
    unit: Optional[str] = None
    system: Optional[str] = None
    code: Optional[str] = None


class Period(FHIRModel):
    start: Optional[str] = None
    end: Optional[str] = None


class Identifier(FHIRModel):
    system: Optional[str] = None
    value: Optional[str] = None


class HumanName(FHIRModel):
    use: Optional[str] = None
    family: Optional[str] = None
    given: List[str] = Field(default_factory=list)


class ContactPoint(FHIRModel):
    system: Optional[str] = None
    value: Optional[str] = None
    use: Optional[str] = None


class Address(FHIRModel):
    line: List[str] = Field(default_factory=list)
    city: Optional[str] = None
    state: Optional[str] = None
    postalCode: Optional[str] = None
    country: Optional[str] = None


class Extension(FHIRModel):
    """One level of nesting is enough for the US Core race/ethnicity shape."""

    url: str
    extension: List["Extension"] = Field(default_factory=list)
    valueCoding: Optional[Coding] = None
    valueString: Optional[str] = None


class Patient(FHIRModel):
    id: str
    identifier: List[Identifier] = Field(default_factory=list)
    active: Optional[bool] = None
    name: List[HumanName] = Field(default_factory=list)
    telecom: List[ContactPoint] = Field(default_factory=list)
    gender: Optional[str] = None
    birthDate: Optional[str] = None
    address: List[Address] = Field(default_factory=list)
    extension: List[Extension] = Field(default_factory=list)


class Encounter(FHIRModel):
    id: str
    status: Optional[str] = None
    class_: Optional[Coding] = Field(default=None, alias="class")
    type: List[CodeableConcept] = Field(default_factory=list)
    subject: Optional[Reference] = None
    period: Optional[Period] = None


class Condition(FHIRModel):
    id: str
    clinicalStatus: Optional[CodeableConcept] = None
    verificationStatus: Optional[CodeableConcept] = None
    code: Optional[CodeableConcept] = None
    subject: Optional[Reference] = None
    encounter: Optional[Reference] = None
    onsetDateTime: Optional[str] = None


class ObservationComponent(FHIRModel):
    code: Optional[CodeableConcept] = None
    valueQuantity: Optional[Quantity] = None


class Observation(FHIRModel):
    id: str
    status: Optional[str] = None
    category: List[CodeableConcept] = Field(default_factory=list)
    code: Optional[CodeableConcept] = None
    subject: Optional[Reference] = None
    encounter: Optional[Reference] = None
    performer: List[Reference] = Field(default_factory=list)
    effectiveDateTime: Optional[str] = None
    valueQuantity: Optional[Quantity] = None
    component: List[ObservationComponent] = Field(default_factory=list)


class Dosage(FHIRModel):
    text: Optional[str] = None


class MedicationRequest(FHIRModel):
    id: str
    status: Optional[str] = None
    intent: Optional[str] = None
    medicationCodeableConcept: Optional[CodeableConcept] = None
    subject: Optional[Reference] = None
    encounter: Optional[Reference] = None
    authoredOn: Optional[str] = None
    dosageInstruction: List[Dosage] = Field(default_factory=list)


class AllergyIntolerance(FHIRModel):
    id: str
    clinicalStatus: Optional[CodeableConcept] = None
    verificationStatus: Optional[CodeableConcept] = None
    code: Optional[CodeableConcept] = None
    criticality: Optional[str] = None
    patient: Optional[Reference] = None
    recordedDate: Optional[str] = None


class BundleEntry(FHIRModel):
    # Left as a dict so each resource is validated individually and a single
    # malformed entry cannot fail the whole bundle.
    resource: Optional[dict] = None


class Bundle(FHIRModel):
    resourceType: str
    id: Optional[str] = None
    type: Optional[str] = None
    timestamp: Optional[str] = None
    total: Optional[int] = None
    entry: List[BundleEntry] = Field(default_factory=list)


RESOURCE_MODELS = {
    "Patient": Patient,
    "Encounter": Encounter,
    "Condition": Condition,
    "Observation": Observation,
    "MedicationRequest": MedicationRequest,
    "AllergyIntolerance": AllergyIntolerance,
}
