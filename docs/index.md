# pyegp-parser

Parse **SAS Enterprise Guide `.egp` project files** into structured,
machine-readable JSON.

An `.egp` file is a ZIP archive containing `project.xml` plus SAS code, task
configs, execution logs, and ODS results. `pyegp-parser` reads **all** of it
and produces a single structured representation — think of it as decompiling a
SAS Enterprise Guide project into JSON you can query, diff, and analyse.

## Features

- Full extraction of project metadata, elements, tasks, queries, data references, and shortcuts
- Reconstructs the execution **DAG** (process-flow dependencies)
- Extracts embedded SAS code, execution logs, and ODS output references
- Data-lineage tracing across tasks
- Bulk-parse an entire directory tree of `.egp` files
- Optional JSON-schema validation of the output
- Optional [MCP server](ai-integration.md) for AI-assisted exploration
- No heavy dependencies (just `jsonschema`); pure-Python, cross-platform

## Supported Enterprise Guide versions

The parser is **version-agnostic by design**: it reads whatever structure a
project contains and has no version gates or version-specific branches. The
`EGVersion` attribute on the root `ProjectCollection` element is recorded and
surfaced as `project.metadata.eg_version`, but it never changes how a file is
parsed — so an unlisted version is likely to parse.

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
- The 8.1 fixture is a *migrated* project: its elements carry `ModifiedByEGVer`
  values spanning `7.100.5.x` and `8.1.0.x`, so mixed-version element metadata
  within a single project is covered.

Real-world coverage is limited by sample availability — genuine `.egp` files are
rarely published, since they are binary ZIP archives.

### Handling unknown content

How the parser behaves when it meets something it does not understand depends on
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
  whatever metadata was readable.

So a newer EG version introducing a *new* element type or archive entry is
handled gracefully, whereas one that *restructures an existing element* will
fail loudly.

## Install

```bash
pip install pyegp-parser
```

Requires Python 3.11+.

## Quick start

```python
from pyegp_parser import parse_file

project = parse_file("path/to/project.egp")

print(project.metadata.label)     # project name
print(len(project.tasks))         # number of tasks
print(len(project.queries))       # number of Query Builder queries
```

Or from the command line:

```bash
pyegp-parser parse path/to/project.egp --output-dir ./output   # writes ./output/project.json
pyegp-parser bulk ./folder --output-dir ./output               # every .egp under ./folder
pyegp-parser print ./output/project.json                       # human-readable summary
```

## Documentation

- **[Usage & API reference](reference.md)** — the full guide: CLI, Python API,
  output data structure, element types, and error handling.
- **[AI integration](ai-integration.md)** — the MCP server and the Claude
  Skill.
- **[LLM context guide](LLM_CONTEXT.md)** — deep semantics of the JSON output,
  written to be pasted into an LLM's context; doubles as the human reference
  for interpreting `project.json`.

## Links

- [Source on GitHub](https://github.com/lamiskin/pyegp-parser)
- [PyPI package](https://pypi.org/project/pyegp-parser/)
- [Changelog](https://github.com/lamiskin/pyegp-parser/blob/main/CHANGELOG.md)
- [Contributing](https://github.com/lamiskin/pyegp-parser/blob/main/CONTRIBUTING.md)
