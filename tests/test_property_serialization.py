"""Property-based tests for JSON serialization round-trip.

**Validates: Requirements 15.15, 17.2**

Uses Hypothesis to generate random but valid ParsedProject instances,
serialize them to JSON via to_dict() + json.dumps(), deserialize back
via from_dict(), re-serialize, and verify byte-for-byte identical output.

This guarantees round-trip consistency: the serialization format is
deterministic and lossless for all valid model structures.
"""

import json

from hypothesis import given, settings
from hypothesis import strategies as st

from pyegp_parser.models.base import ElementMetadata
from pyegp_parser.models.data import DataItem, DataModel
from pyegp_parser.models.external_file import ExternalFileItem
from pyegp_parser.models.log_code import CodeElement, LogElement
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
from pyegp_parser.models.shortcut import ShortCutToData, ShortCutToFile
from pyegp_parser.models.tasks import (
    CodeTaskElement,
    SubmitableElement,
)
from pyegp_parser.models.visual_layout import (
    ProcessFlowControlState,
    TaskGraphic,
    TreeItem,
    VisualLayout,
)
from pyegp_parser.parsers.dna_parser import DNADescriptor
from pyegp_parser.serializer import from_dict, to_dict

# ---------------------------------------------------------------------------
# Hypothesis strategies for generating model instances
# ---------------------------------------------------------------------------

# Safe text that won't cause issues in JSON serialization
_safe_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S", "Z"),
        blacklist_characters="\x00",
    ),
    min_size=0,
    max_size=30,
)

_nonempty_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "Pd", "Pc"),
        blacklist_characters="\x00",
    ),
    min_size=1,
    max_size=20,
)

_optional_text = st.one_of(st.none(), _safe_text)
_optional_bool = st.one_of(st.none(), st.booleans())
_optional_int = st.one_of(st.none(), st.integers(min_value=0, max_value=10000))
_id_text = _nonempty_text  # Used for IDs


@st.composite
def element_metadata_strategy(draw) -> ElementMetadata:
    """Generate a random ElementMetadata instance."""
    return ElementMetadata(
        label=draw(_optional_text),
        type=draw(_optional_text),
        container=draw(_optional_text),
        id=draw(_optional_text),
        created_on=draw(_optional_text),
        modified_on=draw(_optional_text),
        modified_by=draw(_optional_text),
        modified_by_eg_id=draw(_optional_text),
        modified_by_eg_ver=draw(_optional_text),
        has_serialization_error=draw(_optional_bool),
        input_ids=draw(st.lists(_nonempty_text, max_size=3)),
    )


@st.composite
def dna_descriptor_strategy(draw, max_depth: int = 1) -> DNADescriptor:
    """Generate a random DNADescriptor with limited nesting."""
    parent_dna = None
    if max_depth > 0 and draw(st.booleans()):
        parent_dna = draw(dna_descriptor_strategy(max_depth=0))

    return DNADescriptor(
        type=draw(_nonempty_text),
        name=draw(_nonempty_text),
        version=draw(_nonempty_text),
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
        parent_dna=parent_dna,
    )


@st.composite
def project_metadata_strategy(draw) -> ProjectMetadata:
    """Generate a random ProjectMetadata instance."""
    return ProjectMetadata(
        eg_version=draw(_optional_text),
        type=draw(_optional_text),
        label=draw(_optional_text),
        id=draw(_optional_text),
        created_on=draw(_optional_text),
        modified_on=draw(_optional_text),
        modified_by=draw(_optional_text),
        modified_by_eg_id=draw(_optional_text),
        modified_by_eg_ver=draw(_optional_text),
    )


@st.composite
def project_settings_strategy(draw) -> ProjectSettings:
    """Generate a random ProjectSettings instance."""
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


@st.composite
def source_info_strategy(draw) -> SourceInfo:
    """Generate a random SourceInfo instance."""
    return SourceInfo(
        file_path=draw(_nonempty_text),
        file_name=draw(_nonempty_text),
        file_size_bytes=draw(st.integers(min_value=0, max_value=100_000_000)),
        parsed_at=draw(_nonempty_text),
        total_zip_entries=draw(st.integers(min_value=0, max_value=1000)),
    )


@st.composite
def parameter_strategy(draw) -> Parameter:
    """Generate a random Parameter instance."""
    return Parameter(
        name=draw(_nonempty_text),
        value=draw(_safe_text),
    )


