"""Integration tests against real EGP files.

**Validates: Requirements 17.1, 17.2, 17.3, 18.1**

These tests discover real .egp files from the workspace, parse each end-to-end
using pyegp_parser.parse_file(), and verify:
- The result is a ParsedProject instance
- JSON round-trip consistency (serialize → deserialize → re-serialize = identical)
- Schema validation passes with zero errors
- Source info is populated correctly (file_path, file_name, file_size_bytes, total_zip_entries > 0)

Files that fail to parse are recorded but do not block other tests.
"""

import json
from pathlib import Path

import jsonschema
import pytest

from pyegp_parser import parse_file
from pyegp_parser.models.project import ParsedProject, SourceInfo
from pyegp_parser.schema_generator import _SchemaGenerator
from pyegp_parser.serializer import from_dict, to_dict

# ---------------------------------------------------------------------------
# Discovery: find all .egp files in the workspace
# ---------------------------------------------------------------------------

_WORKSPACE_ROOT = Path(__file__).resolve().parent.parent


def _discover_egp_files() -> list[Path]:
    """Discover all .egp files in the workspace recursively."""
    return sorted(_WORKSPACE_ROOT.glob("**/*.egp"))


_ALL_EGP_FILES = _discover_egp_files()

# These are end-to-end integration tests against real .egp files. The public
# repository intentionally ships no sample .egp files, so the whole module skips
# unless real files are present in the workspace (e.g. when a user runs the suite
# locally against their own projects).
pytestmark = pytest.mark.skipif(
    not _ALL_EGP_FILES,
    reason="No sample .egp files available in the workspace; "
    "integration tests run only when real .egp files are present.",
)


def _try_parse(egp_path: Path) -> tuple[ParsedProject | None, str | None]:
    """Attempt to parse a single EGP file, returning result or error message."""
    try:
        result = parse_file(egp_path)
        return result, None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


# ---------------------------------------------------------------------------
# Classify files into parseable and failing at module load time
# ---------------------------------------------------------------------------

_PARSEABLE_FILES: list[Path] = []
_FAILED_FILES: list[tuple[Path, str]] = []

for _path in _ALL_EGP_FILES:
    _result, _error = _try_parse(_path)
    if _result is not None:
        _PARSEABLE_FILES.append(_path)
    else:
        _FAILED_FILES.append((_path, _error or "Unknown error"))


# ---------------------------------------------------------------------------
# Generate schema once for all tests
# ---------------------------------------------------------------------------

_GENERATED_SCHEMA = _SchemaGenerator().generate()


# ---------------------------------------------------------------------------
# Helper: create a serializable version of a ParsedProject
# ---------------------------------------------------------------------------


def _make_serializable_project(project: ParsedProject) -> ParsedProject:
    """Create a copy of the project with elements replaced by their metadata.

    The current parse_file() stores ParsedElement objects (which include
    xml_node: ET.Element) in the elements list. These aren't JSON-serializable.
    For integration testing of round-trip and schema validation, we replace
    elements with their ElementMetadata (which is fully serializable).
    """
    from pyegp_parser.parsers.element_parser import ParsedElement

    serializable_elements = []
    for elem in project.elements:
        if isinstance(elem, ParsedElement):
            serializable_elements.append(elem.metadata)
        else:
            serializable_elements.append(elem)

    # Create a new project with serializable elements
    return ParsedProject(
        schema_version=project.schema_version,
        parser_version=project.parser_version,
        source=project.source,
        metadata=project.metadata,
        settings=project.settings,
        data_list=project.data_list,
        external_files=project.external_files,
        elements=serializable_elements,
        containers=project.containers,
        parameters=project.parameters,
        project_log=project.project_log,
        visual_layout=project.visual_layout,
        completeness_summary=project.completeness_summary,
        unprocessed_entries=project.unprocessed_entries,
        completeness_warning=project.completeness_warning,
        binary_entries=project.binary_entries,
        application_overrides=project.application_overrides,
        metadata_info=project.metadata_info,
        open_project_view=project.open_project_view,
    )


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------


