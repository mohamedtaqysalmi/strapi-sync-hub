from pathlib import Path

import pytest

from strapi_sync_hub.config import Settings
from strapi_sync_hub.errors import ConfigError

VALID = {
    "STRAPI_SYNC_SECRET": "a-secret-of-sufficient-length",
    "STRAPI_SYNC_TARGET": "meilisearch",
    "MEILISEARCH_URL": "http://localhost:7700",
}


def test_valid_meilisearch_settings_with_defaults() -> None:
    settings = Settings.from_env(VALID)
    assert settings.target == "meilisearch"
    assert settings.secret_header == "X-Sync-Secret"
    assert settings.mapping_file == Path("mapping.yaml")
    assert settings.meilisearch_api_key is None
    assert settings.max_retries == 3
    assert settings.retry_base_seconds == 0.5
    assert settings.dead_letter_path == Path("dead-letter.jsonl")
    assert settings.dry_run is False


def test_retry_and_dry_run_overrides() -> None:
    settings = Settings.from_env(
        {
            **VALID,
            "STRAPI_SYNC_MAX_RETRIES": "5",
            "STRAPI_SYNC_RETRY_BASE_SECONDS": "0.1",
            "STRAPI_SYNC_DEAD_LETTER_PATH": "dlq/events.jsonl",
            "STRAPI_SYNC_DRY_RUN": "true",
            "STRAPI_URL": "http://localhost:1337",
            "STRAPI_API_TOKEN": "tok",
        }
    )
    assert settings.max_retries == 5
    assert settings.retry_base_seconds == 0.1
    assert settings.dead_letter_path == Path("dlq/events.jsonl")
    assert settings.dry_run is True
    assert settings.strapi_url == "http://localhost:1337"
    assert settings.strapi_api_token == "tok"


def test_valid_webhook_settings_with_overrides() -> None:
    env = {
        "STRAPI_SYNC_SECRET": VALID["STRAPI_SYNC_SECRET"],
        "STRAPI_SYNC_TARGET": "webhook",
        "WEBHOOK_TARGET_URL": "https://example.test/ingest",
        "WEBHOOK_TARGET_TOKEN": "tok",
        "STRAPI_SYNC_SECRET_HEADER": "X-Other",
        "STRAPI_SYNC_MAPPING": "custom.yaml",
    }
    settings = Settings.from_env(env)
    assert settings.target == "webhook"
    assert settings.webhook_target_token == "tok"
    assert settings.secret_header == "X-Other"
    assert settings.mapping_file == Path("custom.yaml")


def test_reads_process_environment_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in VALID.items():
        monkeypatch.setenv(key, value)
    assert Settings.from_env().meilisearch_url == "http://localhost:7700"


def test_all_problems_are_reported_at_once() -> None:
    with pytest.raises(ConfigError) as excinfo:
        Settings.from_env({})
    text = str(excinfo.value)
    assert "STRAPI_SYNC_SECRET is required" in text
    assert "STRAPI_SYNC_TARGET must be" in text


def test_short_secret_is_rejected() -> None:
    with pytest.raises(ConfigError, match="at least 16 characters"):
        Settings.from_env({**VALID, "STRAPI_SYNC_SECRET": "short"})


def test_target_url_is_required_for_chosen_target() -> None:
    env = {k: v for k, v in VALID.items() if k != "MEILISEARCH_URL"}
    with pytest.raises(ConfigError, match="MEILISEARCH_URL is required"):
        Settings.from_env(env)


def test_url_must_be_http() -> None:
    with pytest.raises(ConfigError, match="MEILISEARCH_URL must be an http"):
        Settings.from_env({**VALID, "MEILISEARCH_URL": "localhost:7700"})
