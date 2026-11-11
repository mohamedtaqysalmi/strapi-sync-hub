import json
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from strapi_sync_hub.errors import TargetError
from strapi_sync_hub.targets import JsonWebhookTarget, MeilisearchTarget, Outcome, parse_timestamp

T1 = datetime(2025, 3, 1, 9, 0, tzinfo=UTC)
T2 = datetime(2025, 3, 2, 9, 0, tzinfo=UTC)


class FakeMeilisearch:
    """Stands in for the three Meilisearch endpoints the target uses. Not a real server."""

    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}
        self.requests: list[httpx.Request] = []
        self.missing_index = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.missing_index:
            return httpx.Response(404, json={"code": "index_not_found"})
        if request.method == "POST":
            for doc in json.loads(request.content):
                self.docs[doc["id"]] = doc
            return httpx.Response(202, json={"taskUid": 1})
        doc_id = request.url.path.rsplit("/", 1)[-1]
        if request.method == "GET":
            if doc_id not in self.docs:
                return httpx.Response(404, json={"code": "document_not_found"})
            return httpx.Response(
                200, json={"_source_updated_at": self.docs[doc_id]["_source_updated_at"]}
            )
        self.docs.pop(doc_id, None)
        return httpx.Response(202, json={"taskUid": 2})


def meili(handler: Any) -> MeilisearchTarget:
    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://meili.test")
    return MeilisearchTarget(client)


def test_parse_timestamp_handles_z_suffix_and_naive_values() -> None:
    assert parse_timestamp("2025-03-01T09:00:00.100Z") == datetime(
        2025, 3, 1, 9, 0, 0, 100000, tzinfo=UTC
    )
    assert parse_timestamp("2025-03-01T09:00:00").tzinfo is UTC


def test_meilisearch_upsert_is_idempotent() -> None:
    fake = FakeMeilisearch()
    target = meili(fake)
    assert target.upsert("articles", "a1", {"title": "T"}, T1) is Outcome.APPLIED
    after_first = dict(fake.docs)
    assert target.upsert("articles", "a1", {"title": "T"}, T1) is Outcome.SKIPPED_STALE
    assert fake.docs == after_first
    assert fake.docs["a1"]["_source_updated_at"] == T1.isoformat()


def test_meilisearch_older_event_does_not_overwrite_newer_document() -> None:
    fake = FakeMeilisearch()
    target = meili(fake)
    target.upsert("articles", "a1", {"title": "new"}, T2)
    assert target.upsert("articles", "a1", {"title": "old"}, T1) is Outcome.SKIPPED_STALE
    assert fake.docs["a1"]["title"] == "new"


def test_meilisearch_newer_event_replaces_document() -> None:
    fake = FakeMeilisearch()
    target = meili(fake)
    target.upsert("articles", "a1", {"title": "old"}, T1)
    assert target.upsert("articles", "a1", {"title": "new"}, T2) is Outcome.APPLIED
    assert fake.docs["a1"]["title"] == "new"


def test_meilisearch_upsert_sends_primary_key_and_escapes_ids() -> None:
    fake = FakeMeilisearch()
    meili(fake).upsert("articles", "a/1", {"title": "T"}, T1)
    get, post = fake.requests
    assert get.url.raw_path.split(b"?")[0] == b"/indexes/articles/documents/a%2F1"
    assert get.url.params["fields"] == "_source_updated_at"
    assert post.url.params["primaryKey"] == "id"


def test_meilisearch_delete_is_idempotent_and_tolerates_missing_index() -> None:
    fake = FakeMeilisearch()
    target = meili(fake)
    target.upsert("articles", "a1", {"title": "T"}, T1)
    assert target.delete("articles", "a1") is Outcome.APPLIED
    assert target.delete("articles", "a1") is Outcome.APPLIED
    assert fake.docs == {}
    fake.missing_index = True
    assert target.delete("articles", "a1") is Outcome.APPLIED


def test_meilisearch_document_without_version_is_overwritten() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={})
        return httpx.Response(202, json={})

    assert meili(handler).upsert("articles", "a1", {}, T1) is Outcome.APPLIED


def test_meilisearch_error_status_raises_target_error() -> None:
    target = meili(lambda request: httpx.Response(500, text="boom"))
    with pytest.raises(TargetError, match="returned 500"):
        target.delete("articles", "a1")


def test_meilisearch_network_failure_raises_target_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with pytest.raises(TargetError, match="request failed"):
        meili(handler).delete("articles", "a1")


def webhook_target(handler: Any, token: str | None = None) -> JsonWebhookTarget:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return JsonWebhookTarget("http://sink.test/ingest", client, token=token)


def test_webhook_posts_upsert_payload_with_idempotency_key_and_token() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200)

    target = webhook_target(handler, token="tok")
    assert target.upsert("articles", "a1", {"id": "a1"}, T1) is Outcome.APPLIED
    request = seen[0]
    assert json.loads(request.content) == {
        "action": "upsert",
        "index": "articles",
        "id": "a1",
        "updatedAt": T1.isoformat(),
        "document": {"id": "a1"},
    }
    assert request.headers["Idempotency-Key"] == f"articles:a1:{T1.isoformat()}"
    assert request.headers["Authorization"] == "Bearer tok"


def test_webhook_skips_repeated_and_older_versions() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(200)

    target = webhook_target(handler)
    target.upsert("articles", "a1", {}, T2)
    assert target.upsert("articles", "a1", {}, T2) is Outcome.SKIPPED_STALE
    assert target.upsert("articles", "a1", {}, T1) is Outcome.SKIPPED_STALE
    assert len(calls) == 1


def test_webhook_failed_post_does_not_record_version() -> None:
    responses = iter([httpx.Response(500), httpx.Response(200)])
    target = webhook_target(lambda request: next(responses))
    with pytest.raises(TargetError, match="returned 500"):
        target.upsert("articles", "a1", {}, T1)
    assert target.upsert("articles", "a1", {}, T1) is Outcome.APPLIED


def test_webhook_delete_posts_delete_action() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(204)

    assert webhook_target(handler).delete("articles", "a1") is Outcome.APPLIED
    assert json.loads(seen[0].content) == {"action": "delete", "index": "articles", "id": "a1"}
    assert seen[0].headers["Idempotency-Key"] == "articles:a1:delete"
    assert "Authorization" not in seen[0].headers


def test_webhook_network_failure_raises_target_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with pytest.raises(TargetError, match="request failed"):
        webhook_target(handler).delete("articles", "a1")
