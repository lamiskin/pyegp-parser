# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.5](https://github.com/lamiskin/pyegp-parser/compare/v0.1.4...v0.1.5) (2026-10-10)


### Dependencies

* bump mcp ([#24](https://github.com/lamiskin/pyegp-parser/issues/24)) ([a1d8d7f](https://github.com/lamiskin/pyegp-parser/commit/a1d8d7fbc1f4d9f8b9782063f52b4997cb6e22af))
* bump pyjwt from 2.13.0 to 2.15.0 ([#20](https://github.com/lamiskin/pyegp-parser/issues/20)) ([81098eb](https://github.com/lamiskin/pyegp-parser/commit/81098eb5b29d5af9c821487a4a4bb2d90d822ed8))
* bump urllib3 from 2.7.0 to 2.8.0 ([#23](https://github.com/lamiskin/pyegp-parser/issues/23)) ([473ca8b](https://github.com/lamiskin/pyegp-parser/commit/473ca8b657c60bb4b9c314f1588427a3cb3f9f6c))
* bump virtualenv from 21.7.0 to 21.7.13 ([#22](https://github.com/lamiskin/pyegp-parser/issues/22)) ([f36b118](https://github.com/lamiskin/pyegp-parser/commit/f36b118e92dd52ac76433a7af62def6913201bc9))

## [0.1.4](https://github.com/lamiskin/pyegp-parser/compare/v0.1.3...v0.1.4) (2026-09-22)


### Dependencies

* bump the python-dependencies group with 2 updates ([#16](https://github.com/lamiskin/pyegp-parser/issues/16)) ([eb303f0](https://github.com/lamiskin/pyegp-parser/commit/eb303f0e489ef8a99753668bf7c1bc006a2af5df))

## [0.1.3](https://github.com/lamiskin/pyegp-parser/compare/v0.1.2...v0.1.3) (2026-09-14)


### Dependencies

* bump the python-dependencies group with 2 updates ([#14](https://github.com/lamiskin/pyegp-parser/issues/14)) ([6156218](https://github.com/lamiskin/pyegp-parser/commit/61562182ca4e05a5836a39ca10c327ec15866a56))

## [0.1.2](https://github.com/lamiskin/pyegp-parser/compare/v0.1.1...v0.1.2) (2026-09-07)


### Dependencies

* bump the python-dependencies group with 2 updates ([#11](https://github.com/lamiskin/pyegp-parser/issues/11)) ([01a5291](https://github.com/lamiskin/pyegp-parser/commit/01a52914b2baaea449ca756c43a1bf9c7fc1df41))

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
