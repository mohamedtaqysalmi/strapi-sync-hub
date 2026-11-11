# Test report — v0.1.0

Local run on Windows before the v0.1.0 release PR.

| Field | Value |
|-------|--------|
| Date | 2026-11-11 |
| Host | Windows 10 (win32) |
| Interpreter | CPython 3.15.2 (local); CI matrix is 3.11 and 3.14 |
| Command | ruff check . ; ruff format --check . ; mypy ; pytest |
| Result | 84 passed, 1 warning |
| Coverage | 90.07% statements/branches (fail_under 85%) |

## What is NOT covered

- Happy-path CLI reindex against a live Content API
- Real Meilisearch / real Strapi network I/O
- Dead-letter replay tooling
- Waiting for Meilisearch asynchronous task success

## Fixtures

tests/fixtures/handwritten_from_docs_strapi_events.json — hand-written from Strapi webhook documentation, not recorded from a running Strapi.
