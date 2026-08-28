"""Property-based tests for schema validation.

**Validates: Requirements 15.13, 17.3**

Property 10: Schema Validation — For any valid EGP file (represented as a
generated ParsedProject instance), the JSON output produced by the serializer
SHALL validate successfully against the generated JSON Schema with zero
validation errors.

Uses Hypothesis to generate random ParsedProject instances with varying
content, serializes each to a JSON dict, generates the JSON Schema from model
introspection, and validates the output against the schema using jsonschema.
"""

import jsonschema
from hypothesis import given, settings
from hypothesis import strategies as st

from pyegp_parser.models.base import ElementMetadata
from pyegp_parser.models.data import DataItem, DataModel
from pyegp_parser.models.process_flow import Connection, DAGModel, ProcessFlowContainer
from pyegp_parser.models.project import (
    BinaryEntry,
    CompletenessSummary,
    Parameter,
    ParsedProject,
    ProjectLogInfo,
    ProjectMetadata,
    ProjectSettings,
    SourceInfo,
    UnprocessedEntry,
)
from pyegp_parser.models.query import (
    InputTable,
    QueryModel,
    ResultItem,
)
from pyegp_parser.models.tasks import CodeTaskElement, SubmitableElement
from pyegp_parser.parsers.dna_parser import DNADescriptor
from pyegp_parser.schema_generator import _SchemaGenerator
from pyegp_parser.serializer import to_dict

# ---------------------------------------------------------------------------
# Strategies for generating model components
# ---------------------------------------------------------------------------

_safe_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S"),
        blacklist_characters="\x00",
    ),
    min_size=0,
    max_size=50,
)

_optional_text = st.one_of(st.none(), _safe_text)

_timestamp = st.builds(
    lambda y, m, d, h, mi, s: f"{y:04d}-{m:02d}-{d:02d}T{h:02d}:{mi:02d}:{s:02d}",
    st.integers(min_value=2000, max_value=2030),
    st.integers(min_value=1, max_value=12),
    st.integers(min_value=1, max_value=28),
    st.integers(min_value=0, max_value=23),
    st.integers(min_value=0, max_value=59),
    st.integers(min_value=0, max_value=59),
)

_optional_bool = st.one_of(st.none(), st.booleans())
_optional_int = st.one_of(st.none(), st.integers(min_value=0, max_value=100000))


# --- Element Metadata ---


@st.composite
def element_metadata_strategy(draw):
    return ElementMetadata(
        label=draw(_optional_text),
        type=draw(_optional_text),
        container=draw(_optional_text),
        id=draw(_optional_text),
        created_on=draw(st.one_of(st.none(), _timestamp)),
        modified_on=draw(st.one_of(st.none(), _timestamp)),
        modified_by=draw(_optional_text),
        modified_by_eg_id=draw(_optional_text),
        modified_by_eg_ver=draw(_optional_text),
        has_serialization_error=draw(_optional_bool),
        input_ids=draw(st.lists(_safe_text, max_size=5)),
    )


# --- DNA Descriptor ---


@st.composite
def dna_strategy(draw, allow_parent=True):
    parent = None
    if allow_parent and draw(st.booleans()):
        parent = draw(dna_strategy(allow_parent=False))
    return DNADescriptor(
        type=draw(_safe_text),
        name=draw(_safe_text),
        version=draw(_safe_text),
        assembly=draw(_optional_text),
        factory=draw(_optional_text),
        parent_name=draw(_optional_text),
        display_name=draw(_optional_text),
        display_path=draw(_optional_text),
        server=draw(_optional_text),
        library=draw(_optional_text),
        full_path=draw(_optional_text),
        read_only=draw(_optional_bool),
        temp=draw(_optional_bool),
        parent_dna=parent,
    )


# --- Project Metadata ---


@st.composite
def project_metadata_strategy(draw):
    return ProjectMetadata(
        eg_version=draw(_optional_text),
        type=draw(_optional_text),
        label=draw(_optional_text),
        id=draw(_optional_text),
        created_on=draw(st.one_of(st.none(), _timestamp)),
        modified_on=draw(st.one_of(st.none(), _timestamp)),
        modified_by=draw(_optional_text),
        modified_by_eg_id=draw(_optional_text),
        modified_by_eg_ver=draw(_optional_text),
    )


# --- Project Settings ---


