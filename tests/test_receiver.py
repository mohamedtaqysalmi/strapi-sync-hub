"""Receiver tests, including the contract test against the hand-written Strapi payloads.

The payloads in tests/fixtures are written from the Strapi docs, not recorded from a running
Strapi. These tests show the receiver handles that shape; they do not prove it matches what a
real instance sends.
"""

from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from strapi_sync_hub.app import create_app
from strapi_sync_hub.errors import TargetError
from strapi_sync_hub.mapping import MappingConfig
from strapi_sync_hub.targets import Outcome

SECRET = "a-secret-of-sufficient-length"
HEADER = "X-Sync-Secret"


class MemoryTarget:
    """Keeps documents in a dict and applies the same stale rule as the real targets."""

    def __init__(self) -> None:
        self.docs: dict[tuple[str, str], dict[str, Any]] = {}
        self.versions: dict[tuple[str, str], datetime] = {}
        self.fail = False

    def upsert(
        self, index: str, doc_id: str, document: dict[str, Any], updated_at: datetime
    ) -> Outcome:
        if self.fail:
            raise TargetError("down")
        key = (index, doc_id)
        if key in self.versions and updated_at <= self.versions[key]:
            return Outcome.SKIPPED_STALE
        self.docs[key] = document
        self.versions[key] = updated_at
        return Outcome.APPLIED

    def delete(self, index: str, doc_id: str) -> Outcome:
        if self.fail:
            raise TargetError("down")
        self.docs.pop((index, doc_id), None)
        self.versions.pop((index, doc_id), None)
        return Outcome.APPLIED


@pytest.fixture
def target() -> MemoryTarget:
    return MemoryTarget()


@pytest.fixture
def client(mapping: MappingConfig, target: MemoryTarget) -> TestClient:
    app = create_app(secret=SECRET, secret_header=HEADER, mapping=mapping, target=target)
    return TestClient(app)


def post(client: TestClient, payload: dict[str, Any], secret: str | None = SECRET) -> Any:
    headers = {HEADER: secret} if secret is not None else {}
    return client.post("/webhook", json=payload, headers=headers)


def test_healthz_needs_no_secret(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}


def test_missing_secret_is_rejected_before_the_body_is_read(client: TestClient) -> None:
    response = client.post("/webhook", content=b"not json")
    assert response.status_code == 401
    assert HEADER in response.json()["detail"]


def test_wrong_secret_is_rejected(client: TestClient, events: Any, target: MemoryTarget) -> None:
    response = post(client, events["entry.create"], secret="wrong-secret-value-here")
    assert response.status_code == 403
    assert target.docs == {}


def test_malformed_body_with_valid_secret_is_422(client: TestClient) -> None:
    assert post(client, {"nonsense": True}).status_code == 422


def test_create_event_syncs_mapped_document(
    client: TestClient, events: Any, target: MemoryTarget
) -> None:
    response = post(client, events["entry.create"])
    assert response.status_code == 200
    assert response.json()["status"] == "applied"
    doc = target.docs[("articles", "k3x9p0zq1v7w2m4n5b6c8d9e")]
    assert doc["title"] == "Hello from Rabat"
    assert doc["content"] == "First post."
    assert "body" not in doc
    assert "createdAt" not in doc
    assert doc["_source_updated_at"] == "2025-03-01T09:00:00.100000+00:00"


def test_same_event_twice_leaves_same_end_state(
    client: TestClient, events: Any, target: MemoryTarget
) -> None:
    post(client, events["entry.update"])
    state = dict(target.docs)
    second = post(client, events["entry.update"])
    assert second.json()["status"] == "skipped"
    assert target.docs == state


def test_older_update_does_not_overwrite_newer_document(
    client: TestClient, events: Any, target: MemoryTarget
) -> None:
    post(client, events["entry.update"])
    response = post(client, events["entry.create"])
    assert response.json()["status"] == "skipped"
    assert target.docs[("articles", "k3x9p0zq1v7w2m4n5b6c8d9e")]["title"].endswith("(edited)")


def test_draft_update_is_not_synced(client: TestClient, events: Any, target: MemoryTarget) -> None:
    response = post(client, events["entry.update.draft"])
    assert response.json() == {"status": "skipped", "detail": "entry is an unpublished draft"}
    assert target.docs == {}


def test_publish_then_unpublish_adds_then_removes_document(
    client: TestClient, events: Any, target: MemoryTarget
) -> None:
    post(client, events["entry.publish"])
    assert ("articles", "q1w2e3r4t5y6u7i8o9p0a1s2") in target.docs
    assert post(client, events["entry.unpublish"]).json()["status"] == "applied"
    assert target.docs == {}


def test_delete_removes_document_and_repeat_delete_is_harmless(
    client: TestClient, events: Any, target: MemoryTarget
) -> None:
    post(client, events["entry.create"])
    assert post(client, events["entry.delete"]).status_code == 200
    assert target.docs == {}
    assert post(client, events["entry.delete"]).status_code == 200
    assert target.docs == {}


def test_unmapped_content_type_is_ignored(
    client: TestClient, events: Any, target: MemoryTarget
) -> None:
    payload = {**events["entry.create"], "model": "comment"}
    response = post(client, payload)
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    assert target.docs == {}


def test_unhandled_event_type_is_ignored(client: TestClient, events: Any) -> None:
    payload = {**events["entry.create"], "event": "media.create"}
    assert post(client, payload).json()["status"] == "ignored"


def test_entry_without_id_field_is_422_naming_content_type_and_field(
    client: TestClient, events: Any
) -> None:
    del events["entry.create"]["entry"]["documentId"]
    response = post(client, events["entry.create"])
    assert response.status_code == 422
    assert "content type 'article'" in response.json()["detail"]
    assert "'documentId'" in response.json()["detail"]


@pytest.mark.parametrize("value", [None, "yesterday"])
def test_bad_updated_at_is_422(client: TestClient, events: Any, value: object) -> None:
    events["entry.create"]["entry"]["updatedAt"] = value
    response = post(client, events["entry.create"])
    assert response.status_code == 422
    assert "'updatedAt'" in response.json()["detail"]


def test_target_failure_is_502(client: TestClient, events: Any, target: MemoryTarget) -> None:
    target.fail = True
    assert post(client, events["entry.create"]).status_code == 502
    assert post(client, events["entry.delete"]).status_code == 502
