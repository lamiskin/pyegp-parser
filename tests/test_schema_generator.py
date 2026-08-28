"""Unit tests for the JSON Schema generator.

Validates Requirements 15.13 and 15.14:
- Schema file is written to {output_dir}/schema.json
- Schema includes _schema_version linked to model definitions
- Schema correctly maps Python types to JSON Schema types
- Schema handles nested dataclasses, enums, optionals, and recursion
"""

import json
from pathlib import Path

import pytest

from pyegp_parser.schema_generator import _SCHEMA_VERSION, generate_schema


@pytest.fixture
def schema_output(tmp_path: Path) -> dict:
    """Generate the schema and return the parsed JSON."""
    generate_schema(tmp_path)
    schema_file = tmp_path / "schema.json"
    assert schema_file.exists()
    return json.loads(schema_file.read_text(encoding="utf-8"))


class TestSchemaFileOutput:
    """Tests for schema file writing behavior."""

    def test_writes_schema_json_to_output_dir(self, tmp_path: Path) -> None:
        """Schema file is created at {output_dir}/schema.json."""
        generate_schema(tmp_path)
        assert (tmp_path / "schema.json").exists()

    def test_creates_output_dir_if_missing(self, tmp_path: Path) -> None:
        """Output directory is created recursively if it doesn't exist."""
        nested = tmp_path / "a" / "b" / "c"
        generate_schema(nested)
        assert (nested / "schema.json").exists()

    def test_output_is_valid_json(self, tmp_path: Path) -> None:
        """The schema file contains valid JSON."""
        generate_schema(tmp_path)
        content = (tmp_path / "schema.json").read_text(encoding="utf-8")
        parsed = json.loads(content)
        assert isinstance(parsed, dict)

    def test_output_has_sorted_keys(self, tmp_path: Path) -> None:
        """JSON output uses sorted keys at all levels."""
        json_str = generate_schema(tmp_path)
        expected = json.dumps(json.loads(json_str), indent=2, sort_keys=True)
        assert json_str == expected

    def test_output_uses_two_space_indent(self, tmp_path: Path) -> None:
        """JSON output uses 2-space indentation."""
        json_str = generate_schema(tmp_path)
        lines = json_str.split("\n")
        # Find first indented line
        indented = [l for l in lines if l.startswith(" ") and l.strip()]
        assert any(l.startswith("  ") and not l.startswith("    ") for l in indented)


