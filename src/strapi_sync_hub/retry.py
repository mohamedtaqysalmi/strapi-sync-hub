"""Retry a target call with exponential backoff."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any, TypeVar

from strapi_sync_hub.errors import TargetError
from strapi_sync_hub.targets import Outcome, Target

logger = logging.getLogger(__name__)

T = TypeVar("T")


def call_with_retries(
    action: Callable[[], T],
    *,
    max_attempts: int,
    base_delay_seconds: float,
    sleep: Callable[[float], None] = time.sleep,
    label: str = "target",
) -> T:
    """Run ``action`` up to ``max_attempts`` times. Only ``TargetError`` is retried."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    last: TargetError | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return action()
        except TargetError as exc:
            last = exc
            if attempt == max_attempts:
                break
            delay = base_delay_seconds * (2 ** (attempt - 1))
            logger.warning(
                "%s failed (attempt %s/%s): %s; retrying in %.2fs",
                label,
                attempt,
                max_attempts,
                exc,
                delay,
            )
            sleep(delay)
    assert last is not None
    raise last


class RetryingTarget:
    """Wraps a Target and retries upsert/delete on TargetError."""

    def __init__(
        self,
        inner: Target,
        *,
        max_attempts: int = 3,
        base_delay_seconds: float = 0.5,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._inner = inner
        self._max_attempts = max_attempts
        self._base_delay_seconds = base_delay_seconds
        self._sleep = sleep

    def upsert(
        self, index: str, doc_id: str, document: dict[str, Any], updated_at: datetime
    ) -> Outcome:
        return call_with_retries(
            lambda: self._inner.upsert(index, doc_id, document, updated_at),
            max_attempts=self._max_attempts,
            base_delay_seconds=self._base_delay_seconds,
            sleep=self._sleep,
            label=f"upsert {index}/{doc_id}",
        )

    def delete(self, index: str, doc_id: str) -> Outcome:
        return call_with_retries(
            lambda: self._inner.delete(index, doc_id),
            max_attempts=self._max_attempts,
            base_delay_seconds=self._base_delay_seconds,
            sleep=self._sleep,
            label=f"delete {index}/{doc_id}",
        )
