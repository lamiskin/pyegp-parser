"""Tests for pyegp_parser.serializer module.

Validates:
- to_dict() converts dataclass hierarchies with _type fields
- from_dict() reconstructs typed models from dicts
- serialize_project() writes deterministic JSON with sorted keys
- Round-trip consistency: to_dict → from_dict produces equivalent objects
- Deterministic output: same input always produces same bytes

Requirements: 15.1, 15.2, 15.6, 15.7, 15.11, 15.12, 15.15, 17.1, 17.2, 17.5
"""

import json
import tempfile
from pathlib import Path

import pytest

from pyegp_parser.models.base import ElementMetadata
from pyegp_parser.models.process_flow import Connection, DAGModel
from pyegp_parser.models.project import (
    BinaryEntry,
    CompletenessSummary,
    Parameter,
    ParsedProject,
    ProjectLogInfo,
    ProjectMetadata,
    ProjectSettings,
    SourceInfo,
)
from pyegp_parser.models.query import (
    Calculation,
    Expression,
    FilterNode,
    GroupItem,
    InputTable,
    JoinItem,
    OrderItem,
    QueryModel,
    ResultItem,
)
from pyegp_parser.parsers.dna_parser import DNADescriptor
from pyegp_parser.serializer import from_dict, serialize_project, to_dict


class TestToDict:
    """Tests for the to_dict() conversion function."""

    def test_none_returns_none(self):
        assert to_dict(None) is None

    def test_primitive_string_passthrough(self):
        assert to_dict("hello") == "hello"

    def test_primitive_int_passthrough(self):
        assert to_dict(42) == 42

    def test_primitive_float_passthrough(self):
        assert to_dict(3.14) == 3.14

    def test_primitive_bool_passthrough(self):
        assert to_dict(True) is True

    def test_list_of_primitives(self):
        assert to_dict([1, 2, 3]) == [1, 2, 3]

    def test_empty_list(self):
        assert to_dict([]) == []

    def test_dict_sorted_keys(self):
        """Dicts are serialized with sorted keys for determinism."""
        result = to_dict({"z": 1, "a": 2, "m": 3})
        keys = list(result.keys())
        assert keys == ["a", "m", "z"]

    def test_simple_dataclass_includes_type_field(self):
        """Every dataclass gets a _type field with the class name."""
        meta = ElementMetadata(label="Test", id="123")
        result = to_dict(meta)
        assert result["_type"] == "ElementMetadata"
        assert result["label"] == "Test"
        assert result["id"] == "123"

    def test_dataclass_none_fields_serialized(self):
        """None fields are included in the output."""
        meta = ElementMetadata()
        result = to_dict(meta)
        assert result["label"] is None
        assert result["type"] is None

    def test_nested_dataclass(self):
        """Nested dataclasses each get their own _type field."""
        conn = Connection(source_id="a", target_id="b", resource_dependency=True)
        dag = DAGModel(nodes=["a", "b"], connections=[conn])
        result = to_dict(dag)
        assert result["_type"] == "DAGModel"
        assert result["connections"][0]["_type"] == "Connection"
        assert result["connections"][0]["source_id"] == "a"

    def test_list_of_dataclasses(self):
        """Lists of dataclasses are converted recursively."""
        items = [
            Parameter(name="p1", value="v1"),
            Parameter(name="p2", value="v2"),
        ]
        result = to_dict(items)
        assert len(result) == 2
        assert result[0]["_type"] == "Parameter"
        assert result[0]["name"] == "p1"
        assert result[1]["name"] == "p2"

    def test_enum_serialized_as_value(self):
        """Enum instances are serialized as their .value."""
        from pyegp_parser.archive import EntryCategory

        assert to_dict(EntryCategory.PROJECT_XML) == "project_xml"
        assert to_dict(EntryCategory.UNKNOWN) == "unknown"

    def test_deeply_nested_structure(self):
        """Multi-level nesting preserves _type at all levels."""
        dna = DNADescriptor(
            type="SAS.Servers.ServerDef",
            name="SASApp",
            version="1.0",
            assembly=None,
            factory=None,
            parent_dna=DNADescriptor(
                type="SAS.Libraries.LibraryDef",
                name="WORK",
                version="1.0",
                assembly=None,
                factory=None,
            ),
        )
        result = to_dict(dna)
        assert result["_type"] == "DNADescriptor"
        assert result["parent_dna"]["_type"] == "DNADescriptor"
        assert result["parent_dna"]["name"] == "WORK"

    def test_parsed_project_top_level(self):
        """ParsedProject serialization includes _type and all sections."""
        project = ParsedProject(
            schema_version="1.0.0",
            parser_version="1.0.0",
            source=SourceInfo(
                file_path="/tmp/test.egp",
                file_name="test.egp",
                file_size_bytes=1024,
                parsed_at="2024-01-15T10:30:00",
                total_zip_entries=10,
            ),
        )
        result = to_dict(project)
        assert result["_type"] == "ParsedProject"
        assert result["source"]["_type"] == "SourceInfo"
        assert result["source"]["file_path"] == "/tmp/test.egp"

    def test_iso8601_timestamps_preserved(self):
        """ISO 8601 timestamps are preserved as strings (Req 15.12)."""
        meta = ElementMetadata(
            created_on="2024-01-15T10:30:00",
            modified_on="2024-06-20T14:00:00Z",
        )
        result = to_dict(meta)
        assert result["created_on"] == "2024-01-15T10:30:00"
        assert result["modified_on"] == "2024-06-20T14:00:00Z"

    def test_snake_case_field_names(self):
        """All field names use snake_case (Req 15.11)."""
        meta = ElementMetadata(
            modified_by_eg_id="user-1",
            modified_by_eg_ver="8.1",
            has_serialization_error=False,
        )
        result = to_dict(meta)
        assert "modified_by_eg_id" in result
        assert "modified_by_eg_ver" in result
        assert "has_serialization_error" in result


