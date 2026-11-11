# Demo stack

`docker compose up --build` from this directory starts:

1. **Meilisearch** on `:7700`
2. **strapi-standin** on `:1337` — a Strapi-shaped Content API, not a real Strapi
3. **sync-hub** on `:8000`
4. **seed** — posts two `entry.publish` webhooks, then exits

## Honesty note

A full Strapi bootstrap (admin user, content-type builder, SQLite volume) is heavier than this demo needs. The stand-in returns `/api/articles` in the same envelope the hub's reindex client expects, and fires webhook payloads matching the hand-written fixtures. Point `STRAPI_URL` at a real Strapi when you have one.

## Quick checks

```bash
curl -s http://localhost:8000/healthz
curl -s http://localhost:1337/api/articles | head
curl -s -H "Authorization: Bearer demomasterkeydemomasterkey12" \
  "http://localhost:7700/indexes/articles/documents"
```

Full reindex against the stand-in:

```bash
docker compose exec sync-hub strapi-sync-hub reindex
docker compose exec sync-hub strapi-sync-hub reindex --dry-run
```
