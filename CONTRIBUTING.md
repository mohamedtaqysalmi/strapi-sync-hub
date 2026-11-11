# Contributing

This project is maintained by one person, so replies to issues and pull requests may take a few
days. Small, focused changes are easiest to review.

## Setup

Python 3.11 or newer is required.

```bash
python -m venv .venv
.venv/Scripts/activate        # Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

## Checks

```bash
ruff check .
ruff format --check .
mypy
pytest
```

Coverage must stay at or above 85%. CI runs the same commands on Python 3.11 and 3.14, plus a
package build.

## Branches and commits

- Branch from `main`, named by type: `feat/short-name`, `fix/short-name`, `docs/short-name`,
  `chore/short-name`.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/).
- `main` only changes through pull requests, which are squash-merged after CI passes.

## Pull requests

- Fill in the template: what, why, how you tested it.
- Add or update tests for behaviour changes.
- Update `CHANGELOG.md` under Unreleased for user-visible changes.
- For anything larger than a small fix, open an issue first so we can agree on the approach.

Please use only fake data in tests and examples, and never commit secrets.

## Conduct and security

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Report vulnerabilities as described in
[SECURITY.md](SECURITY.md).