@st.composite
def project_log_info_strategy(draw) -> ProjectLogInfo:
    """Generate a random ProjectLogInfo instance."""
    return ProjectLogInfo(
        enabled=draw(_optional_bool),
        written_to=draw(_optional_bool),
        content=draw(_optional_text),
    )


@st.composite
def completeness_summary_strategy(draw) -> CompletenessSummary:
    """Generate a random CompletenessSummary instance."""
    total = draw(st.integers(min_value=0, max_value=500))
    processed = draw(st.integers(min_value=0, max_value=total))
    return CompletenessSummary(
        total_entries=total,
        processed_entries=processed,
        unprocessed_entries=total - processed,
    )


@st.composite
def unprocessed_entry_strategy(draw) -> UnprocessedEntry:
    """Generate a random UnprocessedEntry instance."""
    return UnprocessedEntry(
        path=draw(_nonempty_text),
        compressed_size=draw(st.integers(min_value=0, max_value=100_000)),
    )


@st.composite
def binary_entry_strategy(draw) -> BinaryEntry:
    """Generate a random BinaryEntry instance."""
    return BinaryEntry(
        path=draw(_nonempty_text),
        compressed_size=draw(st.integers(min_value=0, max_value=100_000)),
        file_extension=draw(_nonempty_text),
        task_id=draw(_optional_text),
    )


@st.composite
def data_model_strategy(draw) -> DataModel:
    """Generate a random DataModel instance."""
    return DataModel(
        server=draw(_optional_text),
        active_data_source=draw(_optional_text),
        display_name=draw(_optional_text),
        table=draw(_optional_text),
        raw_active_data_source_state=draw(_optional_text),
        data_source_state=draw(_optional_text),
        table_state=draw(_optional_text),
        member_type=draw(_optional_text),
        decoded_dna=draw(st.one_of(st.none(), dna_descriptor_strategy())),
    )


@st.composite
def data_item_strategy(draw) -> DataItem:
    """Generate a random DataItem instance."""
    return DataItem(
        element=draw(st.one_of(st.none(), element_metadata_strategy())),
        data_model=draw(st.one_of(st.none(), data_model_strategy())),
        shortcut_list=draw(st.lists(_nonempty_text, max_size=3)),
    )


@st.composite
def external_file_item_strategy(draw) -> ExternalFileItem:
    """Generate a random ExternalFileItem instance."""
    return ExternalFileItem(
        element=draw(st.one_of(st.none(), element_metadata_strategy())),
        shortcut_list=draw(st.lists(_nonempty_text, max_size=3)),
        file_type_type=draw(_optional_text),
        raw_dna=draw(_optional_text),
        decoded_dna=draw(st.one_of(st.none(), dna_descriptor_strategy())),
    )


@st.composite
def connection_strategy(draw) -> Connection:
    """Generate a random Connection instance."""
    return Connection(
        source_id=draw(_nonempty_text),
        target_id=draw(_nonempty_text),
        resource_dependency=draw(st.booleans()),
    )


@st.composite
def dag_model_strategy(draw) -> DAGModel:
    """Generate a random DAGModel instance."""
    return DAGModel(
        nodes=draw(st.lists(_nonempty_text, max_size=5)),
        connections=draw(st.lists(connection_strategy(), max_size=3)),
        warnings=draw(st.lists(_safe_text, max_size=2)),
    )


@st.composite
def process_flow_container_strategy(draw) -> ProcessFlowContainer:
    """Generate a random ProcessFlowContainer instance."""
    return ProcessFlowContainer(
        metadata=draw(st.one_of(st.none(), element_metadata_strategy())),
        dag=draw(st.one_of(st.none(), dag_model_strategy())),
    )


@st.composite
def log_element_strategy(draw) -> LogElement:
    """Generate a random LogElement instance."""
    return LogElement(
        metadata=draw(st.one_of(st.none(), element_metadata_strategy())),
        parent_id=draw(_optional_text),
        line_size=draw(_optional_int),
        page_size=draw(_optional_int),
        portrait=draw(_optional_bool),
        condition_parent=draw(_optional_text),
    )


@st.composite
def code_element_strategy(draw) -> CodeElement:
    """Generate a random CodeElement instance."""
    return CodeElement(
        metadata=draw(st.one_of(st.none(), element_metadata_strategy())),
        text=draw(_optional_text),
        read_only=draw(_optional_bool),
        def_ext=draw(_optional_text),
        parent_id=draw(_optional_text),
        libref_code=draw(_optional_text),
        begin_app_code=draw(_optional_text),
        begin_user_code=draw(_optional_text),
        task_code=draw(_optional_text),
        end_user_code=draw(_optional_text),
        end_app_code=draw(_optional_text),
        libref_cl_code=draw(_optional_text),
        macro_assign_code=draw(_optional_text),
        macro_unassign_code=draw(_optional_text),
    )


