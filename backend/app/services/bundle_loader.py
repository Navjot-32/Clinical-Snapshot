"""Bundle loading: parse every resource independently so one bad entry cannot
take down the summary. Anything that fails is recorded, never swallowed."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from app.models.fhir import (
    AllergyIntolerance,
    Bundle,
    Condition,
    Encounter,
    MedicationRequest,
    Observation,
    Patient,
    RESOURCE_MODELS,
)


@dataclass
class ParseFailure:
    resource_type: Optional[str]
    resource_id: Optional[str]
    reason: str


@dataclass
class LoadedBundle:
    timestamp: Optional[str] = None
    patients: List[Patient] = field(default_factory=list)
    encounters: List[Encounter] = field(default_factory=list)
    conditions: List[Condition] = field(default_factory=list)
    observations: List[Observation] = field(default_factory=list)
    medications: List[MedicationRequest] = field(default_factory=list)
    allergies: List[AllergyIntolerance] = field(default_factory=list)
    index: Dict[str, Any] = field(default_factory=dict)
    failures: List[ParseFailure] = field(default_factory=list)

    def resolve(self, reference: Optional[str]) -> Optional[Any]:
        """Resolve a 'ResourceType/id' reference, or None if it points nowhere."""
        if not reference:
            return None
        return self.index.get(reference)


_COLLECTIONS = {
    "Patient": "patients",
    "Encounter": "encounters",
    "Condition": "conditions",
    "Observation": "observations",
    "MedicationRequest": "medications",
    "AllergyIntolerance": "allergies",
}


def load_bundle(path: Path) -> LoadedBundle:
    loaded = LoadedBundle()

    try:
        raw = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        loaded.failures.append(ParseFailure(None, None, f"bundle could not be read: {exc}"))
        return loaded

    try:
        bundle = Bundle.model_validate(raw)
    except ValidationError as exc:
        loaded.failures.append(ParseFailure("Bundle", None, f"bundle envelope invalid: {exc.error_count()} error(s)"))
        return loaded

    loaded.timestamp = bundle.timestamp

    for entry in bundle.entry:
        resource = entry.resource
        if not resource:
            loaded.failures.append(ParseFailure(None, None, "bundle entry contained no resource"))
            continue

        resource_type = resource.get("resourceType")
        resource_id = resource.get("id")

        model = RESOURCE_MODELS.get(resource_type)
        if model is None:
            loaded.failures.append(
                ParseFailure(resource_type, resource_id, f"resource type not modelled: {resource_type}")
            )
            continue

        try:
            parsed = model.model_validate(resource)
        except ValidationError as exc:
            first = exc.errors()[0]
            location = ".".join(str(p) for p in first["loc"])
            loaded.failures.append(
                ParseFailure(resource_type, resource_id, f"failed validation at '{location}': {first['msg']}")
            )
            continue

        getattr(loaded, _COLLECTIONS[resource_type]).append(parsed)
        loaded.index[f"{resource_type}/{parsed.id}"] = parsed

    return loaded


_CACHE: Dict[str, LoadedBundle] = {}


def get_cached_bundle(path: Path) -> LoadedBundle:
    """Parse the bundle once per path and reuse it.

    The bundle is a static file, so re-reading and re-validating it on every request
    buys nothing. Cached by path so tests pointing at fixtures are unaffected.
    """
    key = str(path)
    if key not in _CACHE:
        _CACHE[key] = load_bundle(path)
    return _CACHE[key]


def clear_bundle_cache() -> None:
    _CACHE.clear()
