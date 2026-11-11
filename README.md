# strapi-sync-hub

A small FastAPI service that receives Strapi webhook events and syncs content to Meilisearch and a generic JSON/webhook target.

**Status: early scaffold, nothing usable yet.** The package currently only exposes its version. The planned scope is YAML content-type mapping, idempotent upserts, retries with backoff and a dead-letter log, but none of that exists yet.

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
