import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from strapi_sync_hub.errors import ConfigError

MIN_SECRET_LENGTH = 16


@dataclass(frozen=True)
class Settings:
    webhook_secret: str
    secret_header: str
    mapping_file: Path
    target: Literal["meilisearch", "webhook"]
    meilisearch_url: str | None
    meilisearch_api_key: str | None
    webhook_target_url: str | None
    webhook_target_token: str | None
    max_retries: int
    retry_base_seconds: float
    dead_letter_path: Path
    dry_run: bool
    strapi_url: str | None
    strapi_api_token: str | None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        source = os.environ if env is None else env
        errors: list[str] = []

        def get(name: str, default: str | None = None) -> str | None:
            value = source.get(name, "").strip()
            return value or default

        def url(name: str, required: bool) -> str | None:
            value = get(name)
            if value is None:
                if required:
                    errors.append(f"{name} is required")
                return None
            parsed = urlparse(value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                errors.append(f"{name} must be an http(s) URL")
            return value

        def positive_int(name: str, default: int) -> int:
            raw = get(name)
            if raw is None:
                return default
            try:
                value = int(raw)
            except ValueError:
                errors.append(f"{name} must be an integer")
                return default
            if value < 1:
                errors.append(f"{name} must be >= 1")
                return default
            return value

        def non_negative_float(name: str, default: float) -> float:
            raw = get(name)
            if raw is None:
                return default
            try:
                value = float(raw)
            except ValueError:
                errors.append(f"{name} must be a number")
                return default
            if value < 0:
                errors.append(f"{name} must be >= 0")
                return default
            return value

        secret = get("STRAPI_SYNC_SECRET")
        if secret is None:
            errors.append("STRAPI_SYNC_SECRET is required")
        elif len(secret) < MIN_SECRET_LENGTH:
            errors.append(f"STRAPI_SYNC_SECRET must be at least {MIN_SECRET_LENGTH} characters")

        target = get("STRAPI_SYNC_TARGET")
        if target not in {"meilisearch", "webhook"}:
            errors.append("STRAPI_SYNC_TARGET must be 'meilisearch' or 'webhook'")

        meili_url = url("MEILISEARCH_URL", required=target == "meilisearch")
        webhook_url = url("WEBHOOK_TARGET_URL", required=target == "webhook")
        strapi_url = url("STRAPI_URL", required=False)

        dry_raw = (get("STRAPI_SYNC_DRY_RUN", "false") or "false").lower()
        if dry_raw not in {"true", "false", "1", "0", "yes", "no"}:
            errors.append("STRAPI_SYNC_DRY_RUN must be true or false")
        dry_run = dry_raw in {"true", "1", "yes"}

        if errors:
            raise ConfigError("invalid configuration:\n" + "\n".join(f"  - {e}" for e in errors))
        assert secret is not None
        return cls(
            webhook_secret=secret,
            secret_header=get("STRAPI_SYNC_SECRET_HEADER", "X-Sync-Secret") or "X-Sync-Secret",
            mapping_file=Path(get("STRAPI_SYNC_MAPPING", "mapping.yaml") or "mapping.yaml"),
            target="meilisearch" if target == "meilisearch" else "webhook",
            meilisearch_url=meili_url,
            meilisearch_api_key=get("MEILISEARCH_API_KEY"),
            webhook_target_url=webhook_url,
            webhook_target_token=get("WEBHOOK_TARGET_TOKEN"),
            max_retries=positive_int("STRAPI_SYNC_MAX_RETRIES", 3),
            retry_base_seconds=non_negative_float("STRAPI_SYNC_RETRY_BASE_SECONDS", 0.5),
            dead_letter_path=Path(
                get("STRAPI_SYNC_DEAD_LETTER_PATH", "dead-letter.jsonl") or "dead-letter.jsonl"
            ),
            dry_run=dry_run,
            strapi_url=strapi_url,
            strapi_api_token=get("STRAPI_API_TOKEN"),
        )
