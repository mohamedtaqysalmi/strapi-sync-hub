"""Strapi-shaped demo CMS for docker-compose. Not a real Strapi instance."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI

SEED_ARTICLES: list[dict[str, Any]] = [
    {
        "id": 1,
        "documentId": "demoarticle00000000000001",
        "title": "Harbor lights in Tangier",
        "slug": "harbor-lights-tangier",
        "body": "A short demo article used by the sync-hub compose stack.",
        "updatedAt": "2025-03-01T09:00:00.000Z",
        "publishedAt": "2025-03-01T09:00:00.000Z",
    },
    {
        "id": 2,
        "documentId": "demoarticle00000000000002",
        "title": "Atlas trail notes",
        "slug": "atlas-trail-notes",
        "body": "Second seeded article for Meilisearch indexing.",
        "updatedAt": "2025-03-02T10:00:00.000Z",
        "publishedAt": "2025-03-02T10:00:00.000Z",
    },
]

app = FastAPI(title="strapi-standin")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "kind": "strapi-standin"}


@app.get("/api/articles")
def list_articles() -> dict[str, Any]:
    return {
        "data": SEED_ARTICLES,
        "meta": {
            "pagination": {
                "page": 1,
                "pageSize": 100,
                "pageCount": 1,
                "total": len(SEED_ARTICLES),
            }
        },
    }


@app.get("/_meta")
def meta() -> dict[str, str]:
    return {
        "note": "This is a Strapi-shaped stand-in for the demo compose stack.",
        "generated_at": datetime.now(UTC).isoformat(),
    }