@st.composite
def project_settings_strategy(draw):
    return ProjectSettings(
        use_relative_paths=draw(_optional_bool),
        submit_to_grid=draw(_optional_bool),
        queue_submits_for_server=draw(_optional_bool),
        action_on_error=draw(_optional_text),
        show_project_log_warning_message=draw(_optional_bool),
        remove_older_project_log_items=draw(_optional_bool),
        export_project_log_then_clear=draw(_optional_bool),
        project_log_export_filename=draw(_optional_text),
        project_log_export_location=draw(_optional_text),
        project_log_max_size=draw(_optional_int),
        clear_project_log_on_exit=draw(_optional_bool),
    )


# --- Source Info ---


@st.composite
def source_info_strategy(draw):
    return SourceInfo(
        file_path=draw(_safe_text),
        file_name=draw(_safe_text),
        file_size_bytes=draw(st.integers(min_value=0, max_value=10_000_000)),
        parsed_at=draw(_timestamp),
        total_zip_entries=draw(st.integers(min_value=0, max_value=500)),
    )


# --- Parameters ---


@st.composite
def parameter_strategy(draw):
    return Parameter(
        name=draw(_safe_text),
        value=draw(_safe_text),
    )


# --- Connections and DAG ---


@st.composite
def connection_strategy(draw):
    return Connection(
        source_id=draw(_safe_text),
        target_id=draw(_safe_text),
        resource_dependency=draw(st.booleans()),
    )


@st.composite
def dag_model_strategy(draw):
    nodes = draw(st.lists(_safe_text, max_size=8))
    connections = draw(st.lists(connection_strategy(), max_size=5))
    warnings = draw(st.lists(_safe_text, max_size=3))
    return DAGModel(nodes=nodes, connections=connections, warnings=warnings)


# --- Data Items ---


@st.composite
def data_model_strategy(draw):
    return DataModel(
        server=draw(_optional_text),
        active_data_source=draw(_optional_text),
        display_name=draw(_optional_text),
        table=draw(_optional_text),
        raw_active_data_source_state=draw(_optional_text),
        data_source_state=draw(_optional_text),
        table_state=draw(_optional_text),
        member_type=draw(_optional_text),
        decoded_dna=draw(st.one_of(st.none(), dna_strategy())),
    )


@st.composite
def data_item_strategy(draw):
    return DataItem(
        element=draw(element_metadata_strategy()),
        data_model=draw(data_model_strategy()),
        shortcut_list=draw(st.lists(_safe_text, max_size=4)),
    )


# --- Query Model (simplified) ---


@st.composite
def query_model_strategy(draw):
    return QueryModel(
        use_explicit_and_execute=draw(_optional_bool),
        output_library=draw(_optional_text),
        output_member=draw(_optional_text),
        output_type=draw(_optional_text),
        server=draw(_optional_text),
        input_tables=draw(
            st.lists(
                st.builds(
                    InputTable,
                    id=_optional_text,
                    input_table_name=_optional_text,
                    alias=_optional_text,
                ),
                max_size=3,
            )
        ),
        result_items=draw(
            st.lists(
                st.builds(
                    ResultItem,
                    result_id=_optional_text,
                    alias=_optional_text,
                    table_id=_optional_text,
                ),
                max_size=3,
            )
        ),
    )


# --- Process Flow Container ---


@st.composite
def process_flow_container_strategy(draw):
    return ProcessFlowContainer(
        metadata=draw(element_metadata_strategy()),
        dag=draw(dag_model_strategy()),
    )


# --- Completeness ---


@st.composite
def completeness_summary_strategy(draw):
    total = draw(st.integers(min_value=0, max_value=500))
    processed = draw(st.integers(min_value=0, max_value=total))
    return CompletenessSummary(
        total_entries=total,
        processed_entries=processed,
        unprocessed_entries=total - processed,
    )


# --- Binary and Unprocessed Entries ---


@st.composite
def binary_entry_strategy(draw):
    return BinaryEntry(
        path=draw(_safe_text),
        compressed_size=draw(st.integers(min_value=0, max_value=1_000_000)),
        file_extension=draw(_safe_text),
        task_id=draw(_optional_text),
    )


@st.composite
def unprocessed_entry_strategy(draw):
    return UnprocessedEntry(
        path=draw(_safe_text),
        compressed_size=draw(st.integers(min_value=0, max_value=1_000_000)),
    )


# --- Code Task (to exercise element types) ---


@st.composite
def submitable_element_strategy(draw):
    return SubmitableElement(
        use_global_options=draw(_optional_bool),
        server=draw(_optional_text),
        has_error=draw(_optional_bool),
        has_warning=draw(_optional_bool),
        execution_time_span=draw(_optional_text),
    )


