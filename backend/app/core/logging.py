"""Structured logging for decisions that hide clinical data.

Every record withheld from the summary is emitted as a JSON line. The data-quality
panel in the UI is a view over these decisions, not the only record of them — in
production the reasoning has to be auditable without opening a browser.
"""

import json
import logging
import sys
from typing import Optional

LOGGER_NAME = "clinical_snapshot"

logger = logging.getLogger(LOGGER_NAME)

_RESERVED = set(
    logging.LogRecord(name="", level=0, pathname="", lineno=0, msg="", args=None, exc_info=None).__dict__
) | {"message", "asctime", "taskName"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record),
            "level": record.levelname.lower(),
            "event": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    if logger.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(level)
    # Own handler only; do not duplicate through uvicorn's root configuration.
    logger.propagate = False


def log_withheld(resource_type: str, resource_id: str, reason: str, section: Optional[str] = None) -> None:
    logger.warning(
        "clinical_record_withheld",
        extra={"resource_type": resource_type, "resource_id": resource_id, "reason": reason, "section": section},
    )


def log_summary_built(patient_id: str, withheld_total: int, unparsed_total: int, notes: int) -> None:
    logger.info(
        "patient_summary_built",
        extra={
            "patient_id": patient_id,
            "withheld_total": withheld_total,
            "unparsed_total": unparsed_total,
            "data_quality_notes": notes,
        },
    )