@st.composite
def submitable_element_strategy(draw) -> SubmitableElement:
    """Generate a random SubmitableElement instance."""
    return SubmitableElement(
        use_global_options=draw(_optional_bool),
        server=draw(_optional_text),
        has_error=draw(_optional_bool),
        has_warning=draw(_optional_bool),
        ods_style_overrides=None,  # dict fields are complex; keep None for simplicity
        expected_output_data_list=draw(st.lists(_nonempty_text, max_size=2)),
        parameters=draw(st.lists(_nonempty_text, max_size=2)),
        execution_time_span=draw(_optional_text),
        job_recipe=None,
    )


@st.composite
def code_task_element_strategy(draw) -> CodeTaskElement:
    """Generate a random CodeTaskElement instance."""
    return CodeTaskElement(
        metadata=draw(st.one_of(st.none(), element_metadata_strategy())),
        submitable=draw(st.one_of(st.none(), submitable_element_strategy())),
        code_content=draw(_optional_text),
        log_content=draw(_optional_text),
    )


@st.composite
def shortcut_to_data_strategy(draw) -> ShortCutToData:
    """Generate a random ShortCutToData instance."""
    return ShortCutToData(
        metadata=draw(st.one_of(st.none(), element_metadata_strategy())),
        parent_id=draw(_optional_text),
        input_list=draw(st.lists(_nonempty_text, max_size=3)),
        user_has_explicitly_set_label=draw(_optional_bool),
    )


@st.composite
def shortcut_to_file_strategy(draw) -> ShortCutToFile:
    """Generate a random ShortCutToFile instance."""
    return ShortCutToFile(
        metadata=draw(st.one_of(st.none(), element_metadata_strategy())),
        parent_id=draw(_optional_text),
        input_list=draw(st.lists(_nonempty_text, max_size=3)),
        user_has_explicitly_set_label=draw(_optional_bool),
    )


@st.composite
def task_graphic_strategy(draw) -> TaskGraphic:
    """Generate a random TaskGraphic instance."""
    return TaskGraphic(
        type=draw(_optional_text),
        id=draw(_optional_text),
        line_width=draw(_optional_text),
        fill=draw(_optional_text),
        pos_x=draw(_optional_text),
        pos_y=draw(_optional_text),
        width=draw(_optional_text),
        height=draw(_optional_text),
        rotation=draw(_optional_text),
        visible=draw(_optional_text),
        border=draw(_optional_text),
        auto_size=draw(_optional_text),
        removable=draw(_optional_text),
        child=draw(_optional_text),
        selected=draw(_optional_text),
        label=draw(_optional_text),
        element=draw(_optional_text),
    )


@st.composite
def process_flow_control_state_strategy(draw) -> ProcessFlowControlState:
    """Generate a random ProcessFlowControlState instance."""
    return ProcessFlowControlState(
        container_id=draw(_optional_text),
        zoom=draw(_optional_text),
        show_grid=draw(_optional_text),
        show_margins=draw(_optional_text),
        align=draw(_optional_text),
        task_graphics=draw(st.lists(task_graphic_strategy(), max_size=3)),
    )


@st.composite
def tree_item_strategy(draw) -> TreeItem:
    """Generate a random TreeItem instance."""
    return TreeItem(
        id=draw(_optional_text),
        is_expanded=draw(_optional_bool),
    )


@st.composite
def visual_layout_strategy(draw) -> VisualLayout:
    """Generate a random VisualLayout instance."""
    return VisualLayout(
        process_flow_states=draw(
            st.lists(process_flow_control_state_strategy(), max_size=2)
        ),
        warnings=draw(st.lists(_safe_text, max_size=2)),
    )


# Strategy for mixed element types (elements list can contain various types)
_element_strategy = st.one_of(
    code_task_element_strategy(),
    log_element_strategy(),
    code_element_strategy(),
    shortcut_to_data_strategy(),
    shortcut_to_file_strategy(),
)


