import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from strapi_sync_hub.errors import EventError, MappingError

# Written into every synced document so a later event can be compared against it.
VERSION_FIELD = "_source_updated_at"
RESERVED_TARGET_FIELDS = frozenset({"id", VERSION_FIELD})

_INDEX_NAME = re.compile(r"^[A-Za-z0-9_-]+$")
_CONTENT_TYPE_KEYS = {"index", "id_field", "fields"}


@dataclass(frozen=True)
class ContentTypeMapping:
    content_type: str
    index: str
    id_field: str
    fields: dict[str, str]

    def document_id(self, entry: dict[str, Any]) -> str:
        value = entry.get(self.id_field)
        if value is None or isinstance(value, bool) or not isinstance(value, str | int):
            raise EventError(
                f"content type '{self.content_type}': id field '{self.id_field}' "
                "is missing from the entry or is not a string or integer"
            )
        return str(value)

    def build_document(self, entry: dict[str, Any]) -> dict[str, Any]:
        # Strapi leaves out relations that were not populated, so absent fields are skipped.
        document = {dst: entry[src] for src, dst in self.fields.items() if src in entry}
        document["id"] = self.document_id(entry)
        return document


@dataclass(frozen=True)
class MappingConfig:
    content_types: dict[str, ContentTypeMapping]

    def get(self, model: str) -> ContentTypeMapping | None:
        return self.content_types.get(model)


def load_mapping(path: Path) -> MappingConfig:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise MappingError(f"cannot read mapping file {path}: {exc.strerror or exc}") from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise MappingError(f"{path} is not valid YAML: {exc}") from exc
    return parse_mapping(raw)


def parse_mapping(raw: object) -> MappingConfig:
    errors: list[str] = []
    if not isinstance(raw, dict) or not isinstance(raw.get("content_types"), dict):
        raise MappingError("mapping must be a YAML mapping with a 'content_types' mapping")
    unknown = set(raw) - {"content_types"}
    if unknown:
        errors.append(f"unknown top-level keys: {sorted(map(str, unknown))}")

    result: dict[str, ContentTypeMapping] = {}
    for name, body in raw["content_types"].items():
        parsed = _parse_content_type(name, body, errors)
        if parsed is not None:
            result[parsed.content_type] = parsed
    if not raw["content_types"]:
        errors.append("'content_types' is empty")
    if errors:
        raise MappingError("invalid mapping:\n" + "\n".join(f"  - {e}" for e in errors))
    return MappingConfig(content_types=result)


def _parse_content_type(name: object, body: object, errors: list[str]) -> ContentTypeMapping | None:
    if not isinstance(name, str) or not name:
        errors.append(f"content type names must be non-empty strings, got {name!r}")
        return None
    before = len(errors)
    prefix = f"content type '{name}'"
    if not isinstance(body, dict):
        errors.append(f"{prefix}: expected a mapping with 'index' and 'fields'")
        return None
    unknown = set(body) - _CONTENT_TYPE_KEYS
    if unknown:
        errors.append(f"{prefix}: unknown keys {sorted(map(str, unknown))}")

    index = body.get("index")
    if not isinstance(index, str) or not _INDEX_NAME.match(index):
        errors.append(f"{prefix}: 'index' must be a string of letters, digits, '-' and '_'")
    id_field = body.get("id_field", "id")
    if not isinstance(id_field, str) or not id_field:
        errors.append(f"{prefix}: 'id_field' must be a non-empty string")
    fields = _parse_fields(name, body.get("fields"), errors)

    if len(errors) > before:
        return None
    assert isinstance(index, str)
    assert isinstance(id_field, str)
    return ContentTypeMapping(content_type=name, index=index, id_field=id_field, fields=fields)


def _parse_fields(name: str, raw: object, errors: list[str]) -> dict[str, str]:
    prefix = f"content type '{name}'"
    pairs: list[tuple[object, object]]
    if isinstance(raw, list):
        pairs = [(item, None) for item in raw]
    elif isinstance(raw, dict):
        pairs = list(raw.items())
    else:
        errors.append(f"{prefix}: 'fields' must be a list of names or a source: target mapping")
        return {}
    if not pairs:
        errors.append(f"{prefix}: 'fields' must not be empty")

    fields: dict[str, str] = {}
    seen: set[str] = set()
    for source, target in pairs:
        if not isinstance(source, str) or not source:
            errors.append(f"{prefix}: field names must be non-empty strings, got {source!r}")
            continue
        final = source if target is None else target
        if not isinstance(final, str) or not final:
            errors.append(f"{prefix}: field '{source}': target name must be a non-empty string")
        elif final in RESERVED_TARGET_FIELDS:
            errors.append(f"{prefix}: field '{source}': target name '{final}' is reserved")
        elif final in seen:
            errors.append(f"{prefix}: field '{source}': target name '{final}' is used twice")
        else:
            seen.add(final)
            fields[source] = final
    return fields
