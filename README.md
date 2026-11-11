# strapi-sync-hub

A small FastAPI service that receives Strapi webhook events and syncs content to Meilisearch or a generic JSON webhook target.

**Status: early development.** The receiver, YAML mapping and idempotent upserts exist and are unit tested. It has not been run against a real Strapi or a real Meilisearch yet, and there are no retries, so treat it as unfinished.

## What works

- `POST /webhook` accepts Strapi `entry.create`, `entry.update`, `entry.publish`, `entry.unpublish` and `entry.delete` events.
- Each request must carry a shared secret in a header (default `X-Sync-Secret`). It is compared in constant time. A missing header gets 401, a wrong one 403.
- A YAML file maps each content type to a target index, picks and renames fields, and names the document id field. Validation errors name the content type and field.
- Targets: Meilisearch over its REST API, and a generic JSON webhook that receives `{action, index, id, updatedAt, document}` with an `Idempotency-Key` header.
- Upserts are idempotent. Every synced document carries `_source_updated_at`; an event whose `updatedAt` is not newer than what the target holds is skipped. Delivering the same event twice, or an old one after a new one, leaves the newer document in place.
- `entry.unpublish` and `entry.delete` remove the document. Deleting something already gone is fine.
- Drafts (`publishedAt` is null on a create, update or publish event) are skipped, so unpublished content does not become searchable.
- Events for content types that are not in the mapping, and other event types, are acknowledged and ignored.

## What is not built

- Retries with backoff and a dead-letter log. If the target is down the request fails with 502 and the event is lost.
- Full reindex, dry-run mode, and a docker-compose demo.
- Ordering guarantees across restarts for the webhook target: it remembers the newest `updatedAt` per document in memory only.
- Protection against concurrent deliveries of the same document to Meilisearch. The stale check is a read followed by a write.
- Meilisearch applies writes as asynchronous tasks. The target only checks that the task was queued.
- An update that arrives after a delete can bring the document back, because nothing records deletions.

## Configuration

Settings come from environment variables and are validated at startup, so a bad config stops the process with a list of what is wrong. See [.env.example](.env.example).

| Variable | Meaning |
| --- | --- |
| `STRAPI_SYNC_SECRET` | Shared secret, at least 16 characters |
| `STRAPI_SYNC_SECRET_HEADER` | Header carrying the secret, default `X-Sync-Secret` |
| `STRAPI_SYNC_MAPPING` | Path to the mapping YAML, default `mapping.yaml` |
| `STRAPI_SYNC_TARGET` | `meilisearch` or `webhook` |
| `MEILISEARCH_URL`, `MEILISEARCH_API_KEY` | Meilisearch target (key optional) |
| `WEBHOOK_TARGET_URL`, `WEBHOOK_TARGET_TOKEN` | JSON webhook target (token optional) |

Mapping example (also in [mapping.example.yaml](mapping.example.yaml)):

```yaml
content_types:
  article:            # the "model" value in the Strapi payload
    index: articles
    id_field: documentId
    fields:
      title: title
      slug: slug
      body: content   # renamed
```

`fields` can also be a plain list of names to keep unchanged. `id` and `_source_updated_at` are reserved names in the target document.

In Strapi, add a webhook pointing at `/webhook` with a custom header holding the same secret, and enable the entry events you want.

## Running

```bash
cp .env.example .env   # then edit; export the variables however you prefer
uvicorn --factory strapi_sync_hub.main:create_app_from_env
```

## Tests

The Strapi payloads in `tests/fixtures/handwritten_from_docs_strapi_events.json` are **hand-written from the Strapi documentation, not recorded from a running Strapi**. The contract tests show the receiver handles that shape. They do not prove it matches a real instance, and replacing the fixture with recorded payloads is still to do.

The Meilisearch tests use an in-process fake of the three endpoints the target calls, through an httpx mock transport. No network is used and no real Meilisearch has been involved.

## Development

Requires Python 3.11 or newer.

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows; on Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

Run the checks:

```bash
ruff check .
ruff format --check .
mypy
pytest
```

`pytest` reports coverage and fails below 85%.

## License

MIT, see [LICENSE](LICENSE).
