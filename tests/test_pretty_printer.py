"""Tests for the EGP pretty printer module.

Validates Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6
"""

import json

import pytest

from pyegp_parser.pretty_printer import pretty_print

# --- Test fixtures ---

MINIMAL_PROJECT = {
    "_type": "ParsedProject",
    "_schema_version": "1.0.0",
    "parser_version": "1.0.0",
    "source": {
        "_type": "SourceInfo",
        "file_name": "test.egp",
        "file_path": "/path/to/test.egp",
        "file_size_bytes": 12345,
        "parsed_at": "2024-01-01T00:00:00",
        "total_zip_entries": 10,
    },
    "metadata": {
        "_type": "ProjectMetadata",
        "label": "Test Project",
        "eg_version": "8.1",
        "type": "SAS.EG.Project",
        "id": "proj-001",
        "created_on": "2024-01-01T00:00:00",
        "modified_on": "2024-06-15T12:00:00",
        "modified_by": "testuser",
    },
    "elements": [],
    "containers": [],
    "data_list": [],
    "external_files": [],
    "completeness_summary": {
        "_type": "CompletenessSummary",
        "total_entries": 10,
        "processed_entries": 8,
        "unprocessed_entries": 2,
    },
}

PROJECT_WITH_CODE_TASK = {
    "_type": "ParsedProject",
    "_schema_version": "1.0.0",
    "source": {
        "_type": "SourceInfo",
        "file_name": "code.egp",
        "file_path": "/path/to/code.egp",
        "file_size_bytes": 5000,
        "parsed_at": "2024-01-01T00:00:00",
        "total_zip_entries": 5,
    },
    "metadata": {
        "_type": "ProjectMetadata",
        "label": "Code Project",
    },
    "elements": [
        {
            "_type": "CodeTaskElement",
            "metadata": {
                "_type": "ElementMetadata",
                "label": "My Code Task",
                "id": "ct-001",
            },
            "code_content": "proc print data=work.test;\nrun;",
        }
    ],
    "containers": [],
    "data_list": [],
    "external_files": [],
}

PROJECT_WITH_LONG_CODE = {
    "_type": "ParsedProject",
    "_schema_version": "1.0.0",
    "source": {
        "_type": "SourceInfo",
        "file_name": "long.egp",
        "file_path": "/path/to/long.egp",
        "file_size_bytes": 9000,
        "parsed_at": "2024-01-01T00:00:00",
        "total_zip_entries": 3,
    },
    "metadata": {"_type": "ProjectMetadata", "label": "Long Code"},
    "elements": [
        {
            "_type": "CodeTaskElement",
            "metadata": {
                "_type": "ElementMetadata",
                "label": "Long Code Task",
                "id": "ct-long",
            },
            "code_content": "\n".join([f"/* line {i} */" for i in range(1, 61)]),
        }
    ],
    "containers": [],
    "data_list": [],
    "external_files": [],
}

PROJECT_WITH_PROCESS_FLOW = {
    "_type": "ParsedProject",
    "_schema_version": "1.0.0",
    "source": {
        "_type": "SourceInfo",
        "file_name": "flow.egp",
        "file_path": "/path/to/flow.egp",
        "file_size_bytes": 7000,
        "parsed_at": "2024-01-01T00:00:00",
        "total_zip_entries": 8,
    },
    "metadata": {"_type": "ProjectMetadata", "label": "Flow Project"},
    "elements": [
        {
            "_type": "CodeTaskElement",
            "metadata": {
                "_type": "ElementMetadata",
                "label": "Load Data",
                "id": "elem-1",
            },
        },
        {
            "_type": "CodeTaskElement",
            "metadata": {
                "_type": "ElementMetadata",
                "label": "Transform",
                "id": "elem-2",
            },
        },
        {
            "_type": "CodeTaskElement",
            "metadata": {
                "_type": "ElementMetadata",
                "label": "Export",
                "id": "elem-3",
            },
        },
    ],
    "containers": [
        {
            "_type": "ProcessFlowContainer",
            "metadata": {
                "_type": "ElementMetadata",
                "label": "Main Flow",
                "id": "pf-001",
            },
            "dag": {
                "_type": "DAGModel",
                "nodes": ["elem-1", "elem-2", "elem-3"],
                "connections": [
                    {
                        "_type": "Connection",
                        "source_id": "elem-1",
                        "target_id": "elem-2",
                        "resource_dependency": False,
                    },
                    {
                        "_type": "Connection",
                        "source_id": "elem-2",
                        "target_id": "elem-3",
                        "resource_dependency": True,
                    },
                ],
                "warnings": [],
            },
        }
    ],
    "data_list": [],
    "external_files": [],
}

