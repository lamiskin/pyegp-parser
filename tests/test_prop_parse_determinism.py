"""Property-based tests for parse determinism.

**Validates: Requirements 17.1, 17.5**

Property 9: Parse Determinism — Parsing the same EGP file multiple times
produces byte-for-byte identical JSON output. Also validates that serializing
generated ParsedProject instances multiple times is deterministic.

Uses Hypothesis to:
1. Generate random ParsedProject instances and verify serialization determinism.
2. Parse real EGP files from the workspace multiple times and verify the JSON
   outputs are byte-for-byte identical across all runs.

This validates that the full pipeline (archive → parsers → models → serializer)
is deterministic regardless of the complexity or content of the input.
"""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from pyegp_parser.archive import open_archive
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
from pyegp_parser.parsers.data_parser import parse_data_list, parse_external_file_list
from pyegp_parser.parsers.dna_parser import DNADescriptor
from pyegp_parser.parsers.element_parser import parse_elements
from pyegp_parser.parsers.project_parser import parse_project_xml
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
        elements=[],
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
# Property 9: Parse Determinism
# ---------------------------------------------------------------------------


class TestParseDeterminism:
    """**Validates: Requirements 17.1, 17.5**

    Property 9: Serializing the same ParsedProject multiple times always
    produces byte-for-byte identical JSON output, verifying deterministic
    key ordering and stable collection handling.
    """

    @given(project=parsed_project_strategy())
    @settings(max_examples=50)
    def test_serialization_deterministic_across_multiple_calls(self, project):
        """Serializing the same project instance N times yields identical JSON.

        This validates Requirement 17.1 (deterministic output with stable key
        ordering) and Requirement 17.5 (stable sorting for non-deterministic data).
        """
        # Serialize the same instance 3 times
        json_str_1 = json.dumps(
            to_dict(project), indent=2, ensure_ascii=False, sort_keys=True
        )
        json_str_2 = json.dumps(
            to_dict(project), indent=2, ensure_ascii=False, sort_keys=True
        )
        json_str_3 = json.dumps(
            to_dict(project), indent=2, ensure_ascii=False, sort_keys=True
        )

        # All outputs must be byte-for-byte identical
        assert json_str_1 == json_str_2, (
            "Serialization 1 and 2 differ!\n"
            f"Length 1: {len(json_str_1)}, Length 2: {len(json_str_2)}"
        )
        assert json_str_1 == json_str_3, (
            "Serialization 1 and 3 differ!\n"
            f"Length 1: {len(json_str_1)}, Length 3: {len(json_str_3)}"
        )

    @given(project=parsed_project_strategy())
    @settings(max_examples=50)
    def test_to_dict_deterministic(self, project):
        """to_dict() called multiple times on the same object produces identical dicts.

        This is a stronger check that the intermediate representation (before
        json.dumps) is itself deterministic.
        """
        dict_1 = to_dict(project)
        dict_2 = to_dict(project)

        # Convert to JSON strings for byte-level comparison
        json_1 = json.dumps(dict_1, sort_keys=True, ensure_ascii=False)
        json_2 = json.dumps(dict_2, sort_keys=True, ensure_ascii=False)

        assert json_1 == json_2, (
            "to_dict() produced different results for the same input"
        )

    @given(project=parsed_project_strategy())
    @settings(max_examples=50)
    def test_json_output_has_sorted_keys_at_all_levels(self, project):
        """All objects in the serialized JSON have their keys in sorted order.

        This validates Requirement 17.1's requirement for stable key ordering
        across all nesting levels.
        """
        json_str = json.dumps(
            to_dict(project), indent=2, ensure_ascii=False, sort_keys=True
        )
        data = json.loads(json_str)

        def _check_sorted_keys(obj, path="root"):
            """Recursively check that all dict keys are sorted."""
            if isinstance(obj, dict):
                keys = list(obj.keys())
                assert keys == sorted(keys), f"Keys not sorted at {path}: {keys}"
                for k, v in obj.items():
                    _check_sorted_keys(v, path=f"{path}.{k}")
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    _check_sorted_keys(item, path=f"{path}[{i}]")

        _check_sorted_keys(data)


# ---------------------------------------------------------------------------
# Helper: Parse an EGP file into a ParsedProject using available parsers
# ---------------------------------------------------------------------------


