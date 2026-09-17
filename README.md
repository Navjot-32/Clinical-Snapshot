# Clinical Snapshot

A FastAPI service that normalises the FHIR bundle and a Next.js page that renders it.
The bundle is broken in about a dozen ways on purpose, so most of the work here is
deciding what is safe to put in front of a clinician, not drawing the page.

## Running it

Backend first.

```bash
cd backend
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/uvicorn app.main:app --port 8000
```

`/health` is liveness, `/ready` confirms the bundle actually parsed, `/docs` is the
generated API reference. If `bundle_present` comes back false, point `BUNDLE_PATH` at
`data/scenario1_fhir_bundle.json`.

Then the frontend:

```bash
cd frontend
npm install
npm run dev
```

<http://localhost:3000>. Node 18+, developed on 24. It needs the backend running; set
`BACKEND_URL` if that isn't on port 8000. If the API is down the page says so rather
than rendering blank sections.

Tests: `cd backend && ./.venv/bin/python -m pytest tests/ -q` — 120 of them, about a
fifth of a second.

## How it's laid out

`models/fhir.py` is what the bundle contains. `models/summary.py` is what's safe to
show. Everything in `services/` is the pass between the two, and that's where the
time went. The frontend is one server-rendered page; there are no client components.

## Decisions

### Empty sections

This is the one I'd defend hardest. If you filter every allergy record out of a
bundle and then render an empty allergies box, a clinician reads that as "no known
allergies" — a clinical claim you haven't earned. So every section carries a state:
nothing was in the source, everything was withheld, some was withheld, or it's fine.
The UI says which. Getting this wrong is a patient-safety bug, not a cosmetic one.

### entered-in-error means gone

`observation-004` is a creatinine of 14.7 mg/dL flagged `entered-in-error`. It's a
number that would make someone act, and the source says it never happened. It isn't
shown as a result, isn't shown as an abnormal flag, and — the part that's easy to get
wrong — isn't named in the data-quality panel either. Listing "Creatinine 14.7
withheld" in a footnote puts it right back on the screen. The notes carry the record
id and the rule that fired, nothing else. There's a test asserting the string `14.7`
appears nowhere in the response or the logs.

### Statuses come from the spec, not from this bundle

Only five status values actually occur in the sample. If I'd coded to those, a
`refuted` condition or a `cancelled` medication would sail through as current fact,
and the brief says plainly that the list of defects isn't exhaustive. So the
classifier covers the full R4 value sets and anything it doesn't recognise fails safe.

One deliberate exception: for allergies, "fails safe" means the opposite. Everywhere
else an unintelligible status demotes the record out of the current view. An allergy
with a broken status still gets shown, flagged. Withholding a diagnosis is cautious;
withholding an allergy can kill someone. It's the only inconsistency in the codebase
and it's there on purpose.

### Codes with no name stay unnamed

Four codings arrive with a code and a system and no display text. It is very tempting
to fill those in — I had a model offer me an identification for SNOMED `91936005` and
simultaneously warn me its recall of SNOMED identifiers isn't trustworthy. That's the
whole argument. A wrong drug name rendered as fact is worse than a gap, so unnamed
codes render as `E11.9 · ICD-10-CM` with a marker. Same reasoning applies to blood
pressure: rather than hardcoding which LOINC code is systolic, the components are
identified from the display text the bundle itself supplies, because getting it
backwards gives you `88/138`.

This costs real readability and I'd rather say so than pretend otherwise.

### Dates keep whatever precision they arrived with

`"2019"` renders as `2019`. Sorting needs a real datetime, so one is derived and
excluded from the API response, where it can't be mistaken for something the source
said. Timestamps sitting at exactly midnight are treated as dates — that's upstream
padding far more often than a real clinical time — but I stopped short of demoting
`2018-01-01T00:00:00Z` to a bare year, because a thing that genuinely happened on New
Year's Day would lose a real day.

### The two Patient records

Obviously the same person: same name, same address modulo `Lane`/`Ln`, MRNs sharing a
root, and birth dates of `1958-03-12` and `1958`, which agree — one is just less
precise. That last point matters, because treating it as a conflict would put a
spurious warning on a correct match.

They're merged by union rather than precedence. Precedence looks reasonable until you
notice one record holds a *home* number and the other a *mobile*: different slots, not
competing values, and picking a winner silently drops a phone number. Every merged
field records which record it came from.

Merging requires two fields to agree, no contradiction, and at least one of those
agreements to be a field that identifies a *person* — birth date or MRN root. That
last clause came late. I had it counting agreements without weighting them, and while
writing up the tradeoffs I found the rule merged a mother and daughter: same surname,
same address, same gender, one record missing a birth date. Three agreements, no
contradiction, two different people. Name, gender and address describe a household,
not an individual. There's a regression test for it now, and when a match is refused
the record says which check failed.

`medicationrequest-003` is active and belongs to the duplicate record. Folding it into
the active list asserts this patient is taking it; dropping it hides a live drug. It
gets its own block saying the identity isn't verified, with an instruction to check.
Wrong-patient medication is the worst thing this dataset can make you do.

