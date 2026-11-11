from datetime import UTC, datetime
from typing import Any

import pytest

from strapi_sync_hub.errors import TargetError
from strapi_sync_hub.retry import RetryingTarget, call_with_retries
from strapi_sync_hub.targets import Outcome

T1 = datetime(2025, 3, 1, 9, 0, tzinfo=UTC)


class FlakyTarget:
    def __init__(self, fails_before_success: int) -> None:
        self.fails_before_success = fails_before_success
        self.calls = 0
        self.docs: dict[str, dict[str, Any]] = {}

    def upsert(
        self, index: str, doc_id: str, document: dict[str, Any], updated_at: datetime
    ) -> Outcome:
        self.calls += 1
        if self.calls <= self.fails_before_success:
            raise TargetError("temporary")
        self.docs[doc_id] = document
        return Outcome.APPLIED

    def delete(self, index: str, doc_id: str) -> Outcome:
        self.calls += 1
        if self.calls <= self.fails_before_success:
            raise TargetError("temporary")
        self.docs.pop(doc_id, None)
        return Outcome.APPLIED


def test_call_with_retries_succeeds_after_transient_failures() -> None:
    sleeps: list[float] = []
    state = {"n": 0}

    def action() -> str:
        state["n"] += 1
        if state["n"] < 3:
            raise TargetError("nope")
        return "ok"

    assert (
        call_with_retries(action, max_attempts=3, base_delay_seconds=0.25, sleep=sleeps.append)
        == "ok"
    )
    assert sleeps == [0.25, 0.5]


def test_call_with_retries_raises_after_exhaustion() -> None:
    with pytest.raises(TargetError, match="still down"):
        call_with_retries(
            lambda: (_ for _ in ()).throw(TargetError("still down")),
            max_attempts=2,
            base_delay_seconds=0,
            sleep=lambda _d: None,
        )


def test_retrying_target_upserts_after_backoff() -> None:
    inner = FlakyTarget(fails_before_success=2)
    target = RetryingTarget(inner, max_attempts=3, base_delay_seconds=0, sleep=lambda _d: None)
    assert target.upsert("articles", "a1", {"title": "T"}, T1) is Outcome.APPLIED
    assert inner.calls == 3
    assert inner.docs["a1"]["title"] == "T"


def test_retrying_target_delete_surfaces_final_error() -> None:
    inner = FlakyTarget(fails_before_success=99)
    target = RetryingTarget(inner, max_attempts=2, base_delay_seconds=0, sleep=lambda _d: None)
    with pytest.raises(TargetError, match="temporary"):
        target.delete("articles", "a1")
    assert inner.calls == 2
