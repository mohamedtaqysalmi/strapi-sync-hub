from datetime import datetime
from typing import Any

import httpx
import pytest

from strapi_sync_hub.cli import main
from strapi_sync_hub.dry_run import DryRunTarget
from strapi_sync_hub.errors import EventError, TargetError
from strapi_sync_hub.mapping import MappingConfig, parse_mapping
from strapi_sync_hub.reindex import fetch_published_entries, reindex
from strapi_sync_hub.targets import Outcome


class MemoryTarget:
    def __init__(self) -> None:
        self.docs: dict[tuple[str, str], dict[str, Any]] = {}

    def upsert(
        self, index: str, doc_id: str, document: dict[str, Any], updated_at: datetime
    ) -> Outcome:
        self.docs[(index, doc_id)] = document
        return Outcome.APPLIED

    def delete(self, index: str, doc_id: str) -> Outcome:
        self.docs.pop((index, doc_id), None)
        return Outcome.APPLIED


def _page(entries: list[dict[str, Any]], page: int = 1, page_count: int = 1) -> dict[str, Any]:
    return {
        "data": entries,
        "meta": {"pagination": {"page": page, "pageSize": 100, "pageCount": page_count}},
    }


def test_fetch_published_entries_flattens_strapi4_attributes() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "status=published" in str(request.url):
            return httpx.Response(400, json={"error": {"message": "unknown"}})
        return httpx.Response(
            200,
            json=_page(
                [
                    {
                        "id": 1,
                        "attributes": {
                            "title": "A",
                            "updatedAt": "2025-03-01T09:00:00.000Z",
                            "publishedAt": "2025-03-01T09:00:00.000Z",
                        },
                    }
                ]
            ),
        )

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://strapi.test")
    entries = fetch_published_entries(client, "articles")
    assert entries[0]["title"] == "A"
    assert entries[0]["id"] == 1


def test_reindex_upserts_published_entries(mapping: MappingConfig) -> None:
    payload = _page(
        [
            {
                "id": 7,
                "documentId": "k3x9p0zq1v7w2m4n5b6c8d9e",
                "title": "Hello from Rabat",
                "slug": "hello-from-rabat",
                "body": "First post.",
                "updatedAt": "2025-03-01T09:00:00.100Z",
                "publishedAt": "2025-03-01T09:00:00.100Z",
            }
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    target = MemoryTarget()
    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://strapi.test")
    summary = reindex(mapping, target, client, content_types=["article"])
    assert summary.scanned == 1
    assert summary.applied == 1
    doc = target.docs[("articles", "k3x9p0zq1v7w2m4n5b6c8d9e")]
    assert doc["title"] == "Hello from Rabat"
    assert doc["content"] == "First post."


def test_reindex_dry_run_plans_without_writing(mapping: MappingConfig) -> None:
    payload = _page(
        [
            {
                "documentId": "abc",
                "title": "T",
                "slug": "t",
                "body": "B",
                "updatedAt": "2025-03-01T09:00:00.000Z",
                "publishedAt": "2025-03-01T09:00:00.000Z",
            }
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    target = DryRunTarget()
    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://strapi.test")
    summary = reindex(mapping, target, client)
    assert summary.applied == 1
    assert target.actions[0].action == "upsert"
    assert target.actions[0].doc_id == "abc"


def test_reindex_unknown_content_type_raises() -> None:
    mapping = parse_mapping(
        {"content_types": {"article": {"index": "articles", "fields": ["title"]}}}
    )
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _r: httpx.Response(500)),
        base_url="http://strapi.test",
    )
    with pytest.raises(EventError, match="no mapping"):
        reindex(mapping, DryRunTarget(), client, content_types=["missing"])


def test_fetch_propagates_http_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="unavailable")

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://strapi.test")
    with pytest.raises(TargetError, match="503"):
        fetch_published_entries(client, "articles")


def test_cli_version() -> None:
    assert main(["version"]) == 0


def test_cli_reindex_requires_strapi_url(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    mapping_path = tmp_path / "mapping.yaml"
    mapping_path.write_text(
        "content_types:\n  article:\n    index: articles\n    fields: [title]\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("STRAPI_SYNC_SECRET", "a-secret-of-sufficient-length")
    monkeypatch.setenv("STRAPI_SYNC_TARGET", "meilisearch")
    monkeypatch.setenv("MEILISEARCH_URL", "http://meili.invalid:7700")
    monkeypatch.setenv("STRAPI_SYNC_MAPPING", str(mapping_path))
    monkeypatch.delenv("STRAPI_URL", raising=False)
    assert main(["reindex", "--dry-run"]) == 2
