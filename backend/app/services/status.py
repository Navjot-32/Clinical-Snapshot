"""Status classification against the full FHIR R4 value sets.

Written against the specification rather than the values that happen to appear in
one bundle: a `refuted` condition or a `cancelled` medication must not reach the
screen as current fact even though neither occurs in the sample.

Unrecognised statuses fail safe, and "safe" is directional. For conditions,
medications, observations and encounters it means withholding. For allergies it
means the opposite — an allergy is shown even when its status is unintelligible,
because omitting one is the dangerous failure.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from app.models.summary import Flag, FlagCode


class Disposition(str, Enum):
    EXCLUDE = "exclude"
    CURRENT = "current"
    HISTORICAL = "historical"


@dataclass
class StatusVerdict:
    disposition: Disposition
    reason: Optional[str] = None
    flags: List[Flag] = field(default_factory=list)


_ERROR_VERIFICATION = {"entered-in-error", "refuted"}
_UNCONFIRMED_VERIFICATION = {"unconfirmed", "provisional", "differential"}

_CONDITION_CURRENT = {"active", "recurrence", "relapse"}
_CONDITION_HISTORICAL = {"inactive", "remission", "resolved"}

_MEDICATION_ORDER_INTENTS = {"order", "original-order", "reflex-order", "filler-order", "instance-order"}

_ALLERGY_CURRENT = {"active"}
_ALLERGY_HISTORICAL = {"inactive", "resolved"}


def classify_condition(clinical: Optional[str], verification: Optional[str]) -> StatusVerdict:
    if verification in _ERROR_VERIFICATION:
        return StatusVerdict(Disposition.EXCLUDE, f"condition verification status is '{verification}'")

    flags: List[Flag] = []
    if verification in _UNCONFIRMED_VERIFICATION:
        flags.append(Flag(code=FlagCode.UNCONFIRMED, detail=f"verification status is '{verification}'"))

    if clinical in _CONDITION_CURRENT:
        return StatusVerdict(Disposition.CURRENT, flags=flags)
    if clinical in _CONDITION_HISTORICAL:
        return StatusVerdict(Disposition.HISTORICAL, flags=flags)

    flags.append(Flag(code=FlagCode.UNRECOGNISED_STATUS, detail=f"clinical status is '{clinical or 'absent'}'"))
    return StatusVerdict(Disposition.HISTORICAL, flags=flags)


def classify_medication(status: Optional[str], intent: Optional[str]) -> StatusVerdict:
    if intent is not None and intent not in _MEDICATION_ORDER_INTENTS:
        return StatusVerdict(Disposition.EXCLUDE, f"medication intent is '{intent}', not an actual order")

    if status in {"entered-in-error", "cancelled"}:
        return StatusVerdict(Disposition.EXCLUDE, f"medication status is '{status}'")
    if status == "draft":
        return StatusVerdict(Disposition.EXCLUDE, "medication order is a draft and was never issued")

    if status == "active":
        return StatusVerdict(Disposition.CURRENT)
    if status == "on-hold":
        return StatusVerdict(
            Disposition.CURRENT,
            flags=[Flag(code=FlagCode.UNCONFIRMED, detail="order is on hold")],
        )
    if status in {"stopped", "completed", "ended"}:
        return StatusVerdict(Disposition.HISTORICAL)

    return StatusVerdict(
        Disposition.HISTORICAL,
        flags=[Flag(code=FlagCode.UNRECOGNISED_STATUS, detail=f"medication status is '{status or 'absent'}'")],
    )


def classify_observation(status: Optional[str]) -> StatusVerdict:
    if status in {"entered-in-error", "cancelled"}:
        return StatusVerdict(Disposition.EXCLUDE, f"observation status is '{status}'")
    if status == "registered":
        return StatusVerdict(Disposition.EXCLUDE, "observation is registered but has no result yet")

    if status in {"final", "amended", "corrected"}:
        return StatusVerdict(Disposition.CURRENT)
    if status == "preliminary":
        return StatusVerdict(
            Disposition.CURRENT,
            flags=[Flag(code=FlagCode.UNCONFIRMED, detail="result is preliminary")],
        )

    return StatusVerdict(
        Disposition.HISTORICAL,
        flags=[Flag(code=FlagCode.UNRECOGNISED_STATUS, detail=f"observation status is '{status or 'absent'}'")],
    )


def classify_encounter(status: Optional[str]) -> StatusVerdict:
    if status in {"entered-in-error", "cancelled"}:
        return StatusVerdict(Disposition.EXCLUDE, f"encounter status is '{status}'")
    if status == "planned":
        return StatusVerdict(Disposition.EXCLUDE, "encounter is planned and has not occurred")

    if status == "finished":
        return StatusVerdict(Disposition.HISTORICAL)
    if status in {"in-progress", "arrived", "triaged", "onleave"}:
        return StatusVerdict(Disposition.CURRENT)

    return StatusVerdict(Disposition.EXCLUDE, f"encounter status is unrecognised: '{status or 'absent'}'")


def classify_allergy(clinical: Optional[str], verification: Optional[str]) -> StatusVerdict:
    if verification in _ERROR_VERIFICATION:
        return StatusVerdict(Disposition.EXCLUDE, f"allergy verification status is '{verification}'")

    flags: List[Flag] = []
    if verification in _UNCONFIRMED_VERIFICATION:
        flags.append(Flag(code=FlagCode.UNCONFIRMED, detail=f"verification status is '{verification}'"))

    if clinical in _ALLERGY_CURRENT:
        return StatusVerdict(Disposition.CURRENT, flags=flags)
    if clinical in _ALLERGY_HISTORICAL:
        return StatusVerdict(Disposition.HISTORICAL, flags=flags)

    # The inversion. Elsewhere an unintelligible status withholds the record;
    # here it is still shown, because a missed allergy is the worse error.
    flags.append(Flag(code=FlagCode.UNRECOGNISED_STATUS, detail=f"clinical status is '{clinical or 'absent'}'"))
    return StatusVerdict(Disposition.CURRENT, flags=flags)
