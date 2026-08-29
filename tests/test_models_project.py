"""Unit tests for pyegp_parser.models.project dataclasses."""

from dataclasses import fields

from pyegp_parser import __version__
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


class TestProjectMetadata:
    """Tests for ProjectMetadata dataclass."""

    def test_default_construction_all_none(self):
        """All fields should default to None when constructed without arguments."""
        meta = ProjectMetadata()
        assert meta.eg_version is None
        assert meta.type is None
        assert meta.label is None
        assert meta.id is None
        assert meta.created_on is None
        assert meta.modified_on is None
        assert meta.modified_by is None
        assert meta.modified_by_eg_id is None
        assert meta.modified_by_eg_ver is None

    def test_construction_with_all_fields(self):
        """All fields should be set when provided."""
        meta = ProjectMetadata(
            eg_version="8.1",
            type="SAS.EG.Project",
            label="My Project",
            id="abc-123",
            created_on="2024-01-01T00:00:00Z",
            modified_on="2024-06-15T12:30:00Z",
            modified_by="admin",
            modified_by_eg_id="EG001",
            modified_by_eg_ver="8.1.0",
        )
        assert meta.eg_version == "8.1"
        assert meta.type == "SAS.EG.Project"
        assert meta.label == "My Project"
        assert meta.id == "abc-123"
        assert meta.created_on == "2024-01-01T00:00:00Z"
        assert meta.modified_on == "2024-06-15T12:30:00Z"
        assert meta.modified_by == "admin"
        assert meta.modified_by_eg_id == "EG001"
        assert meta.modified_by_eg_ver == "8.1.0"

    def test_partial_construction(self):
        """Should allow partial field population with rest as None."""
        meta = ProjectMetadata(eg_version="8.1", label="Test")
        assert meta.eg_version == "8.1"
        assert meta.label == "Test"
        assert meta.type is None
        assert meta.id is None


class TestProjectSettings:
    """Tests for ProjectSettings dataclass."""

    def test_default_construction_all_none(self):
        """All fields should default to None when constructed without arguments."""
        settings = ProjectSettings()
        for f in fields(settings):
            assert getattr(settings, f.name) is None

    def test_construction_with_bool_fields(self):
        """Boolean fields should accept True/False values."""
        settings = ProjectSettings(
            use_relative_paths=True,
            submit_to_grid=False,
            queue_submits_for_server=True,
            clear_project_log_on_exit=False,
        )
        assert settings.use_relative_paths is True
        assert settings.submit_to_grid is False
        assert settings.queue_submits_for_server is True
        assert settings.clear_project_log_on_exit is False

    def test_construction_with_mixed_types(self):
        """Should handle string, int, and bool fields together."""
        settings = ProjectSettings(
            action_on_error="StopExecution",
            project_log_max_size=1000,
            project_log_export_filename="log.txt",
            project_log_export_location="/tmp/logs",
        )
        assert settings.action_on_error == "StopExecution"
        assert settings.project_log_max_size == 1000
        assert settings.project_log_export_filename == "log.txt"
        assert settings.project_log_export_location == "/tmp/logs"


class TestParameter:
    """Tests for Parameter dataclass."""

    def test_construction(self):
        """Parameter requires name and value."""
        param = Parameter(name="server", value="SASApp")
        assert param.name == "server"
        assert param.value == "SASApp"

    def test_empty_value(self):
        """Parameter value can be empty string."""
        param = Parameter(name="key", value="")
        assert param.value == ""


class TestProjectLogInfo:
    """Tests for ProjectLogInfo dataclass."""

    def test_default_construction_all_none(self):
        """All fields should default to None."""
        log = ProjectLogInfo()
        assert log.enabled is None
        assert log.written_to is None
        assert log.content is None

    def test_construction_with_content(self):
        """Should store log content as string."""
        log = ProjectLogInfo(enabled=True, written_to=True, content="Log output here")
        assert log.enabled is True
        assert log.written_to is True
        assert log.content == "Log output here"


class TestCompletenessSummary:
    """Tests for CompletenessSummary dataclass."""

    def test_default_construction_zeros(self):
        """All counts should default to 0."""
        summary = CompletenessSummary()
        assert summary.total_entries == 0
        assert summary.processed_entries == 0
        assert summary.unprocessed_entries == 0

    def test_construction_with_counts(self):
        """Should store entry counts."""
        summary = CompletenessSummary(
            total_entries=50,
            processed_entries=45,
            unprocessed_entries=5,
        )
        assert summary.total_entries == 50
        assert summary.processed_entries == 45
        assert summary.unprocessed_entries == 5


