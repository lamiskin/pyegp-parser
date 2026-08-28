"""MCP Server for EGP Parser.

Exposes the EGP parser as MCP tools that can be called by any
MCP-compatible client. Provides tools for parsing EGP files, extracting
code, tracing data lineage, and exploring project structure.
"""

import json
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from pyegp_parser import parse_directory, parse_file
from pyegp_parser.redaction import redact
from pyegp_parser.serializer import to_dict

mcp = FastMCP(
    "pyegp-parser",
    instructions="Parse SAS Enterprise Guide .egp project files into structured JSON. Use these tools to extract code, data lineage, queries, and project structure from EGP archives.",
)


@mcp.tool()
def parse_egp(file_path: str, output_dir: str | None = None) -> str:
    """Parse a single .egp file and return the structured JSON output.

    Args:
        file_path: Absolute path to the .egp file to parse.
        output_dir: Optional directory to write project.json to. If omitted, returns JSON directly.

    Returns:
        JSON string of the parsed project, or a success message if output_dir is provided.
    """
    path = Path(file_path)
    if not path.exists():
        return json.dumps({"error": f"File not found: {file_path}"})
    if path.suffix.lower() != ".egp":
        return json.dumps({"error": f"Not an .egp file: {file_path}"})

    try:
        if output_dir:
            project = parse_file(path, output_dir=Path(output_dir))
            return json.dumps(
                {
                    "status": "success",
                    "file": str(path),
                    "output_dir": output_dir,
                    "elements": len(project.elements),
                    "tasks": len(project.tasks),
                    "queries": len(project.queries),
                }
            )
        else:
            project = parse_file(path)
            data, _ = redact(to_dict(project))
            return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True)
    except (ValueError, FileNotFoundError) as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def parse_egp_directory(directory_path: str, output_dir: str | None = None) -> str:
    """Parse all .egp files in a directory recursively.

    Args:
        directory_path: Root directory to scan for .egp files.
        output_dir: Optional directory for JSON output (preserves subdirectory structure).

    Returns:
        JSON summary with total files, successes, and failures.
    """
    dir_path = Path(directory_path)
    if not dir_path.exists():
        return json.dumps({"error": f"Directory not found: {directory_path}"})
    if not dir_path.is_dir():
        return json.dumps({"error": f"Not a directory: {directory_path}"})

    try:
        out = Path(output_dir) if output_dir else None
        result = parse_directory(dir_path, output_dir=out)
        response = {
            "status": "success",
            "total_files": result.summary.total_files,
            "success_count": result.summary.success_count,
            "failure_count": result.summary.failure_count,
        }
        if result.failures:
            response["failures"] = [
                {"file": f.file_path, "error": f.error_message} for f in result.failures
            ]
        return json.dumps(response, indent=2)
    except ValueError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_project_summary(file_path: str) -> str:
    """Get a high-level summary of an EGP project without the full JSON dump.

    Returns project name, element counts by type, execution order, and data sources.

    Args:
        file_path: Absolute path to the .egp file.

    Returns:
        JSON summary with project overview, element counts, DAG, and data sources.
    """
    path = Path(file_path)
    if not path.exists():
        return json.dumps({"error": f"File not found: {file_path}"})

    try:
        project = parse_file(path)
        summary: dict[str, Any] = {
            "project_name": project.metadata.label if project.metadata else None,
            "eg_version": project.metadata.eg_version if project.metadata else None,
            "file_name": project.source.file_name if project.source else None,
            "file_size_bytes": project.source.file_size_bytes
            if project.source
            else None,
            "counts": {
                "elements": len(project.elements),
                "process_flows": len(project.containers),
                "queries": len(project.queries),
                "code_tasks": sum(
                    1 for t in project.tasks if hasattr(t, "code_content")
                ),
                "import_tasks": sum(
                    1
                    for t in project.tasks
                    if hasattr(t, "task_config")
                    and hasattr(t, "eg_task_clsid") is False
                ),
                "shortcuts": len(project.shortcuts),
                "data_items": len(project.data_list),
                "external_files": len(project.external_files),
                "external_objects": len(project.external_objects),
                "code_elements": len(project.code_elements),
                "log_elements": len(project.log_elements),
            },
            "execution_order": [],
            "data_sources": [],
            "completeness": None,
        }

        # Execution DAGs
        for container in project.containers:
            dag_info = {
                "process_flow": container.metadata.label
                if container.metadata
                else "Unknown",
                "nodes": container.dag.nodes if container.dag else [],
                "connections": [
                    {"from": c.source_id, "to": c.target_id}
                    for c in (container.dag.connections if container.dag else [])
                ],
            }
            summary["execution_order"].append(dag_info)

        # Data sources
        for item in project.data_list:
            if item.data_model:
                summary["data_sources"].append(
                    {
                        "label": item.element.label if item.element else None,
                        "server": item.data_model.server,
                        "table": item.data_model.table,
                        "member_type": item.data_model.member_type,
                    }
                )

        # Completeness
        if project.completeness_summary:
            summary["completeness"] = {
                "total_entries": project.completeness_summary.total_entries,
                "processed": project.completeness_summary.processed_entries,
                "unprocessed": project.completeness_summary.unprocessed_entries,
            }

        return json.dumps(summary, indent=2, ensure_ascii=False)
    except (ValueError, FileNotFoundError) as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_sas_code(file_path: str, element_id: str | None = None) -> str:
    """Extract SAS code from an EGP project.

    If element_id is provided, returns code for that specific element.
    Otherwise, returns all code from all tasks and code elements.

    Args:
        file_path: Absolute path to the .egp file.
        element_id: Optional element ID to get code for a specific task.

    Returns:
        JSON with extracted SAS code blocks.
    """
    path = Path(file_path)
    if not path.exists():
        return json.dumps({"error": f"File not found: {file_path}"})

    try:
        project = parse_file(path)
        code_blocks = []

        if element_id:
            # Find specific element
            for task in project.tasks:
                if (
                    hasattr(task, "metadata")
                    and task.metadata
                    and task.metadata.id == element_id
                ):
                    code_blocks.append(
                        {
                            "element_id": element_id,
                            "label": task.metadata.label,
                            "type": task.metadata.type,
                            "code": getattr(task, "code_content", None),
                        }
                    )
            for ce in project.code_elements:
                if ce.metadata and ce.metadata.id == element_id:
                    code_blocks.append(
                        {
                            "element_id": element_id,
                            "label": ce.metadata.label,
                            "parent_id": ce.parent_id,
                            "task_code": ce.task_code,
                            "full_code": ce.text,
                        }
                    )
                elif ce.parent_id == element_id:
                    code_blocks.append(
                        {
                            "element_id": ce.metadata.id if ce.metadata else None,
                            "label": ce.metadata.label if ce.metadata else None,
                            "parent_id": ce.parent_id,
                            "task_code": ce.task_code,
                            "full_code": ce.text,
                        }
                    )
            if not code_blocks:
                return json.dumps({"error": f"No code found for element: {element_id}"})
        else:
            # Get all code
            for task in project.tasks:
                if hasattr(task, "code_content") and task.code_content:
                    code_blocks.append(
                        {
                            "element_id": task.metadata.id if task.metadata else None,
                            "label": task.metadata.label if task.metadata else None,
                            "type": "CodeTask",
                            "code": task.code_content,
                        }
                    )
            for ce in project.code_elements:
                if ce.task_code:
                    code_blocks.append(
                        {
                            "element_id": ce.metadata.id if ce.metadata else None,
                            "label": ce.metadata.label if ce.metadata else None,
                            "parent_id": ce.parent_id,
                            "type": "CodeElement",
                            "task_code": ce.task_code,
                        }
                    )

        redacted_blocks, _ = redact(code_blocks)
        return json.dumps(
            {"code_blocks": redacted_blocks}, indent=2, ensure_ascii=False
        )
    except (ValueError, FileNotFoundError) as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_data_lineage(file_path: str, element_id: str | None = None) -> str:
    """Trace data lineage in an EGP project.

    Shows what data each task reads and produces, following shortcut references
    and input_ids to build a dependency picture.

    Args:
        file_path: Absolute path to the .egp file.
        element_id: Optional element ID to trace lineage for a specific element.

    Returns:
        JSON with data lineage information (inputs, outputs, connections).
    """
    path = Path(file_path)
    if not path.exists():
        return json.dumps({"error": f"File not found: {file_path}"})

    try:
        project = parse_file(path)

        # Build lookup maps
        element_map = {}
        for elem in project.elements:
            element_map[elem.id] = {
                "id": elem.id,
                "label": elem.label,
                "type": elem.type,
                "input_ids": elem.input_ids,
                "container": elem.container,
            }

        data_map = {}
        for item in project.data_list:
            if item.element and item.element.id:
                data_map[item.element.id] = {
                    "label": item.element.label,
                    "server": item.data_model.server if item.data_model else None,
                    "table": item.data_model.table if item.data_model else None,
                }

        shortcut_map = {}
        for sc in project.shortcuts:
            if sc.metadata and sc.metadata.id:
                shortcut_map[sc.metadata.id] = {
                    "label": sc.metadata.label,
                    "parent_id": sc.parent_id,
                    "resolved_data": data_map.get(sc.parent_id),
                }

        if element_id:
            # Trace specific element
            elem_info = element_map.get(element_id)
            if not elem_info:
                return json.dumps({"error": f"Element not found: {element_id}"})

            inputs = []
            for input_id in elem_info.get("input_ids", []):
                if input_id in shortcut_map:
                    inputs.append({"type": "shortcut", **shortcut_map[input_id]})
                elif input_id in data_map:
                    inputs.append(
                        {"type": "data", "id": input_id, **data_map[input_id]}
                    )
                elif input_id in element_map:
                    inputs.append({"type": "element", **element_map[input_id]})

            # Find what depends on this element
            dependents = []
            for einfo in element_map.values():
                if element_id in einfo.get("input_ids", []):
                    dependents.append(einfo)

            return json.dumps(
                {
                    "element": elem_info,
                    "inputs": inputs,
                    "dependents": dependents,
                },
                indent=2,
                ensure_ascii=False,
            )
        else:
            # Full lineage summary
            lineage = []
            for eid, einfo in element_map.items():
                if einfo.get("input_ids"):
                    resolved_inputs = []
                    for iid in einfo["input_ids"]:
                        if iid in shortcut_map:
                            resolved_inputs.append(shortcut_map[iid])
                        elif iid in element_map:
                            resolved_inputs.append(
                                {"id": iid, "label": element_map[iid].get("label")}
                            )
                    if resolved_inputs:
                        lineage.append(
                            {
                                "element": {
                                    "id": eid,
                                    "label": einfo.get("label"),
                                    "type": einfo.get("type"),
                                },
                                "reads_from": resolved_inputs,
                            }
                        )
            return json.dumps({"lineage": lineage}, indent=2, ensure_ascii=False)
    except (ValueError, FileNotFoundError) as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_queries(file_path: str) -> str:
    """Extract all Query Builder queries from an EGP project.

    Returns the full query definitions including input tables, joins,
    filters, result columns, and calculated fields.

    Args:
        file_path: Absolute path to the .egp file.

    Returns:
        JSON with all query definitions.
    """
    path = Path(file_path)
    if not path.exists():
        return json.dumps({"error": f"File not found: {file_path}"})

    try:
        project = parse_file(path)
        queries = []
        for q in project.queries:
            query_info = {
                "label": q["metadata"].label if q.get("metadata") else None,
                "element_id": q["metadata"].id if q.get("metadata") else None,
            }
            if q.get("query_model"):
                qm = q["query_model"]
                query_info["input_tables"] = [
                    {"id": t.id, "name": t.input_table_name, "alias": t.alias}
                    for t in qm.input_tables
                ]
                query_info["result_columns"] = [
                    {"alias": r.alias, "table_id": r.table_id, "format": r.format}
                    for r in qm.result_items
                ]
                query_info["joins"] = [
                    {
                        "left_table": j.left_table_id,
                        "right_table": j.right_table_id,
                        "type": j.join_type,
                        "left_col": j.left_column_name,
                        "right_col": j.right_column_name,
                    }
                    for j in qm.join_items
                ]
                query_info["calculations"] = [
                    {"id": c.id, "alias": c.alias, "is_aggregate": c.is_aggregate}
                    for c in qm.calculations
                ]
                query_info["output"] = {
                    "library": qm.output_library,
                    "member": qm.output_member,
                    "type": qm.output_type,
                }
            queries.append(query_info)

        return json.dumps({"queries": queries}, indent=2, ensure_ascii=False)
    except (ValueError, FileNotFoundError) as e:
        return json.dumps({"error": str(e)})


def main() -> None:
    """Entry point for the ``pyegp-parser-mcp`` console script."""
    mcp.run()


if __name__ == "__main__":
    main()
