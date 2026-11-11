"""Append-only JSONL dead-letter log for events that exhausted retries."""

from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class DeadLetterLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def record(self, *, event: dict[str, Any], error: str, detail: str = "") -> None:
        entry = {
            "recorded_at": datetime.now(UTC).isoformat(),
            "error": error,
            "detail": detail,
            "event": event,
        }
        line = json.dumps(entry, ensure_ascii=False, default=str) + "\n"
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line)
        logger.error("dead-lettered event to %s: %s", self.path, error)
