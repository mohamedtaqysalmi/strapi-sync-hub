# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Rebuilt the GitHub Pages site on the shared page style, with a mapping generator whose output is tested against the real config loader.

## [0.1.0] - 2026-11-11

### Added

- Webhook receiver for Strapi entry events with constant-time shared-secret verification.
- YAML content-type mapping with field selection, renaming, document id field, and optional `api_id`.
- Meilisearch and generic JSON webhook targets with idempotent upserts that skip stale events.
- Retries with exponential backoff around target upsert/delete.
- Dead-letter JSONL log when retries are exhausted (webhook returns `dead_lettered`).
- Dry-run target via `STRAPI_SYNC_DRY_RUN` and `strapi-sync-hub reindex --dry-run`.
- Full-reindex CLI against a Strapi Content API (`STRAPI_URL` / `STRAPI_API_TOKEN`).
- Docker Compose demo with Meilisearch, a Strapi-shaped stand-in, the hub, and a seed job.
- GitHub Pages site with architecture notes, config examples, and an in-browser mapping generator.
- Environment-based configuration validated at startup, contract tests against hand-written Strapi payloads, QA notes and architecture ADRs.

[0.1.0]: https://github.com/mohamedtaqysalmi/strapi-sync-hub/releases/tag/v0.1.0
[Unreleased]: https://github.com/mohamedtaqysalmi/strapi-sync-hub/compare/v0.1.0...HEAD
