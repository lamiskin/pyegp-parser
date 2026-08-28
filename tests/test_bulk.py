"""Unit tests for the bulk directory processing module.

Tests cover:
- File discovery with recursive search and lexicographic sorting
- ValueError for invalid directory paths
- Independent parsing with success/failure recording
- Per-file JSON output with subdirectory structure preservation
- Empty directory handling

Requirements: 19.1, 19.2, 19.3, 19.4, 19.5, 19.6, 19.7
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from pyegp_parser.bulk import discover_egp_files, process_directory
from pyegp_parser.models.bulk import (
    BulkFileFailure,
    BulkFileSuccess,
    BulkResult,
    BulkSummary,
)


class TestDiscoverEgpFiles:
    """Tests for the discover_egp_files function."""

    def test_raises_valueerror_for_nonexistent_path(self, tmp_path: Path):
        """Requirement 19.2: ValueError for non-existent directory."""
        nonexistent = tmp_path / "does_not_exist"
        with pytest.raises(ValueError, match="does not exist"):
            discover_egp_files(nonexistent)

    def test_raises_valueerror_for_file_path(self, tmp_path: Path):
        """Requirement 19.2: ValueError when path is a file, not directory."""
        file_path = tmp_path / "some_file.txt"
        file_path.write_text("content")
        with pytest.raises(ValueError, match="is not a directory"):
            discover_egp_files(file_path)

    def test_discovers_egp_files_recursively(self, tmp_path: Path):
        """Requirement 19.1: Discover .egp files recursively."""
        # Create nested structure
        (tmp_path / "sub1").mkdir()
        (tmp_path / "sub1" / "sub2").mkdir()

        # Create .egp files at various levels
        (tmp_path / "root.egp").write_bytes(b"")
        (tmp_path / "sub1" / "nested.egp").write_bytes(b"")
        (tmp_path / "sub1" / "sub2" / "deep.egp").write_bytes(b"")

        # Create non-egp files that should be ignored
        (tmp_path / "readme.txt").write_text("not an egp")
        (tmp_path / "sub1" / "data.csv").write_text("data")

        result = discover_egp_files(tmp_path)
        assert len(result) == 3
        assert all(p.suffix == ".egp" for p in result)

    def test_sorted_lexicographically(self, tmp_path: Path):
        """Requirement 19.1: Results sorted lexicographically by full path."""
        (tmp_path / "b_dir").mkdir()
        (tmp_path / "a_dir").mkdir()

        (tmp_path / "b_dir" / "z_file.egp").write_bytes(b"")
        (tmp_path / "a_dir" / "a_file.egp").write_bytes(b"")
        (tmp_path / "b_dir" / "a_file.egp").write_bytes(b"")

        result = discover_egp_files(tmp_path)
        paths_as_strings = [str(p) for p in result]
        assert paths_as_strings == sorted(paths_as_strings)

    def test_empty_directory_returns_empty_list(self, tmp_path: Path):
        """Requirement 19.6: Empty directory yields empty list."""
        result = discover_egp_files(tmp_path)
        assert result == []


class TestProcessDirectory:
    """Tests for the process_directory function."""

    def test_raises_valueerror_for_invalid_directory(self, tmp_path: Path):
        """Requirement 19.2: ValueError for invalid directory."""
        nonexistent = tmp_path / "nope"
        with pytest.raises(ValueError, match="does not exist"):
            process_directory(nonexistent)

    def test_empty_directory_returns_empty_result(self, tmp_path: Path):
        """Requirement 19.6: No .egp files yields empty BulkResult."""
        result = process_directory(tmp_path)
        assert isinstance(result, BulkResult)
        assert result.successes == []
        assert result.failures == []
        assert result.summary.total_files == 0
        assert result.summary.success_count == 0
        assert result.summary.failure_count == 0

    def test_records_failures_and_continues(self, tmp_path: Path):
        """Requirement 19.4: Failed files are recorded; processing continues."""
        # Create invalid .egp files (not valid ZIPs)
        (tmp_path / "bad1.egp").write_text("not a zip")
        (tmp_path / "bad2.egp").write_text("also not a zip")

        result = process_directory(tmp_path)
        assert result.summary.total_files == 2
        assert result.summary.failure_count == 2
        assert result.summary.success_count == 0
        assert len(result.failures) == 2
        # Each failure should have the file path and an error message
        for failure in result.failures:
            assert failure.file_path
            assert failure.error_message

    def test_records_successes_with_valid_egp(self, tmp_path: Path):
        """Requirement 19.3: Successful parses are recorded with their project."""
        # Create a minimal valid .egp file (ZIP with project.xml)
        egp_path = tmp_path / "valid.egp"
        (egp_path).write_bytes(b"")  # placeholder

        mock_project = object()  # stand-in for a ParsedProject

        with patch("pyegp_parser.parse_file", return_value=mock_project):
            result = process_directory(tmp_path)

        assert result.summary.total_files == 1
        assert result.summary.success_count == 1
        assert result.summary.failure_count == 0
        assert len(result.successes) == 1
        assert result.successes[0].file_path == str(egp_path)
        assert result.successes[0].project is mock_project

    def test_mix_of_valid_and_invalid(self, tmp_path: Path):
        """Requirement 19.3, 19.4: Mix of valid and invalid files."""
        # Create two .egp files
        (tmp_path / "good.egp").write_bytes(b"")
        (tmp_path / "bad.egp").write_bytes(b"")

        call_count = [0]

        def mock_parse_file(egp_path, output_dir=None):
            call_count[0] += 1
            path_str = str(egp_path)
            if "bad" in path_str:
                raise ValueError("Not a valid EGP archive")
            return object()  # mock success

        with patch("pyegp_parser.parse_file", side_effect=mock_parse_file):
            result = process_directory(tmp_path)

        assert result.summary.total_files == 2
        assert result.summary.success_count == 1
        assert result.summary.failure_count == 1
        assert (
            result.summary.success_count + result.summary.failure_count
            == result.summary.total_files
        )

    def test_summary_counts_match(self, tmp_path: Path):
        """Requirement 19.5: Summary counts are correct."""
        # Create 3 invalid files
        for i in range(3):
            (tmp_path / f"file{i}.egp").write_text("bad")

        result = process_directory(tmp_path)
        assert result.summary.total_files == 3
        assert result.summary.success_count == len(result.successes)
        assert result.summary.failure_count == len(result.failures)
        assert (
            result.summary.success_count + result.summary.failure_count
            == result.summary.total_files
        )

    def test_output_preserves_subdirectory_structure(self, tmp_path: Path):
        """Requirement 19.7: Per-file output preserves subdirectory structure."""
        # Setup: directory with nested .egp file
        sub_dir = tmp_path / "input" / "subdir"
        sub_dir.mkdir(parents=True)
        output_dir = tmp_path / "output"

        egp_path = sub_dir / "project.egp"
        egp_path.write_bytes(b"")  # placeholder

        # Track what output_dir was passed to parse_file
        captured_output_dirs = []

        def mock_parse_file(path, output_dir=None):
            captured_output_dirs.append(output_dir)
            return object()

        with patch("pyegp_parser.parse_file", side_effect=mock_parse_file):
            result = process_directory(tmp_path / "input", output_dir=output_dir)

        assert result.summary.success_count == 1
        # Check that the output_dir passed to parse_file preserves subdir structure
        # Expected: {output_dir}/subdir/project
        expected_file_output = output_dir / "subdir" / "project"
        assert len(captured_output_dirs) == 1
        assert captured_output_dirs[0] == expected_file_output


class TestBulkModels:
    """Tests for the bulk model dataclasses."""

    def test_bulk_summary_defaults(self):
        """BulkSummary initializes with zero counts."""
        summary = BulkSummary()
        assert summary.total_files == 0
        assert summary.success_count == 0
        assert summary.failure_count == 0

    def test_bulk_result_defaults(self):
        """BulkResult initializes with empty lists and default summary."""
        result = BulkResult()
        assert result.successes == []
        assert result.failures == []
        assert result.summary.total_files == 0

    def test_bulk_file_success_fields(self):
        """BulkFileSuccess stores file path and project."""
        success = BulkFileSuccess(file_path="/path/to/file.egp", project={"test": True})
        assert success.file_path == "/path/to/file.egp"
        assert success.project == {"test": True}

    def test_bulk_file_failure_fields(self):
        """BulkFileFailure stores file path and error message."""
        failure = BulkFileFailure(
            file_path="/path/to/bad.egp",
            error_message="Not a valid ZIP archive",
        )
        assert failure.file_path == "/path/to/bad.egp"
        assert failure.error_message == "Not a valid ZIP archive"
