# Clinical Snapshot

A small full-stack application that converts a messy FHIR R4 bundle into a clinical
snapshot for one patient. The backend is built with FastAPI and Pydantic; the
frontend is a server-rendered Next.js page.

The main work is not the page layout. It is deciding which source records are safe to
present, which need visible qualification, and which must not be treated as clinical
fact.

## Prerequisites

- Python 3
- Node.js 18 or newer (developed with Node.js 24)
- npm

## Running locally

Start the backend first:

```bash
cd backend
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/uvicorn app.main:app --port 8000
```

Available endpoints:

- `GET /health` — process liveness
- `GET /ready` — confirms that the source bundle was found and parsed
- `GET /docs` — generated OpenAPI documentation
- `GET /patient-summary` — normalized patient snapshot consumed by the frontend

If `/ready` reports that the bundle is unavailable, set `BUNDLE_PATH` to the JSON
file:

```bash
BUNDLE_PATH=data/scenario1_fhir_bundle.json \
  ./.venv/bin/uvicorn app.main:app --port 8000
```

Then start the frontend in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. The frontend expects the API at http://localhost:8000;
set `BACKEND_URL` if it is running elsewhere.

If the API is unavailable, the page renders an explicit error state rather than empty
clinical sections.

## Tests and verification

Run the backend test suite with:

```bash
cd backend
./.venv/bin/python -m pytest tests/ -q
```

The suite contains 116 tests covering normalization, date precision, status handling,
reconciliation, unresolved references, withholding rules, and the API contract.

Verify the frontend production build with:

```bash
cd frontend
npm run build
```

The frontend was also rendered in headless Chrome and inspected manually. There is no
full browser-level E2E suite; see Known limitations.

## Project structure

```
backend/
  app/
    models/
      fhir.py          # permissive models for the source bundle
      summary.py       # normalized, safe-to-display response models
    services/          # indexing, reconciliation and normalization rules
    main.py            # FastAPI application and endpoints
  tests/

frontend/
  app/                 # server-rendered patient summary page
  components/          # clinical snapshot sections and shared UI
  lib/                 # API client and TypeScript response types

data/
  scenario1_fhir_bundle.json
```

The raw FHIR models and the summary response models are intentionally separate. The
frontend never needs to interpret raw FHIR or reproduce clinical filtering rules.

## Key decisions

### Empty does not always mean "none recorded"

An empty section can represent different situations:

- The bundle contained no matching records.
- Matching records existed, but all were invalid or unsafe to display.
- Some records were displayed and others were withheld.
- The section was populated without qualification.

Collapsing these cases into an empty array could turn a data-quality problem into a
clinical assertion. For example, an empty allergy section could be read as "no known
allergies" even when allergy records existed but could not safely be presented. Each
section therefore carries an explicit state, and the UI renders that state in plain
language.

### `entered-in-error` records are not clinical facts

Resources marked `entered-in-error` are excluded from clinical sections. This
includes `observation-004`, whose value could appear clinically significant even
though the source explicitly marks the record as invalid.

The invalid value is not repeated in the clinical UI, data-quality messages, API
response, or application logs. Normalization audit information retains only the
resource identity and the exclusion rule. Tests verify that the value does not leak
back through another output path.

### Status handling is resource-specific

Status does not mean the same thing for every FHIR resource:

- A `finished` `Encounter` is appropriate for encounter history.
- A `stopped` `MedicationRequest` is valid historical information but not an active
  medication.
- A `preliminary` `Observation` can be displayed only with its uncertainty visible.
- A `refuted` or `entered-in-error` `Condition` must not appear as a current problem.

The normalizer uses an explicit policy for each supported resource type and a
conservative fallback for missing or unrecognized statuses. Unknown data is never
promoted to current clinical fact.

Allergies are the deliberate exception to the usual fallback direction. An otherwise
attributable allergy with an uncertain status remains visible with an uncertainty
label because omission may carry greater risk. `Refuted` and `entered-in-error`
allergies are still excluded.

### Missing terminology displays stay unresolved

Several codings contain a system and code but no human-readable display. The
application does not ask an LLM or use a hardcoded clinical lookup table to supply
the missing meaning.

Display resolution follows this order:

1. `CodeableConcept.text`
2. Source-provided `Coding.display`
3. Original code plus a normalized coding-system name
4. An explicit "description unavailable" marker

For example, an unmapped code is shown as `E11.9 · ICD-10-CM`, not as a
model-generated diagnosis. This costs readability but avoids presenting an unverified
label as fact. A production version should use a versioned terminology service and
retain lookup provenance.

The blood-pressure observation is composite. In this bundle, the source provides
labels for the systolic and diastolic components, so the combined value is derived
from those labels rather than array position or model recall.

### Dates preserve source precision

FHIR dates in the bundle range from year-only values such as `"2019"` to complete
timestamps. The raw value and its lexical precision are retained during
normalization:

- `"2019"` displays as `2019`.
- A complete date displays as a date.
- A clinical timestamp can retain its time where that detail is relevant.

An internal sort value may be derived for deterministic ordering, but it is not
returned as if it came from the source. Midnight and January 1 values are not
automatically downgraded: without provenance, they might be padding or genuine
clinical times. Presentation can omit unnecessary time detail without changing the
recorded source precision.

### The two Patient resources are reconciled as a probable duplicate

The two Patient resources have compatible names, gender, birth year, and addresses.
The assessment also states that the bundle represents one patient. Their MRNs are not
identical, so this is treated as a probable reconciliation rather than a verified
enterprise identity match.

`patient-001` is selected as the canonical record because it has the more complete
demographics and a US Core profile. Complementary values are combined rather than
resolved through blanket field precedence. This preserves both the home number from
one record and the mobile number from the other. Field-level provenance records where
each selected value originated, and genuine contradictions are surfaced as conflicts.

`medicationrequest-003` belongs to `patient-002`. Treating it as an unquestioned
active medication would overstate the identity match, while dropping it would hide a
live order. It is therefore displayed separately with its identity uncertainty and
source association made explicit.

This reconciliation is scoped to the supplied single-patient scenario. It is not
intended to replace a production Master Patient Index.

### The frontend prioritizes rapid scanning

The brief defines the clinical sections but not their presentation. The page
therefore makes several explicit layout choices:

- Allergies appear before problems because they may affect an immediate decision.
- Numeric observation values align consistently for faster scanning.
- Active and historical medications remain visually separate.
- Uncertainty uses a shared badge vocabulary across sections.
- Status is communicated with text, not colour alone.

The page is server-rendered and contains no client components because this view does
not require client-side state or interaction.

## Known limitations and accepted trade-offs

- **Terminology resolution:** Unknown codes remain difficult to read. Without a
  verified terminology service, the application also cannot reliably identify
  semantic duplicates expressed through different coding systems.
- **Patient matching:** Reconciliation is an assessment-scoped heuristic supported by
  the single-patient guarantee, not general-purpose record linkage.
- **Clinical interpretation:** The bundle does not provide reference ranges or
  reliable interpretation metadata, so observations such as 138/88 are displayed
  without independently labelling them normal or abnormal.
- **Allergy detail:** `AllergyIntolerance.reaction` is not modelled. A production
  summary should distinguish reaction manifestations and severity where available.
- **Observation values:** The current implementation focuses on quantities and
  composite quantity observations. Additional FHIR value types would need explicit
  display policies.
- **Frontend testing:** There is no full Playwright or component-test suite. Current
  verification consists of type checking, a production build, server-rendered HTML
  assertions, and manual inspection of browser screenshots.
- **Normalizer size:** `summary_builder.py` is larger than ideal. Before supporting
  more resource types, I would extract shared flag construction and value rendering
  into focused modules.

## What I would do next

- Add a verified terminology service with versioning, caching, and provenance.
- Add reference ranges and source-provided observation interpretation.
- Provide an audit view of the individual source Patient records and the
  reconciliation evidence.
- Add Playwright coverage for the main clinical and error-state journeys.
- Add property-based tests over generated bundles to exercise status, reference, and
  date-precision combinations.
- Complete a screen-reader and automated contrast review.

## AI-assisted development

The project was built with Claude Code. The models used, areas where AI accelerated
development, and specific examples where its output was rejected or corrected are
documented in `AI_USAGE.md`.
