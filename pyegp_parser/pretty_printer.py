"""Pretty printer for parsed EGP project JSON output.

Produces human-readable text summaries from the self-describing JSON
document produced by the EGP parser.

Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6
"""

import json


def pretty_print(json_input: str | dict) -> str:
    """Produce a human-readable text representation of a parsed EGP project.

    Accepts either a JSON string or a pre-parsed dict with _type fields.
    Formats project metadata, elements, and process flow connections.

    Args:
        json_input: Either a JSON string or a pre-parsed dict with _type fields.

    Returns:
        Multi-line string with indented structure.

    Raises:
        ValueError: If input is invalid or cannot be deserialized.
    """
    if isinstance(json_input, str):
        try:
            data = json.loads(json_input)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON input: {e}") from e
    elif isinstance(json_input, dict):
        data = json_input
    else:
        raise ValueError("Expected a JSON string or dict")

    if isinstance(data, list):
        raise ValueError("JSON input must represent an object, not a list")

    if not isinstance(data, dict):
        raise ValueError("JSON input must represent an object")

    if "_type" not in data:
        raise ValueError("JSON input is missing '_type' field")

    lines: list[str] = []
    lines.extend(_format_project(data))
    return "\n".join(lines)


def _format_project(project: dict, indent: int = 0) -> list[str]:
    """Format the project-level metadata."""
    prefix = " " * indent
    lines: list[str] = []

    # Header
    lines.append(f"{prefix}=== EGP Project ===")

    # Source info
    source = project.get("source")
    if source and isinstance(source, dict):
        lines.append(f"{prefix}Source: {source.get('file_name', 'unknown')}")
        lines.append(f"{prefix}Path: {source.get('file_path', 'unknown')}")
        lines.append(f"{prefix}Size: {source.get('file_size_bytes', 0)} bytes")
        lines.append(f"{prefix}ZIP Entries: {source.get('total_zip_entries', 0)}")
        lines.append(f"{prefix}Parsed at: {source.get('parsed_at', 'unknown')}")

    # Metadata
    metadata = project.get("metadata")
    if metadata and isinstance(metadata, dict):
        lines.append(f"{prefix}")
        lines.append(f"{prefix}--- Metadata ---")
        if metadata.get("label"):
            lines.append(f"{prefix}Label: {metadata.get('label')}")
        if metadata.get("eg_version"):
            lines.append(f"{prefix}EG Version: {metadata.get('eg_version')}")
        if metadata.get("type"):
            lines.append(f"{prefix}Type: {metadata.get('type')}")
        if metadata.get("modified_by"):
            lines.append(f"{prefix}Modified by: {metadata.get('modified_by')}")
        if metadata.get("modified_on"):
            lines.append(f"{prefix}Modified on: {metadata.get('modified_on')}")

    # Data items
    data_list = project.get("data_list", [])
    if data_list:
        lines.append(f"{prefix}")
        lines.append(f"{prefix}--- Data Items ({len(data_list)}) ---")
        for item in data_list:
            if isinstance(item, dict):
                lines.extend(_format_data_item(item, indent + 2))

    # Elements
    elements = project.get("elements", [])
    if elements:
        lines.append(f"{prefix}")
        lines.append(f"{prefix}--- Elements ({len(elements)}) ---")
        for elem in elements:
            if isinstance(elem, dict):
                lines.extend(_format_element(elem, indent + 2))

    # Containers / process flows
    containers = project.get("containers", [])
    if containers:
        lines.append(f"{prefix}")
        lines.append(f"{prefix}--- Process Flows ({len(containers)}) ---")
        for container in containers:
            if isinstance(container, dict):
                lines.extend(_format_process_flow(container, indent + 2, elements))

    # Completeness
    summary = project.get("completeness_summary")
    if summary and isinstance(summary, dict):
        lines.append(f"{prefix}")
        lines.append(f"{prefix}--- Completeness ---")
        lines.append(f"{prefix}Total entries: {summary.get('total_entries', 0)}")
        lines.append(f"{prefix}Processed: {summary.get('processed_entries', 0)}")
        lines.append(f"{prefix}Unprocessed: {summary.get('unprocessed_entries', 0)}")

    return lines


