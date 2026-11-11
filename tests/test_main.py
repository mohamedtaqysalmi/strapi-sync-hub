from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from strapi_sync_hub.errors import ConfigError
from strapi_sync_hub.main import create_app_from_env

MAPPING = """\
content_types:
  article:
    index: articles
    fields: [title]
"""


def test_app_from_env_serves_health_and_rejects_bad_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mapping = tmp_path / "mapping.yaml"
    mapping.write_text(MAPPING, encoding="utf-8")
    monkeypatch.setenv("STRAPI_SYNC_SECRET", "a-secret-of-sufficient-length")
    monkeypatch.setenv("STRAPI_SYNC_TARGET", "meilisearch")
    monkeypatch.setenv("MEILISEARCH_URL", "http://meili.invalid:7700")
    monkeypatch.setenv("MEILISEARCH_API_KEY", "fake-key")
    monkeypatch.setenv("STRAPI_SYNC_MAPPING", str(mapping))
    client = TestClient(create_app_from_env())
    assert client.get("/healthz").status_code == 200
    bad = client.post("/webhook", json={}, headers={"X-Sync-Secret": "nope"})
    assert bad.status_code == 403


def test_webhook_target_can_be_built_from_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mapping = tmp_path / "mapping.yaml"
    mapping.write_text(MAPPING, encoding="utf-8")
    monkeypatch.setenv("STRAPI_SYNC_SECRET", "a-secret-of-sufficient-length")
    monkeypatch.setenv("STRAPI_SYNC_TARGET", "webhook")
    monkeypatch.setenv("WEBHOOK_TARGET_URL", "http://sink.invalid/ingest")
    monkeypatch.setenv("STRAPI_SYNC_MAPPING", str(mapping))
    assert TestClient(create_app_from_env()).get("/healthz").status_code == 200


def test_startup_fails_fast_on_bad_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STRAPI_SYNC_SECRET", raising=False)
    monkeypatch.delenv("STRAPI_SYNC_TARGET", raising=False)
    with pytest.raises(ConfigError):
        create_app_from_env()
