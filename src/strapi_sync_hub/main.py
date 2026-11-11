"""Entry point for uvicorn: ``uvicorn --factory strapi_sync_hub.main:create_app_from_env``."""

import httpx
from fastapi import FastAPI

from strapi_sync_hub.app import create_app
from strapi_sync_hub.config import Settings
from strapi_sync_hub.mapping import load_mapping
from strapi_sync_hub.targets import JsonWebhookTarget, MeilisearchTarget, Target

TIMEOUT_SECONDS = 10.0


def build_target(settings: Settings) -> Target:
    if settings.target == "meilisearch":
        assert settings.meilisearch_url is not None
        headers = (
            {"Authorization": f"Bearer {settings.meilisearch_api_key}"}
            if settings.meilisearch_api_key
            else {}
        )
        client = httpx.Client(
            base_url=settings.meilisearch_url, headers=headers, timeout=TIMEOUT_SECONDS
        )
        return MeilisearchTarget(client)
    assert settings.webhook_target_url is not None
    return JsonWebhookTarget(
        settings.webhook_target_url,
        httpx.Client(timeout=TIMEOUT_SECONDS),
        token=settings.webhook_target_token,
    )


def create_app_from_env() -> FastAPI:
    settings = Settings.from_env()
    return create_app(
        secret=settings.webhook_secret,
        secret_header=settings.secret_header,
        mapping=load_mapping(settings.mapping_file),
        target=build_target(settings),
    )
