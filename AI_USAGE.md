# AI Usage

I kept notes as I went instead of writing this at the end, so a few of the entries
below are things I got wrong in front of the model rather than the other way round.

## What I used

Claude Code in the VS Code extension for the whole build. Sonnet 5 for planning,
scaffolding, test generation and the routine implementation. Opus 5 for reviewing the
plan and for anything where being wrong ends up in front of a clinician.

Swapping between the two on purpose was probably the highest-leverage thing I did all
day. Having one model review another model's plan, while the plan was still just a
document, caught more than any individual code review later did.

## Where it helped

Cataloguing the bundle's defects. Seventeen resources, each one needing a check for
missing `display`, dangling references, error statuses, inconsistent date precision.
That's an hour of careful, boring reading and it's exactly what I want to hand off.

Scaffolding — venv, pinned requirements, FastAPI skeleton, `create-next-app`, health
check green end to end. Maybe forty minutes of typing I didn't have to do.

The tests. Once I'd settled the disposition rules, generating the 120 tests across
dates, status buckets, merge behaviour, resilience and the API went fast and was mostly
right first time.

And reading documentation it couldn't have memorised. Next.js 16 is newer than the
model's training data and ships its own docs inside `node_modules`; pointing it at
those rather than letting it answer from memory caught two real problems, below.

None of that is interesting. The rest of this file is the part I'd want to be judged on.

## Where I overrode it

### It merged a mother and her daughter into one patient

The model wrote this code. I read it, approved it, and it was wrong for most of the
build.

There are two Patient records in the bundle that are obviously the same woman. The
rule the model produced counted how many fields agreed between two records and merged
if enough of them did, with any outright contradiction blocking the merge. Sensible
enough. Works on this bundle.

I caught it writing the README. The tradeoffs section made me state the rule in
English, and in English it reads: *merge two records if two fields agree and nothing
contradicts*. Now picture a mother and daughter at one address. Same surname, same
gender, same address, and suppose one of the two records is missing a birth date, which
is common enough in real feeds. Three agreements. Nothing contradicts. They merge, and
one of them inherits the other's medication list.

Every field was worth the same. That's the bug. Name, gender and address tell you about
a household; only a birth date or a medical record number tells you about a person. I
wrote the failing case as a test before touching the rule, then added one clause:

```python
matched = len(evidence) >= 2 and not conflicts                           # before
matched = identity_signals >= 1 and len(evidence) >= 2 and not conflicts # after
```

The real pair still merges — it agrees on birth date and shares an MRN root, so it has
two identity signals rather than none. `test_relatives_at_one_address_are_not_merged`
holds the bug down and `test_the_bundles_merge_rests_on_two_identity_signals` covers
the other direction, so someone tightening this later can't quietly stop the genuine
match from working.

Worth saying that the mother-and-daughter case isn't in the bundle. I made it up. But
the whole reason I rejected the model's first plan on status handling was that it coded
to the five values that happen to appear in the sample when the brief says the defect
list isn't exhaustive, and matching deserves the same treatment. A rule that only has
to survive the seventeen resources you were handed isn't a rule.

The uncomfortable part is that the model was fluent enough to produce something that
passed my review and passed its own test suite. Writing it down in prose is what caught
it. Code review didn't.

### I wouldn't let it name the unlabelled codes

Four codings turn up with a system and a code and no display text: `E11.9`, LOINC
`4548-4`, RxNorm `849574`, SNOMED `91936005`. Filling those in makes the page
dramatically more readable and takes about two minutes.

I asked the model about `91936005` directly. It gave me a probable answer and, in the
same breath, told me its recall of SNOMED identifiers isn't good enough to put in front
of a clinician. I took the second half of that answer. Unnamed codes render as
`E11.9 · ICD-10-CM` with a marker saying the source didn't name them.

This cost me something real and I'd rather say so than pretend it was free. Readability
is one of the things being marked and `4548-4 · LOINC` is not readable. It also means I
can't detect that two records describe the same concept under different codings, which
is live in this bundle — `allergyintolerance-001` and `-003` might both be penicillin,
and they disagree about severity.

### The same thing again, on blood pressure, where it was harder to resist

`observation-001` holds systolic 138 and diastolic 88 in `component[]`. To print
`138/88` you have to know which is which. Print them backwards and you get `88/138`,
which isn't a warning sign, it's an impossible reading that someone might act on.