### Everything is relative to the bundle timestamp

Ages, recency and staleness anchor to the bundle's own `timestamp` (1 June 2026), not
`now()`. Two reasons. Deterministic output means the tests assert real values instead
of recomputing the thing they're checking — `test_age_is_anchored_to_the_bundle_not_wall_clock`
asserts literally `"68 years"`, which would rot on a birthday if it used the clock.
And "recent" should mean recent relative to the data: an encounter six months before
the bundle is recent whether you read this today or in two years. The page states the
anchor in the footer so nobody reads the figures as current.

### Smaller ones

The brief specifies which sections to show but nothing about presentation, so the
layout is mine. Allergies sit above problems because they're likelier to change an
immediate decision, observation values are right-aligned into one column because you
scan that section for numbers, and uncertainty goes through one badge vocabulary used
identically everywhere.

Every withheld record is logged as structured JSON from the same call that builds the
UI note, so the two can't drift — a test asserts the counts match. No clinical values
reach the logs. An unhandled exception returns an explicit failure rather than a 200
with empty sections, because a server fault must never look like a patient with
nothing wrong with them.

## Tradeoffs

### Unnamed codes are unreadable

Four codings arrive with no display text: `E11.9` on `condition-003`, LOINC `4548-4`
on `observation-002`, RxNorm `849574` on `medicationrequest-003`, SNOMED `91936005` on
`allergyintolerance-003`. They render as `4548-4 · LOINC` with a "no name in source"
badge. A clinician cannot tell that `4548-4` is an HbA1c without looking it up, and
readability is one of the things being marked.

The fix is a static map plus a provenance field — `CodedConcept.labelSource` of
`"source"` or `"local-reference"` — so the UI can show "Hemoglobin A1c (label from
local reference)" without claiming the bundle said it. I didn't do it because
verifying four code-to-label mappings against an authoritative source takes longer
than I had, and an unverified map is precisely the failure I was avoiding.

### Cross-coding duplicates are undetectable

`allergyintolerance-001` is declared SNOMED, code `7980-2`, display "Penicillin".
`allergyintolerance-003` is SNOMED `91936005` with no display. If `91936005` denotes a
penicillin allergy, those are one allergy shown as two rows — and they disagree: the
first is confirmed with high criticality, the second unconfirmed with criticality
unassessable. A clinician could reasonably read that as two separate problems.

Deduplication has to happen on the resolved concept, not on the code, so this is
blocked behind terminology resolution above.

### Patient matching is still a heuristic

`_compare()` in `normalize.py` scores field agreements, requires at least one
identifying field (birth date or MRN root) among them, and refuses on any
contradiction. That rule is deterministic and explainable, which is why I chose it,
but it is not record linkage.

What it still doesn't do:

- **No probabilistic scoring.** Agreement is boolean per field. Real linkage weights
  each field by how discriminating it is — a shared surname of "Smith" is far weaker
  evidence than a shared surname of "Whitfield", and nothing here knows that.
  Fellegi-Sunter with match/review/reject thresholds is the standard treatment.
- **No fuzzy comparison.** `Dorothy` and `Dorothey` are a mismatch, as are transposed
  digits in an MRN. Real feeds are full of both. Jaro-Winkler on names and edit
  distance on identifiers would catch them.
- **No transitivity.** Candidates are compared only against the chosen primary. If A
  matches B and B matches C, C is never compared to A, so a three-record duplicate set
  can resolve into two.
- **O(n²) with no blocking.** Fine for two records. A real patient index blocks on
  something cheap — postcode, surname soundex — before pairwise comparison.
- **Primary selection is crude.** `_completeness()` sums field counts and adds the
  *string length* of the birth date so a full date outranks a bare year. It works on
  this data and it mixes units; a real implementation would score by which fields are
  populated, not by how long they are.

The UI never states the match as fact, which limits the damage of a wrong call, but
that's mitigation rather than a fix.

### No reference ranges or interpretation

`Observation.referenceRange` and `Observation.interpretation` aren't modelled. Blood
pressure 138/88 is stage 1 hypertension and an HbA1c of 6.1% is pre-diabetic, and the
page shows both as bare numbers with no indication either is out of range.

Worth being precise about the cause: this bundle doesn't supply `referenceRange` on
any observation, so modelling the field alone wouldn't help here — it needs locally
held ranges, which raises the same provenance question as code labels. Of everything I
left out this is the one I'm least comfortable with, because a snapshot meant to be
read in seconds is exactly where an out-of-range marker earns its keep.

### Observations with non-quantity values are misreported

`_observation_value()` handles `valueQuantity` and `component[].valueQuantity` only.
FHIR also permits `valueString`, `valueCodeableConcept`, `valueBoolean`, `valueRatio`,
`valueRange` and others. An observation carrying any of those currently renders "No
value recorded" with an `unconfirmed` flag.

That's worse than a gap — it asserts no result exists when one does. A blood culture
reported as a `valueCodeableConcept` would read as an unresolved test. It doesn't
occur in this bundle, so nothing is wrong on screen today, but I'd class it as a
latent correctness bug rather than a missing feature — which is why it leads the list
at the end.

