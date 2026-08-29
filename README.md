# pyegp-parser

Parse **SAS Enterprise Guide `.egp` project files** into structured, machine-readable JSON.

[![CI](https://github.com/lamiskin/pyegp-parser/actions/workflows/ci.yml/badge.svg)](https://github.com/lamiskin/pyegp-parser/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/lamiskin/pyegp-parser/branch/main/graph/badge.svg)](https://codecov.io/gh/lamiskin/pyegp-parser)
[![PyPI](https://img.shields.io/pypi/v/pyegp-parser.svg)](https://pypi.org/project/pyegp-parser/)
[![Python versions](https://img.shields.io/pypi/pyversions/pyegp-parser.svg)](https://pypi.org/project/pyegp-parser/)
[![CodeQL](https://github.com/lamiskin/pyegp-parser/actions/workflows/codeql.yml/badge.svg)](https://github.com/lamiskin/pyegp-parser/actions/workflows/codeql.yml)
[![Docs](https://img.shields.io/badge/docs-lamiskin.github.io-blue)](https://lamiskin.github.io/pyegp-parser/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An `.egp` file is a ZIP archive containing `project.xml` plus SAS code, task
configs, execution logs, and ODS results. `pyegp-parser` reads **all** of it and
produces a single structured representation — think of it as decompiling a SAS
Enterprise Guide project into JSON you can query, diff, and analyse.

## Features

- Full extraction of project metadata, elements, tasks, queries, data references, and shortcuts
- Reconstructs the execution **DAG** (process-flow dependencies)
- Extracts embedded SAS code, execution logs, and ODS output references
- Data-lineage tracing across tasks
- Best-effort credential redaction for passwords embedded in SAS code
- Bulk-parse an entire directory tree of `.egp` files
- Optional JSON-schema validation of the output
- Optional [MCP](https://modelcontextprotocol.io) server for AI-assisted exploration
- No heavy dependencies (just `jsonschema`); pure-Python, cross-platform

## Supported Enterprise Guide versions

The parser is **version-agnostic by design**: it reads whatever structure a
project contains and has no version gates or version-specific branches. The
`EGVersion` attribute on the root `ProjectCollection` element is recorded and
surfaced as `project.metadata.eg_version`, but it never changes how a file is
parsed. In practice that means an unlisted version is likely to parse, and
anything the parser does not recognise is reported rather than dropped — see
[Handling unknown content](#handling-unknown-content) below.

| EG version | Status | How it is verified |
|---|---|---|
| **8.1** | Verified against a real project | `tests/fixtures/real_world/eg81_process_flows.egp`, plus most of the synthetic suite |
| **7.1** | Verified against a real project | `tests/fixtures/real_world/eg71_code_tasks.egp` |
| Other 7.x / 8.x | Expected to work, untested | No version gating exists, but no sample was available |
| 9.x and later | Unknown | Not released at the time of writing |

Two caveats worth stating plainly:

- The 7.1 fixture was produced by a third-party 8→7 downgrade converter rather
  than written by Enterprise Guide 7.1 itself. Its `project.xml`, embedded SAS
  code, and execution logs are EG-authored, but it is not a pristine 7.1 file.
- The 8.1 fixture is a *migrated* project: its elements carry
  `ModifiedByEGVer` values spanning `7.100.5.x` and `8.1.0.x`, so mixed-version
  element metadata within a single project is covered.

Real-world coverage is limited by sample availability — genuine `.egp` files are
rarely published, since they are binary ZIP archives. Provenance and the exact
sanitisation applied to both fixtures are documented in
[`tests/fixtures/real_world/README.md`](tests/fixtures/real_world/README.md).

### Handling unknown content

Because there is no version gating, an unlisted version is likely to parse. How
the parser behaves when it meets something it does not understand depends on
what that something is:

- **Unrecognised archive entries** are listed in `project.unprocessed_entries`
  and counted in `project.completeness_summary`, so nothing is silently
  discarded. Comparing `processed_entries` against `total_entries` tells you how
  much of a project was understood.
- **Missing optional artifacts** — an absent `code.sas` or task-config file —
  log a warning and leave the corresponding field `None`.
- **A missing required section inside an element** raises `ValueError` and
  aborts the whole parse. This is deliberate: the parser surfaces structural
  gaps rather than emitting quietly incomplete output. Log elements and
  process-flow containers are the two exceptions — they are recorded with
  whatever metadata was readable, because a display-settings or DAG failure does
  not undermine the rest of the project.

So a newer EG version introducing a *new* element type or archive entry is
handled gracefully, whereas one that *restructures an existing element* will
fail loudly. If you hit either, `completeness_summary` and `unprocessed_entries`
are the place to look first, and a bug report quoting the EG version plus those
fields is the most useful thing you can send.

## Installation

```bash
pip install pyegp-parser
```

Requires Python 3.11+.

## Quick start

```python
from pyegp_parser import parse_file

project = parse_file("path/to/project.egp")

print(project.metadata.label)  # project name
print(len(project.tasks))  # number of tasks
print(len(project.queries))  # number of Query Builder queries
```

Write JSON to disk:

```python
parse_file("project.egp", output_dir="./output")  # writes ./output/project.json
```

## CLI

```bash
# Parse a single file
pyegp-parser parse path/to/project.egp --output-dir ./output

# Recursively parse every .egp under a directory (mirrors the tree)
pyegp-parser bulk ./source-pipeline --output-dir ./output

# Pretty-print a parsed project.json
pyegp-parser print ./output/project.json
```

## Credential redaction

`.egp` projects embed SAS programs and logs verbatim, and SAS code routinely
carries live credentials. Passwords are therefore redacted automatically when
output is written:

```python
from pyegp_parser.redaction import redact_text

redact_text("libname dw oracle user=etluser password=hunter2 path=prod;")
# ('libname dw oracle user=etluser password=[SENSITIVE - REDACTED] path=prod;', 1)
```

SAS-encoded passwords (`{SAS002}...`) are redacted too — `PROC PWENCODE` output
is reversible, so it is treated as plaintext. Column names such as
`PASSWORD_HASH` are deliberately left intact: a column *name* is schema
metadata, not a secret.

Redaction applies when `project.json` is written and to MCP server output.
`to_dict()` is a pure serializer and does not redact.

### Handling real projects

Redaction covers credentials, not everything an `.egp` file reveals. Output also
includes library paths, server names, schema names, and usernames. Review parser
output before attaching it to a public issue or sharing it outside your
organisation — see [SECURITY.md](SECURITY.md) for the full security model.

## AI integration

`.egp` projects are dense and hard to read by hand, which makes them a natural fit
for AI-assisted exploration. Two complementary options ship with this project:

### MCP server

An [MCP](https://modelcontextprotocol.io) server exposes the parser as tools
(`parse_egp`, `parse_egp_directory`, `get_project_summary`, `get_sas_code`,
`get_data_lineage`, `get_queries`) to any MCP-compatible client (Claude Desktop,
Claude Code, Cursor, …).

```bash
pip install "pyegp-parser[mcp]"
```

Then register it with your client. Example config:

```json
{
  "mcpServers": {
    "pyegp-parser": {
      "command": "pyegp-parser-mcp"
    }
  }
}
```

### Claude Skill

[`skills/pyegp-parser/SKILL.md`](skills/pyegp-parser/SKILL.md) is a portable
[Agent Skill](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview)
that teaches Claude when and how to parse `.egp` files and interpret the JSON —
no running server required. Copy the `skills/pyegp-parser/` folder into your
`.claude/skills/` directory to use it.

Use the **MCP server** for interactive, on-demand parsing inside a client; use the
**Skill** for a portable, dependency-light way to give any Claude the know-how.

## Documentation

Full documentation lives at
**[lamiskin.github.io/pyegp-parser](https://lamiskin.github.io/pyegp-parser/)**.

- [Full usage guide & API reference](docs/reference.md)
- [Guide to interpreting the JSON output (for LLMs and humans)](docs/LLM_CONTEXT.md)

## Development

This project uses [uv](https://docs.astral.sh/uv/) and [ruff](https://docs.astral.sh/ruff/).

```bash
git clone https://github.com/lamiskin/pyegp-parser
cd pyegp-parser
uv sync                 # create the venv and install deps (incl. dev tools)
uv run pytest           # run the test suite
uv run ruff check       # lint
uv run ruff format      # format
```

## Acknowledgements

This library was developed with substantial assistance from AI coding tools. It
was originally built and validated against a corpus of **real** SAS Enterprise
Guide `.egp` files during a data-migration project. None of that source data — and
no files, identifiers, or history derived from it — is included in this repository;
the test suite runs entirely on synthetic fixtures generated in-memory.

## License

[MIT](LICENSE)
