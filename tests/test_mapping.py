from pathlib import Path
from typing import Any

import pytest

from strapi_sync_hub.errors import EventError, MappingError
from strapi_sync_hub.mapping import load_mapping, parse_mapping

ROOT = Path(__file__).parent.parent


def test_example_mapping_file_is_valid() -> None:
    config = load_mapping(ROOT / "mapping.example.yaml")
    article = config.get("article")
    assert article is not None
    assert article.index == "articles"
    assert article.fields["body"] == "content"


def test_field_list_keeps_names_and_id_field_defaults_to_id() -> None:
    config = parse_mapping({"content_types": {"page": {"index": "pages", "fields": ["title"]}}})
    page = config.get("page")
    assert page is not None
    assert page.id_field == "id"
    assert page.build_document({"id": 3, "title": "T", "other": "x"}) == {"title": "T", "id": "3"}


def test_build_document_renames_and_skips_absent_fields(mapping: Any) -> None:
    article = mapping.get("article")
    doc = article.build_document({"documentId": "abc", "title": "T", "body": "B", "secret": "no"})
    assert doc == {"title": "T", "content": "B", "id": "abc"}


def test_unmapped_model_returns_none(mapping: Any) -> None:
    assert mapping.get("nope") is None


@pytest.mark.parametrize("bad_id", [None, True, 1.5, [1]])
def test_document_id_rejects_unusable_values(mapping: Any, bad_id: object) -> None:
    with pytest.raises(EventError, match=r"content type 'article'.*'documentId'"):
        mapping.get("article").document_id({"documentId": bad_id})


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        (None, "content_types"),
        ({"content_types": {}}, "'content_types' is empty"),
        (
            {"content_types": {"a": {"index": "i", "fields": ["x"]}}, "extra": 1},
            "unknown top-level",
        ),
        ({"content_types": {"a": "nope"}}, "content type 'a': expected a mapping"),
        ({"content_types": {"a": {"fields": ["x"]}}}, "content type 'a': 'index' must be"),
        ({"content_types": {"a": {"index": "bad name", "fields": ["x"]}}}, "'index' must be"),
        ({"content_types": {"a": {"index": "i", "fields": ["x"], "idfield": "x"}}}, "unknown keys"),
        ({"content_types": {"a": {"index": "i", "id_field": "", "fields": ["x"]}}}, "'id_field'"),
        ({"content_types": {"a": {"index": "i"}}}, "'fields' must be a list"),
        ({"content_types": {"a": {"index": "i", "fields": []}}}, "'fields' must not be empty"),
        ({"content_types": {"a": {"index": "i", "fields": [1]}}}, "field names must be"),
        (
            {"content_types": {"a": {"index": "i", "fields": {"title": ""}}}},
            "content type 'a': field 'title': target name must be",
        ),
        (
            {"content_types": {"a": {"index": "i", "fields": {"title": "id"}}}},
            "content type 'a': field 'title': target name 'id' is reserved",
        ),
        (
            {"content_types": {"a": {"index": "i", "fields": {"t": "x", "u": "x"}}}},
            "content type 'a': field 'u': target name 'x' is used twice",
        ),
        ({"content_types": {1: {"index": "i", "fields": ["x"]}}}, "names must be non-empty"),
    ],
)
def test_invalid_mappings_name_the_problem(raw: object, message: str) -> None:
    with pytest.raises(MappingError, match=message):
        parse_mapping(raw)


def test_all_errors_are_reported_together() -> None:
    raw = {"content_types": {"a": {"fields": []}, "b": {"index": "ok", "fields": {"x": "id"}}}}
    with pytest.raises(MappingError) as excinfo:
        parse_mapping(raw)
    text = str(excinfo.value)
    assert "content type 'a'" in text
    assert "content type 'b': field 'x'" in text


def test_load_mapping_reports_missing_file(tmp_path: Path) -> None:
    with pytest.raises(MappingError, match="cannot read mapping file"):
        load_mapping(tmp_path / "missing.yaml")


def test_load_mapping_reports_bad_yaml(tmp_path: Path) -> None:
    path = tmp_path / "m.yaml"
    path.write_text("content_types: [unclosed", encoding="utf-8")
    with pytest.raises(MappingError, match="not valid YAML"):
        load_mapping(path)