def _format_data_item(item: dict, indent: int = 0) -> list[str]:
    """Format a single data item."""
    prefix = " " * indent
    lines: list[str] = []

    element = item.get("element", {})
    label = (
        element.get("label", "Untitled") if isinstance(element, dict) else "Untitled"
    )
    lines.append(f"{prefix}[DataItem] {label}")

    data_model = item.get("data_model", {})
    if isinstance(data_model, dict):
        if data_model.get("server"):
            lines.append(f"{prefix}  Server: {data_model['server']}")
        if data_model.get("table"):
            lines.append(f"{prefix}  Table: {data_model['table']}")
        if data_model.get("display_name"):
            lines.append(f"{prefix}  Display: {data_model['display_name']}")

    return lines


def _format_element(element: dict, indent: int = 0) -> list[str]:
    """Format a single element."""
    prefix = " " * indent
    lines: list[str] = []

    elem_type = element.get("_type", "Unknown")
    metadata = element.get("metadata", {})
    label = (
        metadata.get("label", "Untitled") if isinstance(metadata, dict) else "Untitled"
    )

    lines.append(f"{prefix}[{elem_type}] {label}")

    # Show code for CodeTask elements (truncated at 50 lines)
    code_content = element.get("code_content")
    if code_content and isinstance(code_content, str):
        lines.extend(_format_code(code_content, indent + 2))

    # Show generated SQL for Query elements
    query_model = element.get("query_model")
    if query_model and isinstance(query_model, dict):
        sql = _generate_sql(query_model)
        if sql:
            lines.append(f"{prefix}  Generated SQL:")
            for sql_line in sql.split("\n"):
                lines.append(f"{prefix}    {sql_line}")

    return lines


def _format_process_flow(
    container: dict, indent: int = 0, all_elements: list | None = None
) -> list[str]:
    """Format a process flow with connections shown as arrows.

    Connection format: "Source Label" -[resource|execution]-> "Target Label"
    """
    prefix = " " * indent
    lines: list[str] = []

    metadata = container.get("metadata", {})
    label = (
        metadata.get("label", "Untitled") if isinstance(metadata, dict) else "Untitled"
    )
    lines.append(f"{prefix}Flow: {label}")

    # Build ID → label lookup from all elements
    id_to_label: dict[str, str] = {}
    if all_elements:
        for elem in all_elements:
            if isinstance(elem, dict):
                elem_meta = elem.get("metadata", {})
                if isinstance(elem_meta, dict):
                    eid = elem_meta.get("id")
                    elabel = elem_meta.get("label", "Unknown")
                    if eid:
                        id_to_label[eid] = elabel

    dag = container.get("dag")
    if dag and isinstance(dag, dict):
        nodes = dag.get("nodes", [])
        connections = dag.get("connections", [])

        if nodes:
            lines.append(f"{prefix}  Nodes ({len(nodes)}):")
            for node_id in nodes:
                node_label = id_to_label.get(node_id, node_id)
                lines.append(f"{prefix}    - {node_label}")

        if connections:
            lines.append(f"{prefix}  Connections:")
            for conn in connections:
                if isinstance(conn, dict):
                    source_id = conn.get("source_id", "?")
                    target_id = conn.get("target_id", "?")
                    source_label = id_to_label.get(source_id, source_id)
                    target_label = id_to_label.get(target_id, target_id)
                    dep_type = (
                        "resource" if conn.get("resource_dependency") else "execution"
                    )
                    lines.append(
                        f'{prefix}    "{source_label}" -[{dep_type}]-> "{target_label}"'
                    )

    return lines


def _format_code(code: str, indent: int = 0, max_lines: int = 50) -> list[str]:
    """Format SAS code with truncation at 50 lines.

    Args:
        code: The SAS code string.
        indent: Number of spaces to indent.
        max_lines: Maximum lines to display before truncation.

    Returns:
        List of indented code lines.
    """
    prefix = " " * indent
    code_lines = code.split("\n")
    if len(code_lines) > max_lines:
        code_lines = [*code_lines[:max_lines], "[...truncated]"]
    return [f"{prefix}{line}" for line in code_lines]