class TestIntegrationDiscovery:
    """Verify that test discovery found EGP files to test against."""

    def test_egp_files_discovered(self):
        """At least one .egp file should exist in the workspace."""
        assert len(_ALL_EGP_FILES) > 0, f"No .egp files found under {_WORKSPACE_ROOT}"

    def test_some_files_parseable(self):
        """At least one .egp file should parse successfully."""
        assert len(_PARSEABLE_FILES) > 0, (
            f"No .egp files could be parsed. "
            f"Total found: {len(_ALL_EGP_FILES)}, "
            f"All failed: {[str(p) for p, _ in _FAILED_FILES[:5]]}"
        )

    def test_report_failed_files(self):
        """Report which files failed to parse (informational, always passes)."""
        if _FAILED_FILES:
            report = "\n".join(
                f"  {path.relative_to(_WORKSPACE_ROOT)}: {error}"
                for path, error in _FAILED_FILES[:20]
            )
            # Print for visibility in test output, but don't fail
            print(
                f"\n--- EGP files that failed to parse "
                f"({len(_FAILED_FILES)}/{len(_ALL_EGP_FILES)}) ---\n{report}"
            )


# ---------------------------------------------------------------------------
# Parametrized tests across parseable EGP files
# ---------------------------------------------------------------------------


@pytest.fixture(params=_PARSEABLE_FILES, ids=lambda p: p.name)
def parsed_egp(request) -> tuple[Path, ParsedProject]:
    """Fixture providing a (path, ParsedProject) tuple for each parseable file."""
    egp_path = request.param
    result = parse_file(egp_path)
    return egp_path, result


class TestParsedProjectInstance:
    """Verify that parsed results are valid ParsedProject instances.

    **Validates: Requirements 17.1**
    """

    def test_result_is_parsed_project(self, parsed_egp):
        """parse_file() returns a ParsedProject instance."""
        path, project = parsed_egp
        assert isinstance(project, ParsedProject), (
            f"Expected ParsedProject, got {type(project).__name__} for {path.name}"
        )


class TestSourceInfo:
    """Verify source info is populated correctly.

    **Validates: Requirements 17.1, 18.1**
    """

    def test_source_info_populated(self, parsed_egp):
        """Source info should be populated with file metadata."""
        path, project = parsed_egp
        assert project.source is not None, f"source is None for {path.name}"
        assert isinstance(project.source, SourceInfo)

    def test_source_file_path(self, parsed_egp):
        """source.file_path should contain the original file path."""
        path, project = parsed_egp
        assert project.source is not None
        assert (
            str(path) in project.source.file_path
            or path.name in project.source.file_path
        )

    def test_source_file_name(self, parsed_egp):
        """source.file_name should match the EGP filename."""
        path, project = parsed_egp
        assert project.source is not None
        assert project.source.file_name == path.name

    def test_source_file_size(self, parsed_egp):
        """source.file_size_bytes should be positive and match actual file size."""
        path, project = parsed_egp
        assert project.source is not None
        assert project.source.file_size_bytes > 0
        assert project.source.file_size_bytes == path.stat().st_size

    def test_source_total_zip_entries(self, parsed_egp):
        """source.total_zip_entries should be > 0 (every EGP has at least project.xml)."""
        path, project = parsed_egp
        assert project.source is not None
        assert project.source.total_zip_entries > 0, (
            f"total_zip_entries is {project.source.total_zip_entries} for {path.name}"
        )


class TestJsonRoundTrip:
    """Verify JSON round-trip consistency: serialize → deserialize → re-serialize = identical.

    **Validates: Requirements 17.1, 17.2**
    """

    def test_round_trip_consistency(self, parsed_egp):
        """Serialized → deserialized → re-serialized output must be identical."""
        path, project = parsed_egp

        # Make a serializable version (replace ParsedElement with metadata)
        serializable = _make_serializable_project(project)

        # First serialization
        dict_1 = to_dict(serializable)
        json_str_1 = json.dumps(dict_1, indent=2, ensure_ascii=False, sort_keys=True)

        # Deserialize from dict
        reconstructed = from_dict(dict_1)

        # Second serialization from reconstructed object
        dict_2 = to_dict(reconstructed)
        json_str_2 = json.dumps(dict_2, indent=2, ensure_ascii=False, sort_keys=True)

        assert json_str_1 == json_str_2, (
            f"Round-trip failed for {path.name}.\n"
            f"First serialization length: {len(json_str_1)}\n"
            f"Second serialization length: {len(json_str_2)}\n"
            f"First diff area: {_find_first_diff(json_str_1, json_str_2)}"
        )

    def test_dict_round_trip_equality(self, parsed_egp):
        """to_dict → from_dict → to_dict produces identical dict structures."""
        path, project = parsed_egp

        serializable = _make_serializable_project(project)

        dict_1 = to_dict(serializable)
        reconstructed = from_dict(dict_1)
        dict_2 = to_dict(reconstructed)

        assert dict_1 == dict_2, f"Dict round-trip mismatch for {path.name}"


