// Mirrors the backend's PatientSummary response. Hand-written rather than
// generated: one endpoint, one consumer. If the backend shape changes, this
// must change with it.

export type DatePrecision = "year" | "month" | "day" | "instant" | "unknown";

export interface PrecisionDate {
  raw: string;
  precision: DatePrecision;
  display: string;
}

export interface Recency {
  daysAgo: number | null;
  display: string;
  isStale: boolean;
}

export type FlagCode =
  | "unconfirmed"
  | "unmapped-code"
  | "coding-mismatch"
  | "unresolved-reference"
  | "unverified-subject"
  | "low-precision-date"
  | "stale"
  | "unrecognised-status";

export interface Flag {
  code: FlagCode;
  detail: string | null;
}

export interface CodedConcept {
  display: string | null;
  code: string | null;
  systemLabel: string | null;
  systemUri: string | null;
  hasDisplay: boolean;
}

export interface Sourced<T> {
  value: T;
  sources: string[];
  note: string | null;
}

export type SectionState =
  | "populated"
  | "none-in-source"
  | "all-withheld"
  | "partially-withheld";

export interface Section<T> {
  state: SectionState;
  items: T[];
  withheldCount: number;
}

export interface Problem {
  id: string;
  concept: CodedConcept;
  clinicalStatus: string | null;
  verificationStatus: string | null;
  onset: PrecisionDate | null;
  isHistorical: boolean;
  flags: Flag[];
}

export interface Medication {
  id: string;
  concept: CodedConcept;
  dosage: string | null;
  status: string | null;
  authoredOn: PrecisionDate | null;
  sourceRecord: string | null;
  flags: Flag[];
}

export interface MedicationSection {
  state: SectionState;
  active: Medication[];
  historical: Medication[];
  unverifiedSubject: Medication[];
  withheldCount: number;
}

export interface Allergy {
  id: string;
  concept: CodedConcept;
  criticality: string | null;
  clinicalStatus: string | null;
  verificationStatus: string | null;
  recordedDate: PrecisionDate | null;
  isHistorical: boolean;
  flags: Flag[];
}

export interface EncounterSummary {
  id: string;
  type: CodedConcept | null;
  classDisplay: string | null;
  status: string | null;
  start: PrecisionDate | null;
  end: PrecisionDate | null;
  recency: Recency | null;
  flags: Flag[];
}

export interface ObservationComponentValue {
  label: CodedConcept;
  display: string;
}

export interface ObservationValue {
  display: string;
  components: ObservationComponentValue[];
}

export interface ObservationSummary {
  id: string;
  concept: CodedConcept;
  value: ObservationValue | null;
  effective: PrecisionDate | null;
  recency: Recency | null;
  isVitalSign: boolean;
  flags: Flag[];
}

export interface SourceRecord {
  id: string;
  mrn: string | null;
  role: string;
}

export interface IdentityResolution {
  resolution: string;
  sourceRecords: SourceRecord[];
  matchEvidence: string[];
}

export interface ContactPoint {
  system: string | null;
  use: string | null;
  value: string;
}

export interface Demographics {
  identity: IdentityResolution;
  name: Sourced<string> | null;
  birthDate: Sourced<PrecisionDate> | null;
  age: Sourced<string> | null;
  gender: Sourced<string> | null;
  telecom: Sourced<ContactPoint>[];
  address: Sourced<string> | null;
  race: Sourced<string> | null;
  ethnicity: Sourced<string> | null;
  identifiers: Sourced<string>[];
}

export interface DataQualityNote {
  resourceType: string;
  resourceId: string;
  reason: string;
  section: string | null;
}

export interface DataQuality {
  notes: DataQualityNote[];
  withheldTotal: number;
  unparsedTotal: number;
}

export interface PatientSummary {
  asOf: PrecisionDate;
  patient: Demographics;
  problems: Section<Problem>;
  medications: MedicationSection;
  allergies: Section<Allergy>;
  encounters: Section<EncounterSummary>;
  observations: Section<ObservationSummary>;
  dataQuality: DataQuality;
}