PROJECT_WITH_QUERY = {
    "_type": "ParsedProject",
    "_schema_version": "1.0.0",
    "source": {
        "_type": "SourceInfo",
        "file_name": "query.egp",
        "file_path": "/path/to/query.egp",
        "file_size_bytes": 6000,
        "parsed_at": "2024-01-01T00:00:00",
        "total_zip_entries": 4,
    },
    "metadata": {"_type": "ProjectMetadata", "label": "Query Project"},
    "elements": [
        {
            "_type": "Query",
            "metadata": {
                "_type": "ElementMetadata",
                "label": "Customer Query",
                "id": "q-001",
            },
            "query_model": {
                "_type": "QueryModel",
                "output_library": "WORK",
                "output_member": "RESULTS",
                "input_tables": [
                    {
                        "_type": "InputTable",
                        "id": "it-1",
                        "input_table_name": "CUSTOMERS",
                        "alias": "c",
                    },
                    {
                        "_type": "InputTable",
                        "id": "it-2",
                        "input_table_name": "ORDERS",
                        "alias": "o",
                    },
                ],
                "result_items": [
                    {
                        "_type": "ResultItem",
                        "alias": "name",
                        "table_id": "it-1",
                        "base_column_name": "name",
                    },
                    {
                        "_type": "ResultItem",
                        "alias": "total",
                        "table_id": "it-2",
                        "base_column_name": "amount",
                    },
                ],
                "join_items": [
                    {
                        "_type": "JoinItem",
                        "left_table_id": "it-1",
                        "left_column_name": "id",
                        "right_table_id": "it-2",
                        "right_column_name": "customer_id",
                        "join_operator": "=",
                        "join_type": "INNER JOIN",
                    }
                ],
                "where_filters": [
                    {
                        "_type": "FilterNode",
                        "column_name": "status",
                        "operator": "=",
                        "value": "'active'",
                        "children": [],
                    }
                ],
                "having_filters": [],
                "order_items": [
                    {
                        "_type": "OrderItem",
                        "column_name": "name",
                        "sort_direction": "ASC",
                    }
                ],
                "group_items": [],
                "query_builder_settings": [],
                "calculations": [],
            },
        }
    ],
    "containers": [],
    "data_list": [],
    "external_files": [],
}


# --- Tests ---


class TestPrettyPrintInputValidation:
    """Test Requirement 16.6: ValueError for invalid input."""

    def test_invalid_json_string_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid JSON"):
            pretty_print("not valid json {{{")

    def test_non_dict_input_raises_value_error(self):
        with pytest.raises(ValueError, match="Expected a JSON string or dict"):
            pretty_print(12345)  # type: ignore

    def test_list_json_raises_value_error(self):
        with pytest.raises(ValueError, match="must represent an object"):
            pretty_print("[]")

    def test_missing_type_field_raises_value_error(self):
        with pytest.raises(ValueError, match="missing '_type' field"):
            pretty_print({"some_key": "some_value"})

    def test_empty_string_raises_value_error(self):
        with pytest.raises(ValueError):
            pretty_print("")


class TestPrettyPrintProjectMetadata:
    """Test Requirement 16.1: Display project metadata."""

    def test_shows_project_header(self):
        result = pretty_print(MINIMAL_PROJECT)
        assert "=== EGP Project ===" in result

    def test_shows_source_filename(self):
        result = pretty_print(MINIMAL_PROJECT)
        assert "test.egp" in result

    def test_shows_metadata_label(self):
        result = pretty_print(MINIMAL_PROJECT)
        assert "Test Project" in result

    def test_shows_eg_version(self):
        result = pretty_print(MINIMAL_PROJECT)
        assert "8.1" in result

    def test_shows_modified_by(self):
        result = pretty_print(MINIMAL_PROJECT)
        assert "testuser" in result

    def test_accepts_json_string(self):
        json_str = json.dumps(MINIMAL_PROJECT)
        result = pretty_print(json_str)
        assert "=== EGP Project ===" in result
        assert "Test Project" in result

    def test_shows_completeness_summary(self):
        result = pretty_print(MINIMAL_PROJECT)
        assert "Total entries: 10" in result
        assert "Processed: 8" in result
        assert "Unprocessed: 2" in result