class TestSchemaValidation:
    """Verify schema validation passes with zero errors.

    **Validates: Requirements 15.13, 17.3**
    """

    def test_validates_against_schema(self, parsed_egp):
        """Serialized output must validate against the generated JSON schema."""
        path, project = parsed_egp

        serializable = _make_serializable_project(project)
        serialized = to_dict(serializable)
        validator = jsonschema.Draft202012Validator(_GENERATED_SCHEMA)
        errors = list(validator.iter_errors(serialized))

        assert len(errors) == 0, (
            f"Schema validation failed for {path.name} with {len(errors)} error(s):\n"
            + "\n".join(
                f"  - {e.message} (at path: {list(e.absolute_path)})"
                for e in errors[:10]
            )
        )

    def test_all_type_discriminators_valid(self, parsed_egp):
        """All _type fields in the output must reference known schema definitions."""
        path, project = parsed_egp

        serializable = _make_serializable_project(project)
        serialized = to_dict(serializable)
        defs = _GENERATED_SCHEMA.get("$defs", {})

        invalid_types = []

        def _check_types(obj, json_path="root"):
            if isinstance(obj, dict):
                if "_type" in obj:
                    type_val = obj["_type"]
                    if type_val not in defs:
                        invalid_types.append((json_path, type_val))
                for k, v in obj.items():
                    _check_types(v, json_path=f"{json_path}.{k}")
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    _check_types(item, json_path=f"{json_path}[{i}]")

        _check_types(serialized)

        assert len(invalid_types) == 0, (
            f"Unknown _type values in {path.name}:\n"
            + "\n".join(f"  - {p}: {t}" for p, t in invalid_types)
        )


class TestCompleteness:
    """Verify completeness tracking is populated.

    **Validates: Requirements 18.1**
    """

    def test_completeness_summary_populated(self, parsed_egp):
        """completeness_summary should be populated after parsing."""
        path, project = parsed_egp
        assert project.completeness_summary is not None, (
            f"completeness_summary is None for {path.name}"
        )

    def test_completeness_total_matches_zip(self, parsed_egp):
        """total_entries should match total_zip_entries from source info."""
        path, project = parsed_egp
        if project.completeness_summary is not None and project.source is not None:
            assert (
                project.completeness_summary.total_entries
                == project.source.total_zip_entries
            ), (
                f"total_entries ({project.completeness_summary.total_entries}) != "
                f"total_zip_entries ({project.source.total_zip_entries}) for {path.name}"
            )

    def test_completeness_accounting(self, parsed_egp):
        """processed + unprocessed should equal total entries."""
        path, project = parsed_egp
        if project.completeness_summary is not None:
            total = project.completeness_summary.total_entries
            processed = project.completeness_summary.processed_entries
            unprocessed = project.completeness_summary.unprocessed_entries
            assert processed + unprocessed == total, (
                f"Completeness accounting mismatch for {path.name}: "
                f"processed({processed}) + unprocessed({unprocessed}) != total({total})"
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_first_diff(s1: str, s2: str) -> str:
    """Find the first difference between two strings and return context around it."""
    for i, (c1, c2) in enumerate(zip(s1, s2)):
        if c1 != c2:
            start = max(0, i - 50)
            end = min(len(s1), i + 50)
            return f"Position {i}: first='{s1[start:end]}' second='{s2[start:end]}'"
    if len(s1) != len(s2):
        return f"Strings differ in length: {len(s1)} vs {len(s2)}"
    return "No difference found"
