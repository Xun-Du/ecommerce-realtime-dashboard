"""Application logging configuration with machine-readable JSON records."""

import json
import logging
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    """Emit application log records as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in ("event", "start_time", "end_time", "experiment_group", "granularity"):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = str(value)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    """Configure the dashboard application logger once without changing Uvicorn logs."""
    logger = logging.getLogger("dashboard")
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
