import threading
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol
from urllib.parse import quote

import httpx

from strapi_sync_hub.errors import TargetError
from strapi_sync_hub.mapping import VERSION_FIELD


class Outcome(StrEnum):
    APPLIED = "applied"
    SKIPPED_STALE = "skipped_stale"


class Target(Protocol):
    def upsert(
        self, index: str, doc_id: str, document: dict[str, Any], updated_at: datetime
    ) -> Outcome: ...

    def delete(self, index: str, doc_id: str) -> Outcome: ...


def parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


class MeilisearchTarget:
    """Upserts into Meilisearch over its REST API.

    The stale check is a read followed by a write, so two concurrent deliveries for the same
    document can still race. Meilisearch also applies writes as asynchronous tasks; a 202 here
    means the task was queued, not that it succeeded.
    """

    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def upsert(
        self, index: str, doc_id: str, document: dict[str, Any], updated_at: datetime
    ) -> Outcome:
        existing = self._stored_version(index, doc_id)
        if existing is not None and updated_at <= existing:
            return Outcome.SKIPPED_STALE
        body = {**document, "id": doc_id, VERSION_FIELD: updated_at.isoformat()}
        self._send(
            "POST", f"/indexes/{quote(index, safe='')}/documents", json=[body], primaryKey="id"
        )
        return Outcome.APPLIED

    def delete(self, index: str, doc_id: str) -> Outcome:
        self._send(
            "DELETE",
            f"/indexes/{quote(index, safe='')}/documents/{quote(doc_id, safe='')}",
            allow_missing=True,
        )
        return Outcome.APPLIED

    def _stored_version(self, index: str, doc_id: str) -> datetime | None:
        path = f"/indexes/{quote(index, safe='')}/documents/{quote(doc_id, safe='')}"
        response = self._send("GET", path, allow_missing=True, fields=VERSION_FIELD)
        if response.status_code == 404:
            return None
        value = response.json().get(VERSION_FIELD)
        return parse_timestamp(value) if isinstance(value, str) else None

    def _send(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        allow_missing: bool = False,
        **params: str,
    ) -> httpx.Response:
        try:
            response = self._client.request(method, path, json=json, params=params or None)
        except httpx.HTTPError as exc:
            raise TargetError(f"meilisearch request failed: {exc}") from exc
        if response.status_code == 404 and allow_missing:
            return response
        if response.is_error:
            raise TargetError(
                f"meilisearch returned {response.status_code} for {method} {path}: "
                f"{response.text[:200]}"
            )
        return response


class JsonWebhookTarget:
    """Posts each change as JSON to a URL.

    Stale protection here only covers one process: the newest updatedAt seen per document is
    kept in memory and forgotten on restart. The receiving end should treat the
    Idempotency-Key header as the real deduplication key.
    """

    def __init__(self, url: str, client: httpx.Client, token: str | None = None) -> None:
        self._url = url
        self._client = client
        self._headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._latest: dict[tuple[str, str], datetime] = {}
        self._lock = threading.Lock()

    def upsert(
        self, index: str, doc_id: str, document: dict[str, Any], updated_at: datetime
    ) -> Outcome:
        key = (index, doc_id)
        with self._lock:
            seen = self._latest.get(key)
            if seen is not None and updated_at <= seen:
                return Outcome.SKIPPED_STALE
            self._post(
                {
                    "action": "upsert",
                    "index": index,
                    "id": doc_id,
                    "updatedAt": updated_at.isoformat(),
                    "document": document,
                },
                idempotency_key=f"{index}:{doc_id}:{updated_at.isoformat()}",
            )
            self._latest[key] = updated_at
        return Outcome.APPLIED

    def delete(self, index: str, doc_id: str) -> Outcome:
        self._post(
            {"action": "delete", "index": index, "id": doc_id},
            idempotency_key=f"{index}:{doc_id}:delete",
        )
        return Outcome.APPLIED

    def _post(self, payload: dict[str, Any], idempotency_key: str) -> None:
        headers = {**self._headers, "Idempotency-Key": idempotency_key}
        try:
            response = self._client.post(self._url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise TargetError(f"webhook target request failed: {exc}") from exc
        if response.is_error:
            raise TargetError(f"webhook target returned {response.status_code}")
