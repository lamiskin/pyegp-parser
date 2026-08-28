# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