class TestFromDict:
    """Tests for the from_dict() reconstruction function."""

    def test_none_returns_none(self):
        assert from_dict(None) is None

    def test_primitive_passthrough(self):
        assert from_dict("hello") == "hello"
        assert from_dict(42) == 42
        assert from_dict(True) is True

    def test_list_passthrough(self):
        assert from_dict([1, 2, 3]) == [1, 2, 3]

    def test_simple_dataclass_reconstruction(self):
        """from_dict reconstructs a typed dataclass from a dict with _type."""
        data = {
            "_type": "ElementMetadata",
            "label": "Test",
            "id": "123",
            "type": None,
            "container": None,
            "created_on": None,
            "modified_on": None,
            "modified_by": None,
            "modified_by_eg_id": None,
            "modified_by_eg_ver": None,
            "has_serialization_error": None,
            "input_ids": [],
        }
        result = from_dict(data)
        assert isinstance(result, ElementMetadata)
        assert result.label == "Test"
        assert result.id == "123"
        assert result.input_ids == []

    def test_nested_dataclass_reconstruction(self):
        """Nested _type dicts are recursively reconstructed."""
        data = {
            "_type": "DAGModel",
            "nodes": ["a", "b"],
            "connections": [
                {
                    "_type": "Connection",
                    "source_id": "a",
                    "target_id": "b",
                    "resource_dependency": True,
                }
            ],
            "warnings": [],
        }
        result = from_dict(data)
        assert isinstance(result, DAGModel)
        assert result.nodes == ["a", "b"]
        assert isinstance(result.connections[0], Connection)
        assert result.connections[0].source_id == "a"

    def test_unknown_type_raises_valueerror(self):
        """from_dict raises ValueError for unknown _type values."""
        data = {"_type": "NonExistentType", "foo": "bar"}
        with pytest.raises(ValueError, match="Unknown _type 'NonExistentType'"):
            from_dict(data)

    def test_missing_fields_use_defaults(self):
        """Fields not in the dict use dataclass defaults."""
        data = {"_type": "ElementMetadata", "label": "Partial"}
        result = from_dict(data)
        assert isinstance(result, ElementMetadata)
        assert result.label == "Partial"
        assert result.id is None
        assert result.input_ids == []

    def test_plain_dict_without_type(self):
        """Dicts without _type are reconstructed as plain dicts."""
        data = {"key": "value", "nested": {"inner": 42}}
        result = from_dict(data)
        assert result == {"key": "value", "nested": {"inner": 42}}

    def test_dna_descriptor_with_parent(self):
        """DNADescriptor with nested parent_dna is fully reconstructed."""
        data = {
            "_type": "DNADescriptor",
            "type": "SAS.Servers.ServerDef",
            "name": "SASApp",
            "version": "1.0",
            "assembly": None,
            "factory": None,
            "parent_name": None,
            "display_name": None,
            "display_path": None,
            "server": None,
            "library": None,
            "full_path": None,
            "read_only": None,
            "temp": None,
            "parent_dna": {
                "_type": "DNADescriptor",
                "type": "SAS.Libraries.LibraryDef",
                "name": "WORK",
                "version": "1.0",
                "assembly": None,
                "factory": None,
                "parent_name": None,
                "display_name": None,
                "display_path": None,
                "server": None,
                "library": None,
                "full_path": None,
                "read_only": None,
                "temp": None,
                "parent_dna": None,
            },
        }
        result = from_dict(data)
        assert isinstance(result, DNADescriptor)
        assert result.name == "SASApp"
        assert isinstance(result.parent_dna, DNADescriptor)
        assert result.parent_dna.name == "WORK"