@st.composite
def parsed_project_strategy(draw) -> ParsedProject:
    """Generate a random but valid ParsedProject instance.

    Generates all sub-fields using appropriate strategies to create
    realistic but randomized project structures for round-trip testing.
    """
    return ParsedProject(
        schema_version=draw(_nonempty_text),
        parser_version=draw(_nonempty_text),
        source=draw(st.one_of(st.none(), source_info_strategy())),
        metadata=draw(st.one_of(st.none(), project_metadata_strategy())),
        settings=draw(st.one_of(st.none(), project_settings_strategy())),
        data_list=draw(st.lists(data_item_strategy(), max_size=3)),
        external_files=draw(st.lists(external_file_item_strategy(), max_size=2)),
        elements=draw(st.lists(_element_strategy, max_size=4)),
        containers=draw(st.lists(process_flow_container_strategy(), max_size=2)),
        parameters=draw(st.lists(parameter_strategy(), max_size=3)),
        project_log=draw(st.one_of(st.none(), project_log_info_strategy())),
        visual_layout=draw(st.one_of(st.none(), visual_layout_strategy())),
        completeness_summary=draw(
            st.one_of(st.none(), completeness_summary_strategy())
        ),
        unprocessed_entries=draw(st.lists(unprocessed_entry_strategy(), max_size=2)),
        completeness_warning=draw(st.booleans()),
        binary_entries=draw(st.lists(binary_entry_strategy(), max_size=2)),
        application_overrides=None,
        metadata_info=None,
        open_project_view=draw(st.lists(tree_item_strategy(), max_size=3)),
    )


# ---------------------------------------------------------------------------
# Property 8: JSON Serialization Round-Trip
# ---------------------------------------------------------------------------


class TestJSONSerializationRoundTrip:
    """**Validates: Requirements 15.15, 17.2**"""

    @given(project=parsed_project_strategy())
    @settings(max_examples=200)
    def test_serialize_deserialize_reserialize_identical(self, project: ParsedProject):
        """Generate a random ParsedProject, serialize to JSON, deserialize
        back, re-serialize, and verify the two JSON outputs are byte-for-byte
        identical.

        This validates that:
        - to_dict() produces deterministic output with sorted keys
        - from_dict() correctly reconstructs all types via _type dispatch
        - The round-trip is lossless for all model field types
        - Re-serialization produces identical bytes (determinism guarantee)
        """
        # First serialization
        dict1 = to_dict(project)
        json1 = json.dumps(dict1, indent=2, ensure_ascii=False, sort_keys=True)

        # Deserialize back
        reconstructed = from_dict(dict1)

        # Second serialization
        dict2 = to_dict(reconstructed)
        json2 = json.dumps(dict2, indent=2, ensure_ascii=False, sort_keys=True)

        # Byte-for-byte identical
        assert json1 == json2, (
            f"Round-trip produced different JSON output.\n"
            f"First serialization length: {len(json1)}\n"
            f"Second serialization length: {len(json2)}\n"
            f"First 500 chars diff area: "
            f"{_find_diff_context(json1, json2)}"
        )

    @given(project=parsed_project_strategy())
    @settings(max_examples=200)
    def test_dict_round_trip_structural_equality(self, project: ParsedProject):
        """Verify that to_dict() → from_dict() → to_dict() produces
        structurally equal dicts.

        This is a complementary check ensuring the dict representation
        itself is stable, not just the JSON string.
        """
        dict1 = to_dict(project)
        reconstructed = from_dict(dict1)
        dict2 = to_dict(reconstructed)

        assert dict1 == dict2, (
            f"Dict round-trip produced different structure.\n"
            f"Original _type: {dict1.get('_type')}\n"
            f"Reconstructed _type: {dict2.get('_type')}"
        )

    @given(project=parsed_project_strategy())
    @settings(max_examples=100)
    def test_json_output_is_valid_json(self, project: ParsedProject):
        """Verify that serialized output is always valid JSON that
        can be parsed back without errors."""
        dict_repr = to_dict(project)
        json_str = json.dumps(dict_repr, indent=2, ensure_ascii=False, sort_keys=True)

        # Must parse without error
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)
        assert parsed.get("_type") == "ParsedProject"


def _find_diff_context(s1: str, s2: str) -> str:
    """Find the first point of difference and return surrounding context."""
    for i, (c1, c2) in enumerate(zip(s1, s2)):
        if c1 != c2:
            start = max(0, i - 50)
            end = min(len(s1), i + 50)
            return f"Position {i}: '{s1[start:end]}' vs '{s2[start:end]}'"
    if len(s1) != len(s2):
        return f"Lengths differ: {len(s1)} vs {len(s2)}"
    return "No difference found"
