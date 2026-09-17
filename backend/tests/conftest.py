import json
from pathlib import Path

import pytest

from app.core import config
from app.services.bundle_loader import load_bundle
from app.services.summary_builder import build_summary


@pytest.fixture(scope="session")
def raw_bundle() -> dict:
    return json.loads(config.BUNDLE_PATH.read_text())


@pytest.fixture(scope="session")
def summary():
    return build_summary(load_bundle(config.BUNDLE_PATH))


@pytest.fixture
def bundle_file(tmp_path):
    def _write(payload: dict) -> Path:
        path = tmp_path / "bundle.json"
        path.write_text(json.dumps(payload))
        return path

    return _write
