"""Seed: fire Strapi-shaped webhooks at the hub, then print reindex hint."""

from __future__ import annotations

import os
import sys
import time

import httpx

SECRET = os.environ.get("SYNC_SECRET", "demo-secret-at-least-16")
HUB = os.environ.get("SYNC_HUB_URL", "http://sync-hub:8000/webhook")
STRAPI = os.environ.get("STRAPI_URL", "http://strapi:1337")

EVENTS = [
    {
        "event": "entry.publish",
        "createdAt": "2025-03-01T09:00:00.120Z",
        "model": "article",
        "uid": "api::article.article",
        "entry": {
            "id": 1,
            "documentId": "demoarticle00000000000001",
            "title": "Harbor lights in Tangier",
            "slug": "harbor-lights-tangier",
            "body": "A short demo article used by the sync-hub compose stack.",
            "createdAt": "2025-03-01T09:00:00.000Z",
            "updatedAt": "2025-03-01T09:00:00.000Z",
            "publishedAt": "2025-03-01T09:00:00.000Z",
        },
    },
    {
        "event": "entry.publish",
        "createdAt": "2025-03-02T10:00:00.120Z",
        "model": "article",
        "uid": "api::article.article",
        "entry": {
            "id": 2,
            "documentId": "demoarticle00000000000002",
            "title": "Atlas trail notes",
            "slug": "atlas-trail-notes",
            "body": "Second seeded article for Meilisearch indexing.",
            "createdAt": "2025-03-02T10:00:00.000Z",
            "updatedAt": "2025-03-02T10:00:00.000Z",
            "publishedAt": "2025-03-02T10:00:00.000Z",
        },
    },
]


def wait_for(url: str, attempts: int = 30) -> None:
    for i in range(attempts):
        try:
            response = httpx.get(url, timeout=2.0)
            if response.status_code < 500:
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)
        print(f"waiting for {url} ({i + 1}/{attempts})", flush=True)
    raise SystemExit(f"timed out waiting for {url}")


def main() -> int:
    wait_for(f"{STRAPI.rstrip('/')}/health")
    wait_for(HUB.replace("/webhook", "/healthz"))
    headers = {"X-Sync-Secret": SECRET}
    with httpx.Client(timeout=10.0) as client:
        for event in EVENTS:
            response = client.post(HUB, json=event, headers=headers)
            print(event["entry"]["slug"], response.status_code, response.text, flush=True)
            response.raise_for_status()
    print("seed complete; documents should be in Meilisearch index 'articles'", flush=True)
    print("optional reindex: docker compose exec sync-hub strapi-sync-hub reindex", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
