# pyegp-parser Documentation

**pyegp-parser** extracts the full content of SAS Enterprise Guide `.egp` project files into structured JSON. An `.egp` file is a ZIP archive containing `project.xml` and associated artifacts (code files, task configs, execution logs, ODS results). This tool parses all of it.

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [CLI Usage](#cli-usage)
- [Python API](#python-api)
- [Output Data Structure](#output-data-structure)
- [Element Types](#element-types)
- [Error Handling](#error-handling)
- [Examples](#examples)

---

## Installation

```bash
pip install pyegp-parser
```

With the optional MCP server:

```bash
pip install "pyegp-parser[mcp]"
```

Requires Python 3.11+. No external dependencies beyond `jsonschema` (used for optional schema validation).

For development:

```bash
git clone https://github.com/lamiskin/pyegp-parser
cd pyegp-parser
uv sync --all-extras
```

---

## Quick Start

Parse a single file and get structured data back:

```python
from pyegp_parser import parse_file

project = parse_file("path/to/project.egp")

print(project.metadata.label)        # "My SAS Project"
print(len(project.elements))          # 12
print(len(project.queries))           # 3
print(len(project.tasks))             # 5
print(project.completeness_summary)   # CompletenessSummary(total=15, processed=14, unprocessed=1)
```

Parse and write JSON output:

```python
from pyegp_parser import parse_file

project = parse_file("project.egp", output_dir="./output")
# Writes: ./output/project.json
```

---

## CLI Usage

The CLI provides three commands: `parse`, `bulk`, and `print`.

### Parse a single file

```bash
pyegp-parser parse path/to/project.egp --output-dir ./output
```

### Parse all .egp files in a directory

```bash
pyegp-parser bulk ./source-pipeline --output-dir ./output
```

This recursively finds all `.egp` files and outputs JSON in a mirrored directory structure. For example:

```
source-pipeline/
  01-Staging/
    02-Jobs/
      01-Load-Data.egp
      02-Transform.egp

output/
  01-Staging/
    02-Jobs/
      01-Load-Data/
        project.json
      02-Transform/
        project.json
```

### Pretty-print a parsed JSON file

```bash
pyegp-parser print output/01-Staging/02-Jobs/01-Load-Data/project.json
```

---

## Python API

### `parse_file(egp_path, output_dir=None) -> ParsedProject`

Parse a single `.egp` file into a `ParsedProject` dataclass.

```python
from pyegp_parser import parse_file

project = parse_file("my_project.egp")
```

**Parameters:**
- `egp_path` (str | Path): Path to the `.egp` file.
- `output_dir` (str | Path | None): If provided, writes `project.json` to this directory.

**Returns:** `ParsedProject` — the fully parsed project data.

**Raises:**
- `FileNotFoundError` — if the file doesn't exist.
- `ValueError` — if the file is not a valid EGP archive, or a required section is malformed.

---

### `parse_directory(directory, output_dir=None) -> BulkResult`

Parse all `.egp` files in a directory recursively.

```python
from pyegp_parser import parse_directory

result = parse_directory("./source-pipeline", output_dir="./output")

print(f"Parsed {result.summary.success_count}/{result.summary.total_files} files")
for failure in result.failures:
    print(f"  FAILED: {failure.file_path} — {failure.error_message}")
```

**Parameters:**
- `directory` (str | Path): Root directory to scan.
- `output_dir` (str | Path | None): If provided, writes JSON output preserving the source directory structure.

**Returns:** `BulkResult` with `summary`, `successes`, and `failures` lists.

---

### Serialization Helpers

```python
from pyegp_parser.serializer import to_dict, serialize_project

# Convert to a plain dict (for custom processing)
data = to_dict(project)

# Write JSON to disk
serialize_project(project, output_dir=Path("./output"))
```

---

## Output Data Structure

The JSON output is a single `ParsedProject` object. Every nested object includes a `_type` discriminator field. Keys are sorted alphabetically. Indentation is 2 spaces.

### Top-Level Structure

```json
{
  "_type": "ParsedProject",
  "_schema_version": "1.0.0",
  "source": { ... },
  "metadata": { ... },
  "settings": { ... },
  "parameters": [ ... ],
  "data_list": [ ... ],
  "external_files": [ ... ],
  "elements": [ ... ],
  "containers": [ ... ],
  "queries": [ ... ],
  "tasks": [ ... ],
  "shortcuts": [ ... ],
  "log_elements": [ ... ],
  "code_elements": [ ... ],
  "external_objects": [ ... ],
  "visual_layout": { ... },
  "project_log": { ... },
  "binary_entries": [ ... ],
  "completeness_summary": { ... },
  "unprocessed_entries": [ ... ],
  "completeness_warning": false,
  "application_overrides": { ... },
  "metadata_info": { ... },
  "open_project_view": [ ... ]
}
```

### Section Reference

| Field | Type | Description |
|-------|------|-------------|
| `source` | `SourceInfo` | Provenance: file path, size, parse timestamp, ZIP entry count |
| `metadata` | `ProjectMetadata` | Project name, ID, EG version, creation/modification timestamps |
| `settings` | `ProjectSettings` | Execution settings (grid submission, error handling, log config) |
| `parameters` | `Parameter[]` | Project-level name/value parameters |
| `data_list` | `DataItem[]` | Dataset references with server, library, table, and DNA metadata |
| `external_files` | `ExternalFileItem[]` | External file references with file type and DNA descriptors |
| `elements` | `ElementMetadata[]` | All elements in document order (metadata only) |
| `containers` | `ProcessFlowContainer[]` | Process flow containers with DAG (topologically sorted nodes, edges) |
| `queries` | `object[]` | Query elements with QueryModel (tables, joins, filters, results) |
| `tasks` | `TaskElement[]` | Task elements (CodeTask, ImportTask, EGTask, ExportTask, AppendTask) |
| `shortcuts` | `ShortCutToData/File[]` | Shortcuts referencing data or file items |
| `log_elements` | `LogElement[]` | Log display configuration elements |
| `code_elements` | `CodeElement[]` | Structured code with pre/post task fragments |
| `external_objects` | `ExternalObject[]` | External object references (name, type, path) |
| `visual_layout` | `VisualLayout` | Node positions and styles for process flow diagrams |
| `project_log` | `ProjectLogInfo` | Project log enabled/written state and content |
| `binary_entries` | `BinaryEntry[]` | ODS results tracked by path, size, and extension |
| `completeness_summary` | `CompletenessSummary` | total/processed/unprocessed entry counts |
| `unprocessed_entries` | `UnprocessedEntry[]` | Archive entries not handled by any parser |
| `application_overrides` | `object` | Raw ApplicationOverrides key-value section |
| `metadata_info` | `object` | Raw MetaDataInfo section |
| `open_project_view` | `TreeItem[]` | Project tree view state (expanded/collapsed nodes) |

---

## Element Types

The parser classifies elements by their `Type` attribute and invokes specialized parsers:

| Category | Type suffix | Parser output |
|----------|-------------|---------------|
| Query | `Query` | `QueryModel` with InputTables, ResultItems, JoinItems, Filters, Calculations |
| CodeTask | `CodeTask` | `CodeTaskElement` with SAS code content and SubmitableElement |
| ImportTask | `ImportTask` | `ImportTaskElement` with task config XML and data mappings |
| EGTask | `EGTask` | `EGTaskElement` with wizard-generated task config |
| ExportTask | `ExportTask` | `ExportTaskElement` with export configuration |
| AppendTask | `AppendTask` | `AppendTaskElement` with input data references |
| ShortCutToData | `ShortCutToData` | `ShortCutToData` with parent_id and input_list |
| ShortCutToFile | `ShortCutToFile` | `ShortCutToFile` with parent_id and input_list |
| Log | `Log` | `LogElement` with display settings (line_size, page_size) |
| Code | `Code` | `CodeElement` with structured code sections (pre/post/task code) |
| ProcessFlowContainer | `ProcessFlowContainer` | DAG with topologically sorted nodes and connections |

---

## Detailed Model Reference

### SourceInfo

```json
{
  "_type": "SourceInfo",
  "file_path": "/path/to/projects/my_project.egp",
  "file_name": "my_project.egp",
  "file_size_bytes": 245760,
  "parsed_at": "2025-01-15T10:30:00.123456",
  "total_zip_entries": 28
}
```

### ProjectMetadata

```json
{
  "_type": "ProjectMetadata",
  "eg_version": "8.1",
  "type": "SAS.EG.ProjectElements.ProjectCollection",
  "label": "Customer Analysis",
  "id": "PROJ-abc123",
  "created_on": "638396640000000000",
  "modified_on": "638435520000000000",
  "modified_by": "John Smith",
  "modified_by_eg_id": "jsmith1",
  "modified_by_eg_ver": "8.4.0.110"
}
```

### QueryModel (inside queries array)

```json
{
  "metadata": { "_type": "ElementMetadata", "label": "Filter Customers", ... },
  "submitable": { "_type": "SubmitableElement", "server": "SASApp", ... },
  "query_model": {
    "_type": "QueryModel",
    "input_tables": [
      { "id": "T1", "input_table_name": "WORK.CUSTOMERS", "alias": "t1" }
    ],
    "result_items": [
      { "result_id": "R1", "alias": "customer_name", "table_id": "T1" }
    ],
    "join_items": [
      { "left_table_id": "T1", "right_table_id": "T2", "join_type": "Inner" }
    ],
    "where_filters": [ ... ],
    "order_items": [ ... ],
    "calculations": [ ... ]
  }
}
```

### CodeElement

```json
{
  "_type": "CodeElement",
  "metadata": { "_type": "ElementMetadata", "label": "Code", "id": "Code-abc123", ... },
  "text": "PROC PRINT DATA=work.output; RUN;",
  "task_code": "PROC PRINT DATA=work.output; RUN;",
  "begin_app_code": "ODS _ALL_ CLOSE; ...",
  "end_app_code": ";*';*\";*/;quit;run;\nODS _ALL_ CLOSE;",
  "macro_assign_code": "%LET _CLIENTTASKLABEL='My Task'; ...",
  "macro_unassign_code": "%LET _CLIENTTASKLABEL=; ...",
  "parent_id": "CodeTask-xyz789",
  "read_only": true,
  "def_ext": ".sas"
}
```

### ProcessFlowContainer with DAG

```json
{
  "_type": "ProcessFlowContainer",
  "metadata": { "_type": "ElementMetadata", "label": "Process Flow", "id": "PFC-001" },
  "dag": {
    "_type": "DAGModel",
    "nodes": ["ImportTask-001", "CodeTask-002", "Query-003"],
    "connections": [
      { "source_id": "ImportTask-001", "target_id": "CodeTask-002", "resource_dependency": false },
      { "source_id": "CodeTask-002", "target_id": "Query-003", "resource_dependency": true }
    ],
    "warnings": []
  }
}
```

### DataItem

```json
{
  "_type": "DataItem",
  "element": { "_type": "ElementMetadata", "label": "CUSTOMERS", "id": "DATA-001" },
  "data_model": {
    "_type": "DataModel",
    "server": "SASApp",
    "table": "CUSTOMERS",
    "member_type": "DATA",
    "decoded_dna": { "_type": "DNADescriptor", "name": "CUSTOMERS", ... }
  },
  "shortcut_list": ["SC-001", "SC-002"]
}
```

### CompletenessSummary

```json
{
  "_type": "CompletenessSummary",
  "total_entries": 28,
  "processed_entries": 26,
  "unprocessed_entries": 2
}
```

---

## Error Handling

The parser raises `ValueError` when:
- A typed element has a malformed or missing required section (e.g., a Query without `QueryModel`, a ShortCut without `SHORTCUT`)
- An ExternalObject entry is missing the required `Name` field
- The `project.xml` cannot be decoded from any supported encoding

Non-critical issues are logged as warnings:
- Missing task config files in the archive (common for never-executed tasks)
- Absent project log
- Malformed DNA in external file entries
- Failed process flow DAG construction

Use Python's logging to capture warnings:

```python
import logging
logging.basicConfig(level=logging.WARNING)

from pyegp_parser import parse_file
project = parse_file("project.egp")
```

---

## Examples

### Extract all SAS code from a project

```python
from pyegp_parser import parse_file

project = parse_file("my_project.egp")

# Get code from CodeTask elements
for task in project.tasks:
    if hasattr(task, 'code_content') and task.code_content:
        print(f"--- {task.metadata.label} ---")
        print(task.code_content)

# Get structured code from Code elements
for code_elem in project.code_elements:
    if code_elem.task_code:
        print(f"--- {code_elem.metadata.label} (parent: {code_elem.parent_id}) ---")
        print(code_elem.task_code)
```

### List all query input tables

```python
from pyegp_parser import parse_file

project = parse_file("my_project.egp")

for query in project.queries:
    label = query["metadata"].label
    tables = query["query_model"].input_tables
    print(f"Query: {label}")
    for t in tables:
        print(f"  Input: {t.input_table_name}")
```

### Get the execution DAG

```python
from pyegp_parser import parse_file

project = parse_file("my_project.egp")

for container in project.containers:
    print(f"Process Flow: {container.metadata.label}")
    if container.dag:
        print(f"  Execution order: {container.dag.nodes}")
        for conn in container.dag.connections:
            print(f"  {conn.source_id} -> {conn.target_id}")
```

### Check for unprocessed archive entries

```python
from pyegp_parser import parse_file

project = parse_file("my_project.egp")

if project.completeness_warning:
    print(f"Warning: {project.completeness_summary.unprocessed_entries} entries not processed")
    for entry in project.unprocessed_entries:
        print(f"  {entry.path} ({entry.compressed_size} bytes)")
```

### Bulk parse with error reporting

```python
from pyegp_parser import parse_directory

result = parse_directory("./sas-projects", output_dir="./parsed-output")

print(f"Success: {result.summary.success_count}/{result.summary.total_files}")

if result.failures:
    print("\nFailed files:")
    for f in result.failures:
        print(f"  {f.file_path}: {f.error_message}")
```

### Access project settings and parameters

```python
from pyegp_parser import parse_file

project = parse_file("my_project.egp")

# Project settings
if project.settings:
    print(f"Grid submission: {project.settings.submit_to_grid}")
    print(f"Relative paths: {project.settings.use_relative_paths}")

# Parameters
for param in project.parameters:
    print(f"  {param.name} = {param.value}")
```

### Work with shortcuts and data lineage

```python
from pyegp_parser import parse_file

project = parse_file("my_project.egp")

# Map shortcut -> parent data item
for sc in project.shortcuts:
    print(f"Shortcut '{sc.metadata.label}' -> parent: {sc.parent_id}")
    if sc.input_list:
        print(f"  Inputs: {sc.input_list}")
```

### Find all external object references

```python
from pyegp_parser import parse_file

project = parse_file("my_project.egp")

for obj in project.external_objects:
    print(f"{obj.name} ({obj.type}): {obj.path}")
    if obj.metadata:
        for key, val in obj.metadata.items():
            print(f"  {key}: {val}")
```

---

## JSON Output Conventions

- All dictionary keys are sorted alphabetically
- Indentation is 2 spaces
- Encoding is UTF-8
- Every dataclass object has a `_type` discriminator field with the class name
- `None` values are serialized as `null`
- Empty lists are serialized as `[]`
- Timestamps from EGP XML are preserved as-is (Windows FILETIME ticks, not ISO 8601)

---

## Architecture

```
pyegp_parser/
├── __init__.py          # Main API: parse_file(), parse_directory()
├── archive.py           # ZIP archive handling and entry categorization
├── bulk.py              # Bulk directory processing
├── classifier.py        # Element type classification
├── cli.py               # Command-line interface
├── dag.py               # DAG construction and topological sort
├── models/              # Dataclass definitions
│   ├── base.py          #   ElementMetadata
│   ├── data.py          #   DataItem, DataModel
│   ├── external_file.py #   ExternalFileItem
│   ├── external_objects.py # ExternalObject
│   ├── log_code.py      #   LogElement, CodeElement
│   ├── process_flow.py  #   ProcessFlowContainer, DAGModel, Connection
│   ├── project.py       #   ParsedProject, ProjectMetadata, ProjectSettings, etc.
│   ├── query.py         #   QueryModel, InputTable, ResultItem, JoinItem, etc.
│   ├── shortcut.py      #   ShortCutToData, ShortCutToFile
│   ├── tasks.py         #   CodeTaskElement, ImportTaskElement, EGTaskElement, etc.
│   └── visual_layout.py #   VisualLayout, TaskGraphic, ProcessFlowControlState
├── parsers/             # Section-specific parsers
│   ├── data_parser.py   #   DataList and ExternalFileList parsing
│   ├── dna_parser.py    #   DNA descriptor decoding
│   ├── element_parser.py #  Element classification and metadata extraction
│   ├── external_objects_parser.py # External_Objects section
│   ├── layout_parser.py #   Visual layout and TaskGraphic parsing
│   ├── log_code_parser.py # Log/Code elements and execution logs
│   ├── ods_parser.py    #   ODS result extraction
│   ├── pfd_parser.py    #   Process flow DAG construction
│   ├── project_parser.py #  Project metadata and settings
│   ├── query_parser.py  #   Query element parsing
│   ├── shortcut_parser.py # Shortcut element parsing
│   └── task_parser.py   #   Task element parsing (Import, Code, EG, Export, Append)
├── pretty_printer.py    # Human-readable output formatting
├── schema_generator.py  # JSON schema generation
├── serializer.py        # JSON serialization with _type discriminators
└── validator.py         # Archive completeness validation
```