class TestPrettyPrintIndentation:
    """Test Requirement 16.2: 2-space indentation for nesting."""

    def test_elements_are_indented(self):
        result = pretty_print(PROJECT_WITH_CODE_TASK)
        lines = result.split("\n")
        # Find the code task line - it should be indented
        code_task_lines = [l for l in lines if "My Code Task" in l]
        assert len(code_task_lines) == 1
        # Should have 2 spaces of indentation (nested inside elements section)
        assert code_task_lines[0].startswith("  ")

    def test_code_content_further_indented(self):
        result = pretty_print(PROJECT_WITH_CODE_TASK)
        lines = result.split("\n")
        # Code lines should be indented further than the element line
        code_lines = [l for l in lines if "proc print" in l]
        assert len(code_lines) == 1
        # Should have at least 4 spaces (element + code indentation)
        assert code_lines[0].startswith("    ")


class TestPrettyPrintProcessFlow:
    """Test Requirement 16.3: Arrow notation for process flow connections."""

    def test_shows_process_flow_section(self):
        result = pretty_print(PROJECT_WITH_PROCESS_FLOW)
        assert "Process Flows" in result

    def test_shows_flow_label(self):
        result = pretty_print(PROJECT_WITH_PROCESS_FLOW)
        assert "Main Flow" in result

    def test_shows_execution_arrow(self):
        result = pretty_print(PROJECT_WITH_PROCESS_FLOW)
        assert '"Load Data" -[execution]-> "Transform"' in result

    def test_shows_resource_arrow(self):
        result = pretty_print(PROJECT_WITH_PROCESS_FLOW)
        assert '"Transform" -[resource]-> "Export"' in result

    def test_shows_nodes(self):
        result = pretty_print(PROJECT_WITH_PROCESS_FLOW)
        assert "Nodes (3)" in result
        assert "Load Data" in result
        assert "Transform" in result
        assert "Export" in result


class TestPrettyPrintCodeTruncation:
    """Test Requirement 16.4: Code truncated at 50 lines."""

    def test_short_code_not_truncated(self):
        result = pretty_print(PROJECT_WITH_CODE_TASK)
        assert "[...truncated]" not in result
        assert "proc print" in result

    def test_long_code_truncated_at_50_lines(self):
        result = pretty_print(PROJECT_WITH_LONG_CODE)
        assert "[...truncated]" in result
        # Line 50 should be present
        assert "/* line 50 */" in result
        # Line 51 should NOT be present
        assert "/* line 51 */" not in result


class TestPrettyPrintQuerySQL:
    """Test Requirement 16.5: Display generated SQL for Query elements."""

    def test_shows_generated_sql_header(self):
        result = pretty_print(PROJECT_WITH_QUERY)
        assert "Generated SQL" in result

    def test_shows_select_clause(self):
        result = pretty_print(PROJECT_WITH_QUERY)
        assert "SELECT" in result

    def test_shows_from_clause(self):
        result = pretty_print(PROJECT_WITH_QUERY)
        assert "FROM CUSTOMERS" in result

    def test_shows_join(self):
        result = pretty_print(PROJECT_WITH_QUERY)
        assert "INNER JOIN" in result

    def test_shows_where_clause(self):
        result = pretty_print(PROJECT_WITH_QUERY)
        assert "WHERE" in result
        assert "status" in result

    def test_shows_order_by(self):
        result = pretty_print(PROJECT_WITH_QUERY)
        assert "ORDER BY" in result

    def test_shows_output_comment(self):
        result = pretty_print(PROJECT_WITH_QUERY)
        assert "WORK.RESULTS" in result


class TestPrettyPrintDataItems:
    """Test data items are shown in the output."""

    def test_shows_data_items(self):
        project = {
            **MINIMAL_PROJECT,
            "data_list": [
                {
                    "_type": "DataItem",
                    "element": {
                        "_type": "ElementMetadata",
                        "label": "My Dataset",
                        "id": "d-001",
                    },
                    "data_model": {
                        "_type": "DataModel",
                        "server": "SASApp",
                        "table": "WORK.MYTABLE",
                        "display_name": "My Table",
                    },
                }
            ],
        }
        result = pretty_print(project)
        assert "Data Items (1)" in result
        assert "My Dataset" in result
        assert "SASApp" in result
        assert "WORK.MYTABLE" in result