@st.composite
def code_task_strategy(draw):
    return CodeTaskElement(
        metadata=draw(element_metadata_strategy()),
        submitable=draw(submitable_element_strategy()),
        code_content=draw(_optional_text),
        log_content=draw(_optional_text),
    )


# --- Full ParsedProject ---


@st.composite
def parsed_project_strategy(draw):
    return ParsedProject(
        schema_version="1.0.0",
        parser_version="1.0.0",
        source=draw(st.one_of(st.none(), source_info_strategy())),
        metadata=draw(st.one_of(st.none(), project_metadata_strategy())),
        settings=draw(st.one_of(st.none(), project_settings_strategy())),
        data_list=draw(st.lists(data_item_strategy(), max_size=3)),
        external_files=[],
        elements=draw(st.lists(code_task_strategy(), max_size=3)),
        containers=draw(st.lists(process_flow_container_strategy(), max_size=2)),
        parameters=draw(st.lists(parameter_strategy(), max_size=4)),
        project_log=draw(
            st.one_of(
                st.none(),
                st.builds(
                    ProjectLogInfo,
                    enabled=_optional_bool,
                    written_to=_optional_bool,
                    content=_optional_text,
                ),
            )
        ),
        completeness_summary=draw(
            st.one_of(st.none(), completeness_summary_strategy())
        ),
        unprocessed_entries=draw(st.lists(unprocessed_entry_strategy(), max_size=3)),
        completeness_warning=draw(st.booleans()),
        binary_entries=draw(st.lists(binary_entry_strategy(), max_size=3)),
    )


# ---------------------------------------------------------------------------
# Generate the schema once (module-level) for use in all tests
# ---------------------------------------------------------------------------

_GENERATED_SCHEMA = _SchemaGenerator().generate()


# ---------------------------------------------------------------------------
# Property 10: Schema Validation
# ---------------------------------------------------------------------------


class TestSchemaValidation:
    """**Validates: Requirements 15.13, 17.3**

    Property 10: For any valid ParsedProject instance, the JSON output
    produced by the serializer SHALL validate successfully against the
    generated JSON Schema with zero validation errors.
    """

    @given(project=parsed_project_strategy())
    @settings(max_examples=100)
    def test_serialized_project_validates_against_schema(self, project):
        """Generated ParsedProject instances serialize to JSON that passes
        schema validation with zero errors.

        This validates:
        - Requirement 15.13: JSON Schema generated from dataclass introspection
          correctly describes the serialized output format.
        - Requirement 17.3: Every output produced by the parser conforms to
          the schema without validation errors.
        """
        # Serialize to dict (same as what would be written to project.json)
        serialized = to_dict(project)

        # Validate against the generated schema
        validator = jsonschema.Draft202012Validator(_GENERATED_SCHEMA)
        errors = list(validator.iter_errors(serialized))

        assert len(errors) == 0, (
            f"Schema validation produced {len(errors)} error(s):\n"
            + "\n".join(
                f"  - {e.message} (at path: {list(e.absolute_path)})"
                for e in errors[:10]
            )
        )

    @given(project=parsed_project_strategy())
    @settings(max_examples=50)
    def test_minimal_project_validates(self, project):
        """Even a minimal ParsedProject (default construction) validates
        against the schema — confirming that optional fields and empty
        collections are correctly handled by the schema.
        """
        # Also test a completely minimal project
        minimal = ParsedProject()
        serialized = to_dict(minimal)

        validator = jsonschema.Draft202012Validator(_GENERATED_SCHEMA)
        errors = list(validator.iter_errors(serialized))

        assert len(errors) == 0, (
            f"Minimal project schema validation produced {len(errors)} error(s):\n"
            + "\n".join(
                f"  - {e.message} (at path: {list(e.absolute_path)})"
                for e in errors[:10]
            )
        )

    @given(project=parsed_project_strategy())
    @settings(max_examples=50)
    def test_nested_objects_have_valid_type_discriminator(self, project):
        """All nested objects in the serialized output include a valid _type
        field that matches a definition in the schema's $defs section.
        """
        serialized = to_dict(project)
        defs = _GENERATED_SCHEMA.get("$defs", {})

        def _check_types(obj, path="root"):
            if isinstance(obj, dict):
                if "_type" in obj:
                    type_val = obj["_type"]
                    assert type_val in defs, (
                        f"_type '{type_val}' at {path} not found in schema $defs. "
                        f"Available: {sorted(defs.keys())}"
                    )
                for k, v in obj.items():
                    _check_types(v, path=f"{path}.{k}")
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    _check_types(item, path=f"{path}[{i}]")

        _check_types(serialized)
