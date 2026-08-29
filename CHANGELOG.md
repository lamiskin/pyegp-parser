# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1](https://github.com/lamiskin/pyegp-parser/compare/v0.1.0...v0.1.1) (2026-08-29)


### Bug Fixes

* **ci:** use a real PAT for release-please, not GITHUB_TOKEN ([#8](https://github.com/lamiskin/pyegp-parser/issues/8)) ([40dbc09](https://github.com/lamiskin/pyegp-parser/commit/40dbc09a63f93684cbd745f51aa15ffc703565b4)), closes [#7](https://github.com/lamiskin/pyegp-parser/issues/7)
* **deps:** bump cryptography to 50.0.1, patching a high-severity CVE ([#6](https://github.com/lamiskin/pyegp-parser/issues/6)) ([ab8c4bf](https://github.com/lamiskin/pyegp-parser/commit/ab8c4bf2626e37b04d7a3609b02c46a4170898aa))
* **tests:** assert parser_version against __version__, not a literal ([#9](https://github.com/lamiskin/pyegp-parser/issues/9)) ([cbcce46](https://github.com/lamiskin/pyegp-parser/commit/cbcce4648391e57f41e13d5d26a86736546a9abc))


### Dependencies

* bump the python-dependencies group across 1 directory with 4 updates ([#4](https://github.com/lamiskin/pyegp-parser/issues/4)) ([ef78f70](https://github.com/lamiskin/pyegp-parser/commit/ef78f7092f734db7a38cfb9d9188c5f494f2f10a))

## [Unreleased]

## [0.1.0] - 2026-08-28

### Added

- Initial public release.
- Parse SAS Enterprise Guide `.egp` project files into structured JSON.
- Extraction of project metadata, elements, tasks, queries, data references, and shortcuts.
- Execution DAG reconstruction and data-lineage tracing.
- Embedded SAS code, execution log, and ODS result extraction.
- CLI (`pyegp-parser`) with `parse`, `bulk`, and `print` commands.
- Optional MCP server (`pyegp-parser-mcp`) and a Claude Agent Skill for AI-assisted exploration.
- Optional JSON-schema validation of the output.
- Best-effort credential redaction for passwords embedded in SAS code,
  execution logs, and task configuration.

[Unreleased]: https://github.com/lamiskin/pyegp-parser/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/lamiskin/pyegp-parser/releases/tag/v0.1.0