The obvious fix is to hardcode LOINC `8480-6` as systolic. I nearly did it, and it
would have been the same code-to-meaning assertion I'd just refused to make, from the
same unreliable memory, except with no marker and no gap to give it away. The
components get ordered from the display text the bundle itself provides, falling back
to source order, and both are always listed under the combined value so a bad ordering
is at least visible. There's a test pinning the value to `138/88`.

### Its first plan would have shipped something unsafe

Before writing any code I had Opus review Sonnet's plan against the actual bundle.
Three findings were serious enough to change the design:

The plan filtered error-status resources and rendered whatever survived. Filter every
allergy record and you get an empty allergies box, which a clinician reads as "no known
allergies" — a clinical claim. The honest version is "allergy records exist and none
could be shown", which is a data problem. Nothing in the plan distinguished the two.
That's now a four-valued state on every section and it's the decision I'd defend
hardest.

It also correctly excluded `observation-004`, a creatinine of 14.7 mg/dL marked
`entered-in-error`, and then proposed listing excluded records in a notes panel.
Implement that the obvious way and 14.7 goes straight back on screen in a footnote. The
notes carry a record id and a rule name, nothing else, and there are two tests checking
that `14.7` appears nowhere in the response or the logs.

And the status handling was written to the sample rather than the spec, so a `refuted`
condition or a `cancelled` medication would have sailed through as current fact.

Two smaller ones from the same review: recency was going to be computed against
`datetime.now()`, which makes output drift and tests non-deterministic, and the merge
used field precedence, which silently drops a phone number when one record has a home
number and the other a mobile.

### I made it show me the page

For most of the build I had no way to look at the frontend, and the model telling me
the markup was fine is not evidence of anything. Eventually I drove the already-installed
Chrome in headless mode to produce screenshots and actually looked.

Three defects were obvious within about five seconds that TypeScript, a production
build and every HTML assertion had waved through: long codes breaking mid-token across
lines (`LOINC 85354-` on one line, `9` on the next), a category label wrapping onto two
lines, and the withheld-record count styled so quietly that the one thing the panel
exists to say was the easiest thing on it to miss.

### Smaller corrections

- **Calendar-impossible dates.** The date parser matched on shape, so `"2021-02-30"`
  came out as "30 Feb 2021" and `"2019-13-45"` as "45 13 2019". Inventing a date that
  can't exist is the exact thing the precision handling was there to prevent.
- **Staleness on the wrong kind of date.** A 2021 hypertension *onset* got flagged
  stale. "This may no longer reflect the patient" is a reasonable thing to say about an
  HbA1c and a meaningless thing to say about a diagnosis date, where it reads as doubt
  about the diagnosis itself.
- **Rejected matches vanishing.** The merge recorded why it merged records and threw
  away why it rejected them, so a genuinely different second patient would have
  disappeared with no note at all.
- **A refactor estimate I didn't take on trust.** Asked to restructure
  `summary_builder.py`, it predicted 503 lines would become about 320. The file is 541.
  It counted the duplication it was removing and not the shared machinery it was adding
  to remove it. I kept the change because the structure genuinely is better, but the
  file's length is written up as a tradeoff rather than described as a cleanup.
- **Prerendering.** The page was being built as static, so the summary was fetched once
  during `next build` and frozen — including the error state, if the API had been down
  at that moment. No error, no warning. It showed up as a single character in the build
  output.

## How I caught these

Three habits did most of the work, and they matter more than any individual catch:

**A golden baseline.** Before any refactor I dumped the full API response to a file and
diffed against it afterwards. Every structural change in this project is provably
behaviour-preserving, and the one time the diff came back non-empty it was a field I'd
deliberately removed. That's what let me accept large model-written refactors without
reading every line.

**Tests that assert absence.** `14.7` never appears. `sortKey` never serialises. No
clinical value reaches a log line. They're awkward to write and they're the only ones
that catch a leak.

**Writing it down.** Both the merge bug and a contradiction in the README surfaced while
I was explaining the system rather than while I was reading it. You can skim past a rule
that doesn't hold. You can't write it out in a sentence and not notice.

## What I'm still trusting

`_completeness()` picks the primary record in a merge by adding the *string length* of a
birth date to a count of populated fields, so that a full date outranks a bare year. It
works here. It also mixes units in a way I'd reject in review if someone else had
written it, and I left it because the merge is already gated by the identity rule and I
had better uses for the remaining hours. It's named in the README tradeoffs rather than
left for someone to find.

Bigger one: those 120 tests are mostly model-written. I chose what to assert and I read
them, but a suite written by the same thing that wrote the code inherits its blind
spots, and I have direct evidence of it. Seventeen tests covering patient matching, and not
one of them thought to try two people living at the same address.
