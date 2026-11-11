from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict

from strapi_sync_hub.errors import EventError
from strapi_sync_hub.mapping import VERSION_FIELD, MappingConfig
from strapi_sync_hub.targets import Outcome, Target, parse_timestamp

UPSERT_EVENTS = frozenset({"entry.create", "entry.update", "entry.publish"})
DELETE_EVENTS = frozenset({"entry.delete", "entry.unpublish"})


class StrapiEvent(BaseModel):
    model_config = ConfigDict(extra="allow")

    event: str
    model: str
    entry: dict[str, Any] = {}


@dataclass(frozen=True)
class SyncResult:
    status: str
    detail: str = ""


def handle_event(event: StrapiEvent, mapping: MappingConfig, target: Target) -> SyncResult:
    if event.event not in UPSERT_EVENTS | DELETE_EVENTS:
        return SyncResult("ignored", f"event '{event.event}' is not handled")
    content_type = mapping.get(event.model)
    if content_type is None:
        return SyncResult("ignored", f"no mapping for content type '{event.model}'")

    doc_id = content_type.document_id(event.entry)

    if event.event in DELETE_EVENTS:
        target.delete(content_type.index, doc_id)
        return SyncResult("applied", f"removed {content_type.index}/{doc_id}")

    # Strapi 5 also fires entry.update for drafts. Those must not become searchable.
    if "publishedAt" in event.entry and event.entry["publishedAt"] is None:
        return SyncResult("skipped", "entry is an unpublished draft")

    raw_updated_at = event.entry.get("updatedAt")
    if not isinstance(raw_updated_at, str):
        raise EventError(
            f"content type '{event.model}': field 'updatedAt' is missing from the entry"
        )
    try:
        updated_at = parse_timestamp(raw_updated_at)
    except ValueError as exc:
        raise EventError(
            f"content type '{event.model}': field 'updatedAt' is not an ISO timestamp: "
            f"{raw_updated_at!r}"
        ) from exc

    document = content_type.build_document(event.entry)
    document[VERSION_FIELD] = updated_at.isoformat()
    outcome = target.upsert(content_type.index, doc_id, document, updated_at)
    if outcome is Outcome.SKIPPED_STALE:
        return SyncResult("skipped", "target already holds this version or a newer one")
    return SyncResult("applied", f"upserted {content_type.index}/{doc_id}")