class TestSchemaStructure:
    """Tests for the overall schema document structure."""

    def test_has_json_schema_dialect(self, schema_output: dict) -> None:
        """Schema declares JSON Schema 2020-12 dialect."""
        assert (
            schema_output["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        )

    def test_root_ref_points_to_parsed_project(self, schema_output: dict) -> None:
        """Root $ref points to ParsedProject definition."""
        assert schema_output["$ref"] == "#/$defs/ParsedProject"

    def test_has_defs_section(self, schema_output: dict) -> None:
        """Schema has a $defs section with model definitions."""
        assert "$defs" in schema_output
        assert len(schema_output["$defs"]) > 0

    def test_includes_all_model_classes(self, schema_output: dict) -> None:
        """All expected model classes are present in $defs."""
        defs = schema_output["$defs"]
        expected_models = [
            "ParsedProject",
            "ElementMetadata",
            "DataItem",
            "DataModel",
            "ExternalFileItem",
            "CodeElement",
            "LogElement",
            "Connection",
            "DAGModel",
            "ProcessFlowContainer",
            "QueryModel",
            "InputTable",
            "ResultItem",
            "Calculation",
            "Expression",
            "FilterNode",
            "JoinItem",
            "OrderItem",
            "GroupItem",
            "QueryBuilderTablePosition",
            "ShortCutToData",
            "ShortCutToFile",
            "ImportTaskElement",
            "CodeTaskElement",
            "EGTaskElement",
            "ExportTaskElement",
            "AppendTaskElement",
            "SubmitableElement",
            "TaskGraphic",
            "ProcessFlowControlState",
            "TreeItem",
            "VisualLayout",
            "DNADescriptor",
            "ProjectMetadata",
            "ProjectSettings",
            "SourceInfo",
            "ProjectLogInfo",
            "CompletenessSummary",
        ]
        for model in expected_models:
            assert model in defs, f"Missing definition for {model}"


class TestSchemaVersion:
    """Tests for _schema_version handling (Req 15.14)."""

    def test_parsed_project_has_schema_version(self, schema_output: dict) -> None:
        """ParsedProject definition includes _schema_version property."""
        pp = schema_output["$defs"]["ParsedProject"]
        assert "_schema_version" in pp["properties"]

    def test_schema_version_is_const(self, schema_output: dict) -> None:
        """_schema_version is a const field with the current version."""
        pp = schema_output["$defs"]["ParsedProject"]
        sv = pp["properties"]["_schema_version"]
        assert sv["const"] == _SCHEMA_VERSION

    def test_schema_version_matches_model(self, schema_output: dict) -> None:
        """_schema_version in schema matches the ParsedProject default."""
        from pyegp_parser.models.project import ParsedProject

        project = ParsedProject()
        pp = schema_output["$defs"]["ParsedProject"]
        assert pp["properties"]["_schema_version"]["const"] == project.schema_version


class TestTypeDiscriminator:
    """Tests for _type discriminator fields."""

    def test_all_definitions_have_type_field(self, schema_output: dict) -> None:
        """Every definition includes a _type discriminator field."""
        for name, definition in schema_output["$defs"].items():
            assert "_type" in definition["properties"], f"{name} missing _type"

    def test_type_field_is_const(self, schema_output: dict) -> None:
        """The _type field is defined as a const matching the class name."""
        for name, definition in schema_output["$defs"].items():
            type_prop = definition["properties"]["_type"]
            assert type_prop["const"] == name


class TestTypeMapping:
    """Tests for Python-to-JSON-Schema type mapping."""

    def test_str_maps_to_string(self, schema_output: dict) -> None:
        """str fields become type: string."""
        source = schema_output["$defs"]["SourceInfo"]
        assert source["properties"]["file_path"]["type"] == "string"

    def test_int_maps_to_integer(self, schema_output: dict) -> None:
        """int fields become type: integer."""
        source = schema_output["$defs"]["SourceInfo"]
        assert source["properties"]["file_size_bytes"]["type"] == "integer"

    def test_bool_maps_to_boolean(self, schema_output: dict) -> None:
        """bool fields become type: boolean."""
        pp = schema_output["$defs"]["ParsedProject"]
        assert pp["properties"]["completeness_warning"]["type"] == "boolean"

    def test_optional_str_maps_to_anyof_with_null(self, schema_output: dict) -> None:
        """Optional[str] (str | None) becomes anyOf with string and null."""
        pm = schema_output["$defs"]["ProjectMetadata"]
        label_schema = pm["properties"]["label"]
        assert "anyOf" in label_schema
        types = [s.get("type") for s in label_schema["anyOf"]]
        assert "string" in types
        assert "null" in types

    def test_optional_bool_maps_to_anyof_with_null(self, schema_output: dict) -> None:
        """Optional[bool] (bool | None) becomes anyOf with boolean and null."""
        ps = schema_output["$defs"]["ProjectSettings"]
        prop = ps["properties"]["use_relative_paths"]
        assert "anyOf" in prop
        types = [s.get("type") for s in prop["anyOf"]]
        assert "boolean" in types
        assert "null" in types

    def test_optional_int_maps_to_anyof_with_null(self, schema_output: dict) -> None:
        """Optional[int] (int | None) becomes anyOf with integer and null."""
        ps = schema_output["$defs"]["ProjectSettings"]
        prop = ps["properties"]["project_log_max_size"]
        assert "anyOf" in prop
        types = [s.get("type") for s in prop["anyOf"]]
        assert "integer" in types
        assert "null" in types

    def test_list_of_str_maps_to_array_of_string(self, schema_output: dict) -> None:
        """list[str] becomes array with items: string."""
        em = schema_output["$defs"]["ElementMetadata"]
        input_ids = em["properties"]["input_ids"]
        assert input_ids["type"] == "array"
        assert input_ids["items"]["type"] == "string"

    def test_nested_dataclass_maps_to_ref(self, schema_output: dict) -> None:
        """Nested dataclass fields become $ref to $defs."""
        pp = schema_output["$defs"]["ParsedProject"]
        source = pp["properties"]["source"]
        assert "anyOf" in source
        refs = [s.get("$ref") for s in source["anyOf"] if "$ref" in s]
        assert "#/$defs/SourceInfo" in refs

    def test_recursive_dataclass_handled(self, schema_output: dict) -> None:
        """Recursive dataclass (DNADescriptor.parent_dna) is handled."""
        dna = schema_output["$defs"]["DNADescriptor"]
        parent = dna["properties"]["parent_dna"]
        assert "anyOf" in parent
        refs = [s.get("$ref") for s in parent["anyOf"] if "$ref" in s]
        assert "#/$defs/DNADescriptor" in refs

    def test_list_of_dataclass_maps_to_array_of_ref(self, schema_output: dict) -> None:
        """list[Connection] becomes array with items: $ref."""
        dag = schema_output["$defs"]["DAGModel"]
        conns = dag["properties"]["connections"]
        assert conns["type"] == "array"
        assert conns["items"]["$ref"] == "#/$defs/Connection"


class TestRequiredFields:
    """Tests for required field detection."""

    def test_fields_without_defaults_are_required(self, schema_output: dict) -> None:
        """Fields with no default value are listed as required."""
        conn = schema_output["$defs"]["Connection"]
        required = conn["required"]
        assert "source_id" in required
        assert "target_id" in required
        assert "resource_dependency" in required

    def test_fields_with_defaults_are_not_required(self, schema_output: dict) -> None:
        """Fields with default values are NOT listed as required."""
        pm = schema_output["$defs"]["ProjectMetadata"]
        required = pm.get("required", [])
        # All fields in ProjectMetadata have defaults (None)
        assert "label" not in required
        assert "eg_version" not in required
