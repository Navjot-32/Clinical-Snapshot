"""Output models: what is safe to display, which is not the same as what arrived.

Everything here is produced by the normalization pass. Two absences are deliberate
and load-bearing: there is no SSN field anywhere, and DataQualityNote carries no
value field — naming an erroneous measurement would put it back on screen.
"""

from datetime import datetime
from enum import Enum
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

T = TypeVar("T")


class SummaryModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class DatePrecision(str, Enum):
    YEAR = "year"
    MONTH = "month"
    DAY = "day"
    INSTANT = "instant"
    UNKNOWN = "unknown"


class PrecisionDate(SummaryModel):
    raw: str
    precision: DatePrecision
    display: str
    # Ordering only. Excluded from the response so a padded value can never be
    # mistaken for a real one by a consumer.
    sort_key: Optional[datetime] = Field(default=None, exclude=True)


class Recency(SummaryModel):
    days_ago: Optional[int] = None
    display: str
    is_stale: bool = False


class FlagCode(str, Enum):
    UNCONFIRMED = "unconfirmed"
    UNMAPPED_CODE = "unmapped-code"
    CODING_MISMATCH = "coding-mismatch"
    UNRESOLVED_REFERENCE = "unresolved-reference"
    UNVERIFIED_SUBJECT = "unverified-subject"
    LOW_PRECISION_DATE = "low-precision-date"
    STALE = "stale"
    UNRECOGNISED_STATUS = "unrecognised-status"


class Flag(SummaryModel):
    code: FlagCode
    detail: Optional[str] = None


class CodedConcept(SummaryModel):
    """A code the UI can render honestly, whether or not the source named it."""

    display: Optional[str] = None
    code: Optional[str] = None
    system_label: Optional[str] = None
    system_uri: Optional[str] = None
    has_display: bool = True


class Sourced(SummaryModel, Generic[T]):
    value: T
    sources: List[str] = Field(default_factory=list)
    note: Optional[str] = None


class SectionState(str, Enum):
    POPULATED = "populated"
    NONE_IN_SOURCE = "none-in-source"
    ALL_WITHHELD = "all-withheld"
    PARTIALLY_WITHHELD = "partially-withheld"


class Section(SummaryModel, Generic[T]):
    state: SectionState
    items: List[T] = Field(default_factory=list)
    withheld_count: int = 0


class Problem(SummaryModel):
    id: str
    concept: CodedConcept
    clinical_status: Optional[str] = None
    verification_status: Optional[str] = None
    onset: Optional[PrecisionDate] = None
    is_historical: bool = False
    flags: List[Flag] = Field(default_factory=list)


class Medication(SummaryModel):
    id: str
    concept: CodedConcept
    dosage: Optional[str] = None
    status: Optional[str] = None
    authored_on: Optional[PrecisionDate] = None
    source_record: Optional[str] = None
    flags: List[Flag] = Field(default_factory=list)


class MedicationSection(SummaryModel):
    state: SectionState
    active: List[Medication] = Field(default_factory=list)
    historical: List[Medication] = Field(default_factory=list)
    # Subject resolves to a duplicate patient record rather than the primary one.
    unverified_subject: List[Medication] = Field(default_factory=list)
    withheld_count: int = 0


class Allergy(SummaryModel):
    id: str
    concept: CodedConcept
    criticality: Optional[str] = None
    clinical_status: Optional[str] = None
    verification_status: Optional[str] = None
    recorded_date: Optional[PrecisionDate] = None
    is_historical: bool = False
    flags: List[Flag] = Field(default_factory=list)


class EncounterSummary(SummaryModel):
    id: str
    type: Optional[CodedConcept] = None
    class_display: Optional[str] = None
    status: Optional[str] = None
    start: Optional[PrecisionDate] = None
    end: Optional[PrecisionDate] = None
    recency: Optional[Recency] = None
    flags: List[Flag] = Field(default_factory=list)


class ObservationComponentValue(SummaryModel):
    label: CodedConcept
    display: str


class ObservationValue(SummaryModel):
    display: str
    components: List[ObservationComponentValue] = Field(default_factory=list)


class ObservationSummary(SummaryModel):
    id: str
    concept: CodedConcept
    value: Optional[ObservationValue] = None
    effective: Optional[PrecisionDate] = None
    recency: Optional[Recency] = None
    is_vital_sign: bool = False
    flags: List[Flag] = Field(default_factory=list)


class SourceRecord(SummaryModel):
    id: str
    mrn: Optional[str] = None
    role: str


class IdentityResolution(SummaryModel):
    resolution: str
    source_records: List[SourceRecord] = Field(default_factory=list)
    match_evidence: List[str] = Field(default_factory=list)


class ContactPoint(SummaryModel):
    system: Optional[str] = None
    use: Optional[str] = None
    value: str


class Demographics(SummaryModel):
    identity: IdentityResolution
    name: Optional[Sourced[str]] = None
    birth_date: Optional[Sourced[PrecisionDate]] = None
    age: Optional[Sourced[str]] = None
    gender: Optional[Sourced[str]] = None
    telecom: List[Sourced[ContactPoint]] = Field(default_factory=list)
    address: Optional[Sourced[str]] = None
    race: Optional[Sourced[str]] = None
    ethnicity: Optional[Sourced[str]] = None
    identifiers: List[Sourced[str]] = Field(default_factory=list)


class DataQualityNote(SummaryModel):
    resource_type: str
    resource_id: str
    reason: str
    section: Optional[str] = None


class DataQuality(SummaryModel):
    notes: List[DataQualityNote] = Field(default_factory=list)
    withheld_total: int = 0
    unparsed_total: int = 0


class PatientSummary(SummaryModel):
    as_of: PrecisionDate
    patient: Demographics
    problems: Section[Problem] = Field(default_factory=lambda: Section(state=SectionState.NONE_IN_SOURCE))
    medications: MedicationSection = Field(default_factory=lambda: MedicationSection(state=SectionState.NONE_IN_SOURCE))
    allergies: Section[Allergy] = Field(default_factory=lambda: Section(state=SectionState.NONE_IN_SOURCE))
    encounters: Section[EncounterSummary] = Field(default_factory=lambda: Section(state=SectionState.NONE_IN_SOURCE))
    observations: Section[ObservationSummary] = Field(default_factory=lambda: Section(state=SectionState.NONE_IN_SOURCE))
    data_quality: DataQuality = Field(default_factory=DataQuality)
