from fastapi import APIRouter

from app.core import config
from app.models.summary import PatientSummary
from app.services.bundle_loader import get_cached_bundle
from app.services.summary_builder import build_summary

router = APIRouter(tags=["summary"])


@router.get("/patient-summary", response_model=PatientSummary)
def patient_summary() -> PatientSummary:
    """The normalised, safe-to-display view of the bundle.

    The bundle is parsed once at startup and reused; normalization still runs per
    request so the summary logic stays stateless.
    """
    return build_summary(get_cached_bundle(config.BUNDLE_PATH))