### Allergy reactions aren't modelled

`AllergyIntolerance.reaction[].manifestation` and `.severity` are dropped. "Penicillin,
high criticality" doesn't distinguish anaphylaxis from a rash, which is a
decision-changing difference. Not present in this bundle, and cheap to add.

### No frontend tests

Verification is `tsc --noEmit`, a production build, and assertions against the fetched
HTML. What that leaves untested is component logic in isolation — specifically
`Section.tsx`, which decides between "no records in the source" and "records exist but
none are displayable". That branch is the safety-critical one and it's currently only
exercised indirectly, through the `state` value the backend sends.

The data-safety logic lives in the backend and that's where the 120 tests went. Given
more hours the frontend gets Vitest on `Section`, `Badge` and `ConceptLabel`.

### summary_builder.py is too long

541 lines holding four concerns: orchestration (~95), five section builders (~230),
flag construction (~70), observation value rendering (~85). The five builders share a
shape and are deliberately together, but the two leaf concerns should be their own
modules. It's a pure move with no behaviour change, and I'd rather spend remaining
time on correctness than on shuffling files.

### Operational limits

The bundle is parsed once at startup, so changing the file on disk needs a restart.
One hardcoded patient, no auth, no persistence, no API versioning. `Patient.active` is
parsed but unused — an inactive source record probably ought to weaken a merge rather
than be ignored.

## With more time

Roughly in the order I'd do them. The first item is fixing things that are wrong;
everything after it is adding things that are absent. That ordering is deliberate — a
latent defect outranks a missing feature even when the feature is the one you'd notice.

**Close the known correctness gaps.** Three small things, all defects rather than
absences. A dispatch in `_observation_value()` covering `valueString`,
`valueCodeableConcept`, `valueBoolean`, `valueRatio` and `valueRange`, so an
observation that carries a result stops reporting that it has none (~25 lines).
`AllergyIntolerance.reaction[].manifestation` and `.severity` carried through the
models into `AllergiesList.tsx`, so "penicillin, high criticality" can distinguish
anaphylaxis from a rash (~15). And `Patient.active`, currently parsed and ignored:
an inactive source record merging into an active one should register as a weak
contradiction in `_compare()` rather than pass unremarked. Half a day for the three,
tests included.

**Terminology resolution, with provenance.** Extend `terminology.py` with
`resolve_display(system, code) -> Optional[ResolvedLabel]`, where `ResolvedLabel`
carries whether the label came from the bundle or a local table. `CodedConcept` gains
`labelSource`; the UI renders locally-sourced labels differently from source-supplied
ones. Start with a vendored subset covering the codes actually present, move to a FHIR
terminology server `$lookup` behind the same interface. This unblocks concept-level
deduplication too, which is the only way to catch the possible penicillin duplicate.

**Reference ranges and interpretation.** Model both fields; add `abnormal` and
`rangeDisplay` to `ObservationSummary`; where the source supplies neither, fall back to
locally held ranges marked with the same provenance mechanism as labels. Silence stays
the default when nothing is known — an unmarked value should never imply "normal".

**A real linkage rule, and a merge you can audit.** Two halves, and the second matters
more. On accuracy: replace boolean field agreement with weighted scoring — Fellegi-Sunter,
m/u probabilities estimated from the feed, and match/review/reject thresholds so the
middle band becomes a human queue instead of a coin flip — plus Jaro-Winkler on names
and edit distance on identifiers, transitive closure over candidate pairs so a
three-record duplicate set can't resolve into two, and blocking on surname soundex or
postcode ahead of the pairwise comparison. `_completeness()` gets rewritten to score
which fields are populated rather than summing string lengths. On auditability: return
each source Patient's demographics separately alongside the merged view and expose the
score, not just the evidence strings, so a clinician can drop back to the unmerged
records and judge for themselves. Today the UI tells you a merge happened; it doesn't
let you undo it visually. I'd do the auditability half first — a wrong merge you can see
is recoverable, and a better scoring rule you have to trust blindly is not obviously an
improvement on a worse one you can inspect.

**Property-based tests.** Hypothesis strategies generating resources across the
status × date-precision × reference-validity space, asserting invariants rather than
examples: nothing marked `entered-in-error` ever reaches the response, the loader never
raises, `sortKey` never serialises, and a section's `state` is always consistent with
its item and withheld counts. That covers combinations I didn't think to write
fixtures for, which is the category that worries me most.

**Accessibility.** An axe-core pass over the rendered page — there's no CI to hang it
off yet, which is its own gap — a contrast audit of the amber and red badge tones,
and a screen-reader pass over the `<details>` disclosures and the badge semantics.
Badges carry text rather than relying on colour alone, but none of it has been tested
with assistive technology.

**Observability beyond logging.** Withholding decisions are logged; the next step is a
request id correlating one summary build to all of its decisions, and a counter per
withholding rule so an operator can see a feed suddenly start dropping records instead
of discovering it from a clinician.

**Multi-patient and a real source.** `/api/v1/patients/{id}/summary`, the bundle loader
behind an interface so a file, an API and a database are interchangeable, and cache
invalidation that isn't "restart the process".