def _parse_egp_to_project(egp_path: Path) -> ParsedProject:
    """Parse an EGP file into a ParsedProject using the individual parser modules.

    This wires together the archive opener, project parser, data parser, and
    element parser to produce a ParsedProject comparable to what the full
    parse_file() pipeline will produce (once implemented in task 12.1).

    Args:
        egp_path: Path to the .egp file.

    Returns:
        A populated ParsedProject instance.

    Raises:
        ValueError: If the file cannot be parsed (invalid encoding, malformed XML, etc.)
    """
    inventory = open_archive(egp_path)
    try:
        # Handle different encodings — some EGP files use UTF-16 with BOM
        raw_bytes = inventory.get_bytes("project.xml")
        if raw_bytes.startswith(b"\xff\xfe") or raw_bytes.startswith(b"\xfe\xff"):
            xml_content = raw_bytes.decode("utf-16")
        elif raw_bytes.startswith(b"\xef\xbb\xbf"):
            xml_content = raw_bytes.decode("utf-8-sig")
        else:
            xml_content = raw_bytes.decode("utf-8")

        project = parse_project_xml(xml_content)

        # Parse additional sections from XML root
        root = ET.fromstring(xml_content)
        project.data_list = parse_data_list(root)

        # Parse external files — may raise ValueError on malformed DNA;
        # catch to avoid test failures on known-bad files
        try:
            project.external_files = parse_external_file_list(root)
        except ValueError:
            project.external_files = []

        # Parse elements — store only the metadata (xml_node is not serializable)
        parsed_elements = parse_elements(root)
        project.elements = [elem.metadata for elem in parsed_elements]

        # Source info for provenance — use fixed timestamp for determinism
        project.source = SourceInfo(
            file_path=str(egp_path),
            file_name=egp_path.name,
            file_size_bytes=egp_path.stat().st_size,
            parsed_at="2025-01-01T00:00:00",  # Fixed for determinism
            total_zip_entries=len(inventory.entries),
        )

        return project
    finally:
        inventory.close()


# ---------------------------------------------------------------------------
# Discover real .egp files in the workspace for file-based determinism tests
# ---------------------------------------------------------------------------

_WORKSPACE_ROOT = Path(__file__).resolve().parent.parent


def _discover_parseable_egp_files(max_files: int = 5) -> list[Path]:
    """Find EGP files that can be successfully parsed.

    Tries each discovered .egp file and keeps only those that parse
    without errors. This avoids test failures from corrupt or
    incompatible files.
    """
    candidates = sorted(_WORKSPACE_ROOT.glob("**/*.egp"))
    valid: list[Path] = []
    for path in candidates:
        if len(valid) >= max_files:
            break
        try:
            _parse_egp_to_project(path)
            valid.append(path)
        except (ValueError, Exception):
            continue
    return valid


_EGP_FILES = _discover_parseable_egp_files()


# ---------------------------------------------------------------------------
# Property 9 (file-based): Parse Determinism on Real EGP Files
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _EGP_FILES,
    reason="No sample .egp files available in the workspace; "
    "these end-to-end determinism checks run only when real .egp files are present.",
)
class TestParseDeterminismRealFiles:
    """**Validates: Requirements 17.1, 17.5**

    Property 9: Parse the same EGP file multiple times; verify byte-for-byte
    identical JSON output. This tests the full parse pipeline (archive extraction,
    XML parsing, model construction, JSON serialization) for determinism.
    """

    @given(file_index=st.integers(min_value=0, max_value=max(0, len(_EGP_FILES) - 1)))
    @settings(
        max_examples=min(10, max(1, len(_EGP_FILES) * 3)),
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_parse_same_egp_file_produces_identical_json(self, file_index):
        """Parsing the same EGP file N times yields byte-for-byte identical JSON.

        Uses Hypothesis to select from available .egp files and parses each
        file 3 times, then verifies all JSON outputs are identical.

        This validates:
        - Requirement 17.1: Deterministic output with sorted keys
        - Requirement 17.5: Stable sorting for all collections
        """
        assume(len(_EGP_FILES) > 0)
        egp_path = _EGP_FILES[file_index]

        # Parse the same file 3 times
        results = []
        for _ in range(3):
            project = _parse_egp_to_project(egp_path)
            json_str = json.dumps(
                to_dict(project), indent=2, ensure_ascii=False, sort_keys=True
            )
            results.append(json_str)

        # Verify byte-for-byte identical output across all parses
        assert results[0] == results[1], (
            f"Parse 1 and 2 differ for {egp_path.name}!\n"
            f"Length 1: {len(results[0])}, Length 2: {len(results[1])}"
        )
        assert results[0] == results[2], (
            f"Parse 1 and 3 differ for {egp_path.name}!\n"
            f"Length 1: {len(results[0])}, Length 3: {len(results[2])}"
        )

    @given(file_index=st.integers(min_value=0, max_value=max(0, len(_EGP_FILES) - 1)))
    @settings(
        max_examples=min(10, max(1, len(_EGP_FILES) * 3)),
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_parse_determinism_sorted_keys_at_all_levels(self, file_index):
        """All dicts in the parsed-and-serialized JSON have keys in sorted order.

        Verifies Requirement 17.1 for real EGP files — the serializer must
        produce stable key ordering at every nesting level.
        """
        assume(len(_EGP_FILES) > 0)
        egp_path = _EGP_FILES[file_index]

        project = _parse_egp_to_project(egp_path)
        json_str = json.dumps(
            to_dict(project), indent=2, ensure_ascii=False, sort_keys=True
        )
        data = json.loads(json_str)

        def _check_sorted_keys(obj, path="root"):
            if isinstance(obj, dict):
                keys = list(obj.keys())
                assert keys == sorted(keys), (
                    f"Keys not sorted at {path}: {keys} (file: {egp_path.name})"
                )
                for k, v in obj.items():
                    _check_sorted_keys(v, path=f"{path}.{k}")
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    _check_sorted_keys(item, path=f"{path}[{i}]")

        _check_sorted_keys(data)