class TestRoundTrip:
    """Tests for round-trip consistency: to_dict → from_dict (Req 17.2)."""

    def test_element_metadata_round_trip(self):
        original = ElementMetadata(
            label="My Task",
            type="SAS.EG.ProjectElements.Query",
            container="c-1",
            id="e-1",
            created_on="2024-01-15T10:30:00",
            modified_on="2024-06-20T14:00:00",
            modified_by="User",
            modified_by_eg_id="uid-1",
            modified_by_eg_ver="8.1",
            has_serialization_error=False,
            input_ids=["i-1", "i-2"],
        )
        reconstructed = from_dict(to_dict(original))
        assert reconstructed == original

    def test_parameter_round_trip(self):
        original = Parameter(name="param1", value="val1")
        reconstructed = from_dict(to_dict(original))
        assert reconstructed == original

    def test_connection_round_trip(self):
        original = Connection(source_id="a", target_id="b", resource_dependency=True)
        reconstructed = from_dict(to_dict(original))
        assert reconstructed == original

    def test_dag_model_round_trip(self):
        original = DAGModel(
            nodes=["a", "b", "c"],
            connections=[
                Connection(source_id="a", target_id="b", resource_dependency=False),
                Connection(source_id="b", target_id="c", resource_dependency=True),
            ],
            warnings=["Warning: missing ref"],
        )
        reconstructed = from_dict(to_dict(original))
        assert reconstructed == original

    def test_dna_descriptor_nested_round_trip(self):
        original = DNADescriptor(
            type="SAS.Servers.ServerDef",
            name="SASApp",
            version="1.0",
            assembly="SAS.Tasks.dll",
            factory="SAS.Factory",
            parent_name="parent",
            display_name="Server",
            display_path="/path",
            server="SASApp",
            library="WORK",
            full_path=None,
            read_only=True,
            temp=False,
            parent_dna=DNADescriptor(
                type="SAS.Libraries.LibraryDef",
                name="WORK",
                version="1.0",
                assembly=None,
                factory=None,
            ),
        )
        reconstructed = from_dict(to_dict(original))
        assert reconstructed == original

    def test_query_model_round_trip(self):
        original = QueryModel(
            use_explicit_and_execute=True,
            output_library="WORK",
            output_member="output",
            input_tables=[
                InputTable(id="t1", input_table_name="TABLE1", alias="a"),
            ],
            result_items=[
                ResultItem(result_id="r1", alias="col1", table_id="t1"),
            ],
            calculations=[
                Calculation(
                    id="c1",
                    alias="calc_col",
                    expression=Expression(
                        expression_type="function",
                        expression_text="SUM(x)",
                        sub_expressions=[
                            Expression(expression_type="column", expression_text="x")
                        ],
                    ),
                )
            ],
            join_items=[
                JoinItem(left_table_id="t1", right_table_id="t2", join_type="INNER")
            ],
            where_filters=[
                FilterNode(
                    filter_type="simple",
                    column_name="status",
                    operator="=",
                    value="active",
                )
            ],
            order_items=[
                OrderItem(table_id="t1", column_name="id", sort_direction="ASC")
            ],
            group_items=[GroupItem(table_id="t1", column_name="category")],
        )
        reconstructed = from_dict(to_dict(original))
        assert reconstructed == original

    def test_parsed_project_round_trip(self):
        """Full ParsedProject survives round-trip through to_dict/from_dict."""
        original = ParsedProject(
            schema_version="1.0.0",
            parser_version="1.0.0",
            source=SourceInfo(
                file_path="/tmp/test.egp",
                file_name="test.egp",
                file_size_bytes=2048,
                parsed_at="2024-01-15T10:30:00",
                total_zip_entries=15,
            ),
            metadata=ProjectMetadata(
                eg_version="8.1",
                type="Project",
                label="Test Project",
                id="proj-1",
            ),
            settings=ProjectSettings(
                use_relative_paths=True,
                submit_to_grid=False,
                project_log_max_size=100,
            ),
            parameters=[
                Parameter(name="p1", value="v1"),
            ],
            project_log=ProjectLogInfo(
                enabled=True, written_to=True, content="log text"
            ),
            completeness_summary=CompletenessSummary(
                total_entries=15, processed_entries=12, unprocessed_entries=3
            ),
            binary_entries=[
                BinaryEntry(
                    path="ODSResults/ODSResult-1/result.pptx",
                    compressed_size=5000,
                    file_extension=".pptx",
                    task_id="task-1",
                )
            ],
        )
        reconstructed = from_dict(to_dict(original))
        assert reconstructed == original


