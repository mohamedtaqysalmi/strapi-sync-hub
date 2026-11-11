# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Project scaffold: packaging, linting, type checking and test setup.
- Webhook receiver for Strapi entry events with constant-time shared-secret verification.
- YAML content-type mapping with field selection, renaming and a document id field.
- Meilisearch and generic JSON webhook targets with idempotent upserts that skip stale events.
- Environment-based configuration validated at startup, and `.env.example`.
- Contract tests against hand-written (not recorded) Strapi webhook payloads.
