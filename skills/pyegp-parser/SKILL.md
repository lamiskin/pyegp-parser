---
name: pyegp-parser
description: Parse and interpret SAS Enterprise Guide .egp project files. Use when the user references a .egp file or a project.json produced by pyegp-parser, or asks to extract SAS code, data lineage, queries, or the execution DAG from a SAS Enterprise Guide project.
---

# SAS Enterprise Guide project parsing

Parse `.egp` files into structured JSON with `pyegp-parser`, then interpret the
result. This skill covers both running the tool and reading its output — EGP
projects have several non-obvious conventions that are easy to misread.

An `.egp` file is a ZIP archive containing `project.xml` (the master manifest)
plus SAS code files, task configs, execution logs, and ODS results. The parser
decompiles all of it into one `project.json`.

## Setup

```bash
pip install pyegp-parser
```

No SAS installation is required.

## Running it

```bash
pyegp-parser parse path/to/project.egp --output-dir ./out   # writes ./out/project.json
pyegp-parser bulk ./folder --output-dir ./out               # every .egp under ./folder
pyegp-parser print ./out/project.json                       # human-readable summary
```

From Python:

```python
from pyegp_parser import parse_file

project = parse_file("project.egp")   # -> ParsedProject dataclass
```

Output is large. Prefer extracting the part you need with `jq` or Python over
dumping the whole document into context:

```bash
jq '.metadata.label' out/project.json
jq '.containers[].dag.nodes' out/project.json
jq '.tasks[] | select(._type == "CodeTaskElement") | {id: .metadata.id, label: .metadata.label}' out/project.json
jq '.data_list[].data_model | {server, table}' out/project.json
```

## Approach

1. **Orient first.** Run `pyegp-parser print` (or the `get_project_summary` MCP
   tool) for the project name, element counts, and execution order before
   touching the full JSON.
2. **Then go deep** on the specific task, query, or dataset the user asked
   about, extracting only that section.
3. **Check `completeness_warning`.** If `true`, some archive entries were not
   processed — list `unprocessed_entries` rather than claiming full coverage.

## Non-obvious conventions

### Everything is id-based

Element IDs look like `TypePrefix-RandomAlphanumeric` (e.g.
`CodeTask-a1b2c3d4e5f6`). Relationships are expressed as id references, never
nesting:

- `element.input_ids[]` → upstream dependencies (the data-lineage edges).
- `code_element.parent_id` → the task that owns the code.
- `shortcut.parent_id` → the DataItem or ExternalFileItem it points at.
- `dag.connections[].source_id / target_id` → execution dependencies.

To answer "what feeds task X": look up X's `input_ids`, resolve each id in
`elements` / `data_list` / `shortcuts`, and walk `dag.connections` backwards.

### The `_type` discriminator

Every nested object carries a `_type` field naming its class
(`"CodeTaskElement"`, `"QueryModel"`, `"DAGModel"`, …). Use it to identify
objects without tracking which array they came from.

### Element `type` suffixes

`ElementMetadata.type` is a fully-qualified .NET-style string; the final
segment is what matters:

| Suffix | Meaning |
|---|---|
| `ProcessFlowContainer` | A process flow (one tab in the EG GUI) |
| `CodeTask` | User-written SAS code task — the most common task type |
| `Query` | A Query Builder query (SQL defined via GUI) |
| `EGTask` | A built-in wizard task; `eg_task_clsid` says which wizard |
| `ImportTask` / `ExportTask` | Data import/export wizards |
| `ShortCutToData` / `ShortCutToFile` | Indirect reference to a data/file item |
| `Data` / `ExternalFile` | Registered dataset / external file |
| `Code` / `Log` | Auto-generated code block / log display element |

### The DAG is the execution plan

`containers[].dag.nodes` lists element IDs in **topological execution order**.
`dag.connections` are the dependency edges; `resource_dependency: true` means
the target consumes a dataset the source produces (data dependency, not just
ordering).

### Code elements are mostly boilerplate

Enterprise Guide wraps generated code in sections. **Only `task_code` is the
real logic** — `macro_assign_code`, `begin_app_code`, `end_app_code`, and
`macro_unassign_code` are EG housekeeping (ODS setup, `_CLIENTTASKLABEL`
macros). Do not present boilerplate as the user's program.

For user-written code, read `tasks[].code_content` on `CodeTaskElement`
objects instead.

### Queries are reconstructable SQL

A `query_model` holds `input_tables`, `result_items`, `calculations`,
`join_items`, `where_filters`, `having_filters`, `group_items`, and
`order_items` — enough to reconstruct the SQL the Query Builder would emit.
`input_tables[].data_id` links back to items in `data_list`.

### Shortcuts are indirection, not data

A `ShortCutToData` contains no connection details. Follow its `parent_id` into
`data_list` (or `external_files`) for the actual `server` / `table` /
`member_type`.

### Timestamps are Windows FILETIME ticks

100-nanosecond intervals since 1601-01-01. Convert with:

```
unix_seconds = (ticks - 621355968000000000) / 10_000_000
```

### Null semantics

`null` means "not present in the source XML", which is normal — e.g.
`code_content: null` is a code task that has never been executed, and
`task_config: null` is a task whose config file is missing from the archive.
Do not report nulls as parse failures.

## Handling real projects

EGP archives routinely embed server names, library paths, user IDs in logs,
and business data in ODS results. Parser output reproduces all of it.

When the user is working with production projects, do not paste raw parser
output into anything externally visible, and say so if they are about to.
Quote the specific field they asked about instead of the whole document.
