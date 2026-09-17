from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["bundle_present"] is True


def test_patient_summary_returns_camel_case_payload():
    response = client.get("/patient-summary")
    assert response.status_code == 200
    body = response.json()
    assert {"asOf", "patient", "problems", "medications", "allergies", "encounters", "observations", "dataQuality"} <= set(body)


def test_every_section_declares_a_state():
    body = client.get("/patient-summary").json()
    for section in ("problems", "medications", "allergies", "encounters", "observations"):
        assert body[section]["state"] in {"populated", "none-in-source", "all-withheld", "partially-withheld"}


def test_response_is_stable_across_requests():
    """Output is anchored to the bundle timestamp, so repeated calls must agree."""
    assert client.get("/patient-summary").json() == client.get("/patient-summary").json()


def test_readiness_reports_parsed_resources():
    response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["resources"] == 17
    assert body["unparsed"] == 0


def test_unhandled_error_is_an_explicit_failure_not_empty_data(monkeypatch):
    """A server fault must never be indistinguishable from a patient who simply has
    no recorded problems."""
    from app.routers import patient_summary as router_module

    def boom(_):
        raise RuntimeError("internal detail that must not reach the client")

    monkeypatch.setattr(router_module, "build_summary", boom)
    failing = TestClient(app, raise_server_exceptions=False)

    response = failing.get("/patient-summary")
    assert response.status_code == 500
    body = response.json()
    assert body["error"] == "summary_unavailable"
    assert "not an empty record" in body["message"]
    # The cause belongs in the log, not the response.
    assert "internal detail" not in response.text


def test_bundle_is_parsed_once_and_reused():
    from app.core import config
    from app.services.bundle_loader import clear_bundle_cache, get_cached_bundle

    clear_bundle_cache()
    first = get_cached_bundle(config.BUNDLE_PATH)
    second = get_cached_bundle(config.BUNDLE_PATH)
    assert first is second


def test_every_withheld_record_is_logged():
    """The data-quality panel and the audit log are fed from one call, so they
    cannot drift apart."""
    import logging

    from app.core import config
    from app.core.logging import logger
    from app.services.bundle_loader import load_bundle
    from app.services.summary_builder import build_summary

    captured = []

    class Capture(logging.Handler):
        def emit(self, record):
            captured.append(record)

    handler = Capture()
    logger.addHandler(handler)
    try:
        summary = build_summary(load_bundle(config.BUNDLE_PATH))
    finally:
        logger.removeHandler(handler)

    withheld = [r for r in captured if r.getMessage() == "clinical_record_withheld"]
    assert len(withheld) == len(summary.data_quality.notes)
    assert all(hasattr(r, "resource_id") and hasattr(r, "reason") for r in withheld)


def test_logs_carry_no_clinical_values():
    """observation-004 is withheld for being entered-in-error; its 14.7 mg/dL value
    must not be reintroduced through the log stream."""
    import logging

    from app.core import config
    from app.core.logging import logger
    from app.services.bundle_loader import load_bundle
    from app.services.summary_builder import build_summary

    captured = []

    class Capture(logging.Handler):
        def emit(self, record):
            captured.append(self.format(record))

    handler = Capture()
    handler.setFormatter(logging.Formatter("%(message)s %(resource_id)s %(reason)s"))
    logger.addHandler(handler)
    try:
        build_summary(load_bundle(config.BUNDLE_PATH))
    finally:
        logger.removeHandler(handler)

    assert not any("14.7" in line for line in captured)