class TestSerializeProject:
    """Tests for serialize_project() file output (Req 15.6, 15.7, 17.1)."""

    def test_creates_output_directory_recursively(self):
        """Output directory is created recursively if it does not exist (Req 15.7)."""
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "nested" / "deep" / "dir"
            project = ParsedProject()
            serialize_project(project, output_dir)
            assert output_dir.exists()
            assert (output_dir / "project.json").exists()

    def test_writes_utf8_encoded_file(self):
        """Output file uses UTF-8 encoding (Req 15.6)."""
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            project = ParsedProject(metadata=ProjectMetadata(label="Ünîcödé Prøject"))
            serialize_project(project, output_dir)
            content = (output_dir / "project.json").read_bytes()
            # Verify it's valid UTF-8 containing our unicode chars
            text = content.decode("utf-8")
            assert "Ünîcödé Prøject" in text

    def test_2_space_indentation(self):
        """Output uses 2-space indentation (Req 15.6)."""
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            project = ParsedProject(metadata=ProjectMetadata(label="Test"))
            json_str = serialize_project(project, output_dir)
            # Verify 2-space indentation (not 4-space or tabs)
            lines = json_str.split("\n")
            indented_lines = [
                l for l in lines if l.startswith("  ") and not l.startswith("    ")
            ]
            assert len(indented_lines) > 0

    def test_sorted_keys(self):
        """Output has sorted keys at all levels for determinism (Req 17.1)."""
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            project = ParsedProject(metadata=ProjectMetadata(label="Test", id="p1"))
            json_str = serialize_project(project, output_dir)
            data = json.loads(json_str)
            # Top-level keys should be sorted
            keys = list(data.keys())
            assert keys == sorted(keys)
            # Nested keys should also be sorted
            if data.get("metadata"):
                meta_keys = list(data["metadata"].keys())
                assert meta_keys == sorted(meta_keys)

    def test_deterministic_output(self):
        """Same input produces identical JSON bytes (Req 17.1)."""
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            project = ParsedProject(
                schema_version="1.0.0",
                parser_version="1.0.0",
                source=SourceInfo(
                    file_path="/test.egp",
                    file_name="test.egp",
                    file_size_bytes=100,
                    parsed_at="2024-01-01T00:00:00",
                    total_zip_entries=5,
                ),
                parameters=[
                    Parameter(name="b", value="2"),
                    Parameter(name="a", value="1"),
                ],
            )
            json_str1 = serialize_project(project, output_dir)
            json_str2 = serialize_project(project, output_dir)
            assert json_str1 == json_str2

    def test_round_trip_produces_identical_json(self):
        """serialize → deserialize → re-serialize produces identical bytes (Req 17.2)."""
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            project = ParsedProject(
                schema_version="1.0.0",
                parser_version="1.0.0",
                source=SourceInfo(
                    file_path="/test.egp",
                    file_name="test.egp",
                    file_size_bytes=100,
                    parsed_at="2024-01-01T00:00:00",
                    total_zip_entries=5,
                ),
                metadata=ProjectMetadata(label="Test", id="proj-1"),
                parameters=[Parameter(name="p1", value="v1")],
            )
            # First serialize
            json_str1 = serialize_project(project, output_dir)
            # Deserialize from JSON
            data = json.loads(json_str1)
            reconstructed = from_dict(data)
            # Re-serialize
            json_str2 = serialize_project(reconstructed, output_dir)
            assert json_str1 == json_str2

    def test_returns_json_string(self):
        """serialize_project returns the JSON string that was written."""
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            project = ParsedProject()
            result = serialize_project(project, output_dir)
            assert isinstance(result, str)
            # Should be valid JSON
            json.loads(result)

    def test_output_file_matches_returned_string(self):
        """The file content matches what was returned."""
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            project = ParsedProject(metadata=ProjectMetadata(label="File Check"))
            json_str = serialize_project(project, output_dir)
            file_content = (output_dir / "project.json").read_text(encoding="utf-8")
            assert file_content == json_str

    def test_type_field_on_every_object(self):
        """Every dataclass object has a _type field in the output (Req 15.1)."""
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            project = ParsedProject(
                source=SourceInfo(
                    file_path="/test.egp",
                    file_name="test.egp",
                    file_size_bytes=100,
                    parsed_at="2024-01-01T00:00:00",
                    total_zip_entries=5,
                ),
                metadata=ProjectMetadata(label="Test"),
                completeness_summary=CompletenessSummary(total_entries=5),
            )
            json_str = serialize_project(project, output_dir)
            data = json.loads(json_str)
            # Root has _type
            assert data["_type"] == "ParsedProject"
            # Nested objects have _type
            assert data["source"]["_type"] == "SourceInfo"
            assert data["metadata"]["_type"] == "ProjectMetadata"
            assert data["completeness_summary"]["_type"] == "CompletenessSummary"
