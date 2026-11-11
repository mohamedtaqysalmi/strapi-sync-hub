"""The page's mapping generator must produce YAML that the real loader accepts.

site/generator.js is run under Node, so these tests are skipped where Node is not installed
(it is on the GitHub runners).
"""

import html
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from strapi_sync_hub.mapping import load_mapping

SITE = Path(__file__).parent.parent / "site"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

SCRIPT = """
const gen = require(process.argv[1]);
const inputs = JSON.parse(require("fs").readFileSync(0, "utf8"));
process.stdout.write(JSON.stringify(inputs.map((input) => gen.generate(input))));
"""

DEFAULTS = {
    "model": "article",
    "index": "articles",
    "apiId": "articles",
    "idField": "documentId",
    "fields": "title\nslug\nbody: content\npublishedAt: published_at",
}


def run_generator(inputs: list[dict[str, str]]) -> list[dict[str, Any]]:
    assert NODE is not None
    proc = subprocess.run(
        [NODE, "-e", SCRIPT, str(SITE / "generator.js")],
        input=json.dumps(inputs),
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8",
    )
    return json.loads(proc.stdout)  # type: ignore[no-any-return]


def load_yaml(tmp_path: Path, text: str) -> Any:
    path = tmp_path / "mapping.yaml"
    path.write_text(text, encoding="utf-8")
    return load_mapping(path)


def test_default_output_is_accepted_by_the_loader(tmp_path: Path) -> None:
    [result] = run_generator([DEFAULTS])
    assert result["problems"] == []
    article = load_yaml(tmp_path, result["yaml"]).get("article")
    assert article.index == "articles"
    assert article.api_id == "articles"
    assert article.id_field == "documentId"
    assert article.fields == {
        "title": "title",
        "slug": "slug",
        "body": "content",
        "publishedAt": "published_at",
    }


def test_values_that_yaml_would_misread_are_quoted(tmp_path: Path) -> None:
    [result] = run_generator(
        [
            {
                "model": "null",
                "index": "news-items",
                "apiId": "",
                "idField": "",
                "fields": "on\nyes: no\nseo.title: seo_title\nratio: 1e3\n2024: year",
            }
        ]
    )
    assert result["problems"] == []
    mapping = load_yaml(tmp_path, result["yaml"])
    news = mapping.get("null")
    assert news.api_id == "news-items"
    assert news.id_field == "id"
    assert news.fields == {
        "on": "on",
        "yes": "no",
        "seo.title": "seo_title",
        "ratio": "1e3",
        "2024": "year",
    }


def test_invalid_input_is_reported_and_no_yaml_is_produced() -> None:
    results = run_generator(
        [
            {**DEFAULTS, "index": "bad name"},
            {**DEFAULTS, "fields": "title: id"},
            {**DEFAULTS, "fields": "title\ntitle: other"},
            {**DEFAULTS, "fields": "a: x\nb: x"},
            {**DEFAULTS, "fields": ""},
            {**DEFAULTS, "model": ""},
        ]
    )
    assert all(result["yaml"] is None for result in results)
    messages = [result["problems"][0] for result in results]
    assert "index must be" in messages[0]
    assert "content type 'article': field 'title': target name 'id' is reserved" in messages[1]
    assert "field 'title' is listed twice" in messages[2]
    assert "target name 'x' is used twice" in messages[3]
    assert "add at least one field" in messages[4]
    assert "model is required" in messages[5]


def test_static_yaml_in_the_page_matches_the_generator_defaults(tmp_path: Path) -> None:
    page = (SITE / "index.html").read_text(encoding="utf-8")
    match = re.search(r'<pre id="yaml-out"><code>(.*?)</code></pre>', page, re.DOTALL)
    assert match is not None
    static = html.unescape(match.group(1))
    [result] = run_generator([DEFAULTS])
    assert static == result["yaml"]
    assert load_yaml(tmp_path, static).get("article") is not None