def _generate_sql(query_model: dict) -> str | None:
    """Generate a SQL representation from a QueryModel dict.

    Produces a human-readable SQL statement from the query model components.

    Args:
        query_model: The query model dict with input_tables, result_items, etc.

    Returns:
        SQL string or None if insufficient data.
    """
    parts: list[str] = []

    # Output comment
    output_lib = query_model.get("output_library", "")
    output_member = query_model.get("output_member", "")
    if output_lib and output_member:
        parts.append(f"/* Output: {output_lib}.{output_member} */")

    # SELECT clause
    result_items = query_model.get("result_items", [])
    if result_items:
        columns: list[str] = []
        for item in result_items:
            if isinstance(item, dict):
                alias = item.get("alias", "")
                base_col = item.get("base_column_name", "")
                col_str = base_col or alias or "*"
                columns.append(col_str)
        if columns:
            parts.append(f"SELECT {', '.join(columns)}")
    else:
        parts.append("SELECT *")

    # FROM clause
    input_tables = query_model.get("input_tables", [])
    if input_tables:
        first_table = input_tables[0]
        if isinstance(first_table, dict):
            table_name = first_table.get("input_table_name", "?")
            alias = first_table.get("alias", "")
            from_str = f"FROM {table_name}"
            if alias:
                from_str += f" {alias}"
            parts.append(from_str)

    # JOIN clauses
    join_items = query_model.get("join_items", [])
    for _i, join in enumerate(join_items):
        if isinstance(join, dict):
            join_type = join.get("join_type", "JOIN")
            # Look up the right table from input_tables
            right_table_id = join.get("right_table_id", "")
            right_table_name = "?"
            for tbl in input_tables:
                if isinstance(tbl, dict) and tbl.get("id") == right_table_id:
                    right_table_name = tbl.get("input_table_name", "?")
                    break
            right_alias = ""
            for tbl in input_tables:
                if isinstance(tbl, dict) and tbl.get("id") == right_table_id:
                    right_alias = tbl.get("alias", "")
                    break

            join_str = f"{join_type} {right_table_name}"
            if right_alias:
                join_str += f" {right_alias}"

            left_col = join.get("left_column_name", "?")
            right_col = join.get("right_column_name", "?")
            operator = join.get("join_operator", "=")
            join_str += f" ON {left_col} {operator} {right_col}"
            parts.append(join_str)

    # WHERE clause
    where_filters = query_model.get("where_filters", [])
    if where_filters:
        conditions = _format_filters(where_filters)
        if conditions:
            parts.append(f"WHERE {conditions}")

    # GROUP BY clause
    group_items = query_model.get("group_items", [])
    if group_items:
        cols = []
        for item in group_items:
            if isinstance(item, dict):
                cols.append(item.get("column_name", "?"))
        if cols:
            parts.append(f"GROUP BY {', '.join(cols)}")

    # HAVING clause
    having_filters = query_model.get("having_filters", [])
    if having_filters:
        conditions = _format_filters(having_filters)
        if conditions:
            parts.append(f"HAVING {conditions}")

    # ORDER BY clause
    order_items = query_model.get("order_items", [])
    if order_items:
        cols = []
        for item in order_items:
            if isinstance(item, dict):
                col = item.get("column_name", "?")
                direction = item.get("sort_direction", "")
                if direction:
                    cols.append(f"{col} {direction}")
                else:
                    cols.append(col)
        if cols:
            parts.append(f"ORDER BY {', '.join(cols)}")

    if not parts:
        return None

    return "\n".join(parts)


def _format_filters(filters: list) -> str:
    """Format filter nodes into a SQL condition string."""
    conditions: list[str] = []
    for f in filters:
        if isinstance(f, dict):
            col = f.get("column_name", "?")
            operator = f.get("operator", "=")
            value = f.get("value", "?")
            conditions.append(f"{col} {operator} {value}")
            # Handle children recursively
            children = f.get("children", [])
            if children:
                child_conds = _format_filters(children)
                if child_conds:
                    conditions.append(child_conds)
    return " AND ".join(conditions)
