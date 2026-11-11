# strapi-sync-hub

A small FastAPI service that receives Strapi webhook events and syncs content to Meilisearch or a generic JSON webhook target.

**Status: v0.1.0.** Receiver, YAML mapping, idempotent upserts, retries with backoff, dead-letter JSONL, dry-run, full-reindex CLI, and a docker-compose demo are in place. Contract fixtures are still hand-written from Strapi docs (not recorded from a live instance). The compose “Strapi” service is a stand-in that speaks the same Content API / webhook envelope.

## What works

- `POST /webhook` accepts Strapi `entry.create`, `entry.update`, `entry.publish`, `entry.unpublish` and `entry.delete` events.
- Shared secret in a header (default `X-Sync-Secret`), compared in constant time.
- YAML maps each content type to a target index, field renames, document id field, and optional `api_id` for reindex.
- Meilisearch and JSON webhook targets with idempotent upserts (`_source_updated_at`).
- Retries with exponential backoff; exhausted failures append to a dead-letter JSONL file and return `dead_lettered`.
- `STRAPI_SYNC_DRY_RUN=true` and `strapi-sync-hub reindex --dry-run` plan writes without calling the target.
- `strapi-sync-hub reindex` pulls published entries from a Strapi Content API and upserts them.
- Docker demo: Meilisearch + stand-in CMS + hub + seed (`demo/`).
- Pages site with an in-browser mapping generator: https://mohamedtaqysalmi.github.io/strapi-sync-hub/

## What is still open

- Ordering guarantees across restarts for the webhook target (in-memory latest `updatedAt`).
- Concurrent deliveries of the same document to Meilisearch can race.
- Meilisearch task success is not awaited (queue acceptance only).
- An update after a delete can resurrect a document.
- Dead-letter replay CLI and recorded live-Strapi fixtures.

## Configuration

See [.env.example](.env.example). Mapping example: [mapping.example.yaml](mapping.example.yaml).

| Variable | Meaning |
| --- | --- |
| `STRAPI_SYNC_SECRET` | Shared secret, at least 16 characters |
| `STRAPI_SYNC_SECRET_HEADER` | Header carrying the secret, default `X-Sync-Secret` |
| `STRAPI_SYNC_MAPPING` | Path to the mapping YAML, default `mapping.yaml` |
| `STRAPI_SYNC_TARGET` | `meilisearch` or `webhook` |
| `MEILISEARCH_URL`, `MEILISEARCH_API_KEY` | Meilisearch target |
| `WEBHOOK_TARGET_URL`, `WEBHOOK_TARGET_TOKEN` | JSON webhook target |
| `STRAPI_SYNC_MAX_RETRIES` | Attempts per target call, default `3` |
| `STRAPI_SYNC_RETRY_BASE_SECONDS` | Backoff base, default `0.5` |
| `STRAPI_SYNC_DEAD_LETTER_PATH` | JSONL path, default `dead-letter.jsonl` |
| `STRAPI_SYNC_DRY_RUN` | `true` to plan only |
| `STRAPI_URL`, `STRAPI_API_TOKEN` | Used by `reindex` |

## Running

```bash
cp .env.example .env
uvicorn --factory strapi_sync_hub.main:create_app_from_env
strapi-sync-hub reindex --dry-run
```

Demo stack:

```bash
cd demo
docker compose up --build
```

## Tests

```bash
pip install -e ".[dev]"
ruff check .
ruff format --check .
mypy
pytest
```

Coverage fails below 85%. See [QA.md](QA.md) and [TEST_REPORT.md](TEST_REPORT.md).

## License

MIT, see [LICENSE](LICENSE).
