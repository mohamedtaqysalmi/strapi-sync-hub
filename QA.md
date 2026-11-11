# QA notes (v0.1.0)

Manual and automated checks before tagging. Automated results live in [TEST_REPORT.md](TEST_REPORT.md).

## Scope

In scope: webhook receiver, YAML mapping, Meilisearch + JSON webhook targets, retries/backoff, dead-letter JSONL, dry-run, full-reindex CLI, docker-compose demo (stand-in Strapi + Meilisearch + seed), Pages mapping generator, CI.

Out of scope for this tag: recorded live-Strapi fixtures, dead-letter replay CLI, PyPI publish, multi-tenant secrets, waiting on Meilisearch task completion.

## Automated gate (must be green)

| Check | Command / place |
| --- | --- |
| Lint | `ruff check .` |
| Format | `ruff format --check .` |
| Types | `mypy` |
| Tests + coverage ≥ 85% | `pytest` |
| Wheel build | `python -m build` (CI) |
| CI matrix | Python 3.11 and 3.14 on `ubuntu-latest` |

## Manual checklist (human)

- [ ] Open https://mohamedtaqysalmi.github.io/strapi-sync-hub/ after Pages deploy
- [ ] Mapping generator: change model/fields → YAML updates; Copy works
- [ ] Architecture and config sections readable in light and dark OS theme
- [ ] Mobile width (~375px): hero brand and generator usable, no horizontal scroll
- [ ] `cd demo && docker compose up --build` seeds two articles into Meilisearch
- [ ] `strapi-sync-hub reindex --dry-run` against the stand-in prints planned upserts
- [ ] Force a target failure (bad Meilisearch URL) and confirm a dead-letter JSONL line
- [ ] Record a short demo GIF for the README (not required in this tag)

## Honesty checks

- README and demo docs say the compose CMS is a Strapi-shaped stand-in, not real Strapi
- Fixtures are labeled hand-written from docs, not recorded
- Known races (concurrent upsert, delete-then-late-update) stay documented

## Sign-off

Automated gate: see TEST_REPORT.md for the local run used at tag time. CI on `main` after squash-merge is the public record.
