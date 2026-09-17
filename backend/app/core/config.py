import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

BUNDLE_PATH = Path(os.getenv("BUNDLE_PATH", str(REPO_ROOT / "data" / "scenario1_fhir_bundle.json")))

FRONTEND_ORIGINS = os.getenv("FRONTEND_ORIGINS", "http://localhost:3000").split(",")
