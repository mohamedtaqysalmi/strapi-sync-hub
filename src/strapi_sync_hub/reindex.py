"""Pull published entries from a Strapi Content API and upsert them into the target."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

from strapi_sync_hub.errors import EventError, TargetError
from strapi_sync_hub.mapping import VERSION_FIELD, MappingConfig
from strapi_sync_hub.service import SyncResult
from strapi_sync_hub.targets import Outcome, Target, parse_timestamp

logger = logging.getLogger(__name__)

PAGE_SIZE = 100


@dataclass(frozen=True)
class ReindexSummary:
    scanned: int = 0
    applied: int = 0
    skipped: int = 0
    failed: int = 0


def fetch_published_entries(
    client: httpx.Client,
    api_id: str,
    *,
    page_size: int = PAGE_SIZE,
) -> list[dict[str, Any]]:
    """GET /api/{api_id} with publicationState=live (Strapi 4) / status=published (Strapi 5).

    Tries Strapi 5 query params first, then falls back to Strapi 4 naming. Pagination follows
    the ``meta.pagination`` object when present; otherwise a single page is assumed.
    """
    entries: list[dict[str, Any]] = []
    page = 1
    path = f"/api/{quote(api_id, safe='')}"
    while True:
        params: dict[str, str | int] = {
            "pagination[page]": page,
            "pagination[pageSize]": page_size,
            "status": "published",
        }
        response = _get(client, path, params)
        if response.status_code == 400:
            params = {
                "pagination[page]": page,
                "pagination[pageSize]": page_size,
                "publicationState": "live",
            }
            response = _get(client, path, params)
        if response.is_error:
            raise TargetError(
                f"strapi returned {response.status_code} for GET {path}: {response.text[:200]}"
            )
        body = response.json()
        batch = body.get("data")
        if not isinstance(batch, list):
            raise TargetError(f"strapi GET {path}: expected 'data' to be a list")
        for item in batch:
            entries.append(_normalize_entry(item))
        meta_raw = body.get("meta")
        meta: dict[str, Any] = meta_raw if isinstance(meta_raw, dict) else {}
        pagination_raw = meta.get("pagination")
        pagination: dict[str, Any] = pagination_raw if isinstance(pagination_raw, dict) else {}
        page_count = pagination.get("pageCount")
        if not isinstance(page_count, int) or page >= page_count:
            break
        page += 1
    return entries


def reindex(
    mapping: MappingConfig,
    target: Target,
    client: httpx.Client,
    *,
    content_types: list[str] | None = None,
) -> ReindexSummary:
    """Fetch each mapped content type from Strapi and upsert published documents."""
    selected = content_types or sorted(mapping.content_types)
    scanned = applied = skipped = failed = 0

    for name in selected:
        ctype = mapping.get(name)
        if ctype is None:
            raise EventError(f"no mapping for content type '{name}'")
        api_id = ctype.api_id
        logger.info("reindex: fetching %s via /api/%s", name, api_id)
        try:
            entries = fetch_published_entries(client, api_id)
        except TargetError:
            raise

        for entry in entries:
            scanned += 1
            try:
                result = _upsert_entry(name, entry, mapping, target)
            except (EventError, TargetError) as exc:
                failed += 1
                logger.error("reindex failed for %s: %s", name, exc)
                continue
            if result.status == "applied":
                applied += 1
            else:
                skipped += 1

    return ReindexSummary(scanned=scanned, applied=applied, skipped=skipped, failed=failed)


def _upsert_entry(
    model: str, entry: dict[str, Any], mapping: MappingConfig, target: Target
) -> SyncResult:
    ctype = mapping.get(model)
    assert ctype is not None
    if "publishedAt" in entry and entry["publishedAt"] is None:
        return SyncResult("skipped", "entry is an unpublished draft")
    raw_updated_at = entry.get("updatedAt")
    if not isinstance(raw_updated_at, str):
        raise EventError(f"content type '{model}': field 'updatedAt' is missing from the entry")
    updated_at = parse_timestamp(raw_updated_at)
    document = ctype.build_document(entry)
    document[VERSION_FIELD] = updated_at.isoformat()
    doc_id = ctype.document_id(entry)
    outcome = target.upsert(ctype.index, doc_id, document, updated_at)
    if outcome is Outcome.SKIPPED_STALE:
        return SyncResult("skipped", "target already holds this version or a newer one")
    return SyncResult("applied", f"upserted {ctype.index}/{doc_id}")


def _normalize_entry(item: object) -> dict[str, Any]:
    """Flatten Strapi 4 ``{id, attributes}`` wrappers; pass Strapi 5 flat entries through."""
    if not isinstance(item, dict):
        raise TargetError("strapi entry is not an object")
    attrs = item.get("attributes")
    if isinstance(attrs, dict):
        flat = dict(attrs)
        if "id" in item and "id" not in flat:
            flat["id"] = item["id"]
        if "documentId" in item and "documentId" not in flat:
            flat["documentId"] = item["documentId"]
        return flat
    return item


def _get(client: httpx.Client, path: str, params: dict[str, str | int]) -> httpx.Response:
    try:
        return client.get(path, params=params)
    except httpx.HTTPError as exc:
        raise TargetError(f"strapi request failed: {exc}") from exc