class TestUnprocessedEntry:
    """Tests for UnprocessedEntry dataclass."""

    def test_construction(self):
        """Should store path and compressed size."""
        entry = UnprocessedEntry(path="unknown/file.dat", compressed_size=1024)
        assert entry.path == "unknown/file.dat"
        assert entry.compressed_size == 1024


class TestBinaryEntry:
    """Tests for BinaryEntry dataclass."""

    def test_construction_without_task_id(self):
        """task_id should default to None."""
        entry = BinaryEntry(
            path="ODSResults/ODSResult-123/result.pptx",
            compressed_size=51200,
            file_extension=".pptx",
        )
        assert entry.path == "ODSResults/ODSResult-123/result.pptx"
        assert entry.compressed_size == 51200
        assert entry.file_extension == ".pptx"
        assert entry.task_id is None

    def test_construction_with_task_id(self):
        """Should store associated task_id when provided."""
        entry = BinaryEntry(
            path="ODSResults/ODSResult-456/result.xlsx",
            compressed_size=8192,
            file_extension=".xlsx",
            task_id="task-789",
        )
        assert entry.task_id == "task-789"


class TestSourceInfo:
    """Tests for SourceInfo dataclass."""

    def test_construction(self):
        """All fields are required and should be stored correctly."""
        source = SourceInfo(
            file_path="/home/user/projects/test.egp",
            file_name="test.egp",
            file_size_bytes=102400,
            parsed_at="2024-06-15T10:30:00Z",
            total_zip_entries=25,
        )
        assert source.file_path == "/home/user/projects/test.egp"
        assert source.file_name == "test.egp"
        assert source.file_size_bytes == 102400
        assert source.parsed_at == "2024-06-15T10:30:00Z"
        assert source.total_zip_entries == 25


class TestParsedProject:
    """Tests for ParsedProject root dataclass."""

    def test_default_construction(self):
        """Should construct with all defaults without error."""
        project = ParsedProject()
        assert project.schema_version == "1.0.0"
        assert project.parser_version == __version__
        assert project.source is None
        assert project.metadata is None
        assert project.settings is None
        assert project.data_list == []
        assert project.external_files == []
        assert project.elements == []
        assert project.containers == []
        assert project.parameters == []
        assert project.project_log is None
        assert project.visual_layout is None
        assert project.completeness_summary is None
        assert project.unprocessed_entries == []
        assert project.completeness_warning is False
        assert project.binary_entries == []
        assert project.application_overrides is None
        assert project.metadata_info is None
        assert project.open_project_view == []

    def test_construction_with_nested_models(self):
        """Should accept nested dataclass instances."""
        source = SourceInfo(
            file_path="/tmp/test.egp",
            file_name="test.egp",
            file_size_bytes=5000,
            parsed_at="2024-01-01T00:00:00Z",
            total_zip_entries=10,
        )
        metadata = ProjectMetadata(eg_version="8.1", label="Test Project")
        settings = ProjectSettings(submit_to_grid=True)
        log_info = ProjectLogInfo(enabled=True)
        completeness = CompletenessSummary(total_entries=10, processed_entries=10)

        project = ParsedProject(
            source=source,
            metadata=metadata,
            settings=settings,
            project_log=log_info,
            completeness_summary=completeness,
            parameters=[Parameter(name="p1", value="v1")],
        )
        assert project.source.file_name == "test.egp"
        assert project.metadata.eg_version == "8.1"
        assert project.settings.submit_to_grid is True
        assert project.project_log.enabled is True
        assert project.completeness_summary.total_entries == 10
        assert len(project.parameters) == 1
        assert project.parameters[0].name == "p1"

    def test_list_fields_are_independent_instances(self):
        """Each ParsedProject should have its own list instances (no shared state)."""
        p1 = ParsedProject()
        p2 = ParsedProject()
        p1.data_list.append("item")
        assert p2.data_list == []

    def test_schema_version_accessible_via_fields(self):
        """schema_version and parser_version should appear in dataclass fields."""
        project = ParsedProject()
        field_names = [f.name for f in fields(project)]
        assert "schema_version" in field_names
        assert "parser_version" in field_names
