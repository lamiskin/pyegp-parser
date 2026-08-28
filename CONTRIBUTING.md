# Contributing to pyegp-parser

Thanks for your interest in contributing!

## Development setup

This project uses [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/lamiskin/pyegp-parser
cd pyegp-parser
uv sync --all-extras         # create the venv and install everything
uv run pre-commit install    # enable the git hooks (optional but recommended)
```

## Everyday commands

```bash
uv run pytest                # run tests
uv run ruff check            # lint
uv run ruff format           # auto-format
uv run mypy                  # type-check
```

All of the above run in CI on every pull request across Python 3.11–3.14.

## Guidelines

- **Never commit real or confidential `.egp` data.** The test suite generates all
  input in-memory. Integration tests that need real files skip automatically when
  none are present — keep it that way.
- Add or update tests for any behaviour change.
- Keep public APIs typed (the package ships `py.typed`).
- Do not bump versions or edit `CHANGELOG.md` by hand — release-please owns
  both, and generates them from your commit messages.

## Commit messages

This project uses [Conventional Commits](https://www.conventionalcommits.org/)
(e.g. `feat:`, `fix:`, `docs:`, `ci:`) so releases and the changelog can be
generated automatically.

## Releases

Releases are automated with release-please: merging the generated "release" PR
tags a new version and publishes to PyPI via Trusted Publishing. Maintainers do
not publish manually.

### Bootstrapping the first release (maintainers)

release-please treats `.release-please-manifest.json` as the last *released*
version, so it will only ever propose versions **after** it. The version
currently recorded there has to be tagged and released by hand once, or it never
reaches PyPI:

```bash
git tag -a v0.1.0 -m "pyegp-parser 0.1.0" && git push origin v0.1.0
gh release create v0.1.0 --notes-from-tag
```

Before that, dry-run the whole pipeline without touching real PyPI: run the
**Publish** workflow manually (`workflow_dispatch`) with target `testpypi`. It
builds, validates the metadata, smoke-tests the wheel, and publishes to TestPyPI
only — the PyPI job is unreachable from that trigger.
