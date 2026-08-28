"""Tests for the completeness validator module."""

from unittest.mock import MagicMock

from pyegp_parser.archive import ArchiveEntry, ArchiveInventory, EntryCategory
from pyegp_parser.models.project import CompletenessSummary
from pyegp_parser.validator import validate_completeness


def _make_inventory(entries: list[ArchiveEntry]) -> ArchiveInventory:
    """Create a mock ArchiveInventory from a list of entries."""
    mock_zip = MagicMock()
    return ArchiveInventory(entries=entries, zip_file=mock_zip)


class TestValidateCompleteness:
    """Tests for validate_completeness function."""

    def test_all_entries_processed(self):
        """When all non-directory entries are processed, warning is False."""
        entries = [
            ArchiveEntry("project.xml", EntryCategory.PROJECT_XML, 100, 500),
            ArchiveEntry("CodeTask-1/code.sas", EntryCategory.CODE_FILE, 50, 200),
        ]
        inventory = _make_inventory(entries)
        processed = {"project.xml", "CodeTask-1/code.sas"}

        summary, unprocessed, warning = validate_completeness(inventory, processed)

        assert summary.total_entries == 2
        assert summary.processed_entries == 2
        assert summary.unprocessed_entries == 0
        assert unprocessed == []
        assert warning is False

    def test_unprocessed_entries_detected(self):
        """Entries not in processed_paths appear in unprocessed list."""
        entries = [
            ArchiveEntry("project.xml", EntryCategory.PROJECT_XML, 100, 500),
            ArchiveEntry("CodeTask-1/code.sas", EntryCategory.CODE_FILE, 50, 200),
            ArchiveEntry("unknown/file.dat", EntryCategory.UNKNOWN, 75, 300),
        ]
        inventory = _make_inventory(entries)
        processed = {"project.xml", "CodeTask-1/code.sas"}

        summary, unprocessed, warning = validate_completeness(inventory, processed)

        assert summary.total_entries == 3
        assert summary.processed_entries == 2
        assert summary.unprocessed_entries == 1
        assert len(unprocessed) == 1
        assert unprocessed[0].path == "unknown/file.dat"
        assert unprocessed[0].compressed_size == 75
        assert warning is True

    def test_empty_directories_auto_processed(self):
        """Empty directory entries are automatically considered processed."""
        entries = [
            ArchiveEntry("project.xml", EntryCategory.PROJECT_XML, 100, 500),
            ArchiveEntry("CodeTask-1/", EntryCategory.EMPTY_DIRECTORY, 0, 0),
            ArchiveEntry("SomeDir/", EntryCategory.EMPTY_DIRECTORY, 0, 0),
        ]
        inventory = _make_inventory(entries)
        processed = {"project.xml"}

        summary, unprocessed, warning = validate_completeness(inventory, processed)

        assert summary.total_entries == 3
        assert summary.processed_entries == 3
        assert summary.unprocessed_entries == 0
        assert unprocessed == []
        assert warning is False

    def test_empty_inventory(self):
        """An empty inventory produces zero counts and no warning."""
        inventory = _make_inventory([])
        processed: set[str] = set()

        summary, unprocessed, warning = validate_completeness(inventory, processed)

        assert summary.total_entries == 0
        assert summary.processed_entries == 0
        assert summary.unprocessed_entries == 0
        assert unprocessed == []
        assert warning is False

    def test_all_entries_unprocessed(self):
        """When nothing is processed, all non-directory entries are unprocessed."""
        entries = [
            ArchiveEntry("project.xml", EntryCategory.PROJECT_XML, 100, 500),
            ArchiveEntry("CodeTask-1/code.sas", EntryCategory.CODE_FILE, 50, 200),
        ]
        inventory = _make_inventory(entries)
        processed: set[str] = set()

        summary, unprocessed, warning = validate_completeness(inventory, processed)

        assert summary.total_entries == 2
        assert summary.processed_entries == 0
        assert summary.unprocessed_entries == 2
        assert len(unprocessed) == 2
        assert warning is True

    def test_mixed_entries_with_directories(self):
        """Mix of processed, unprocessed, and directory entries."""
        entries = [
            ArchiveEntry("project.xml", EntryCategory.PROJECT_XML, 100, 500),
            ArchiveEntry("CodeTask-1/", EntryCategory.EMPTY_DIRECTORY, 0, 0),
            ArchiveEntry("CodeTask-1/code.sas", EntryCategory.CODE_FILE, 50, 200),
            ArchiveEntry(
                "ImportTask-2/ImportTask-2.xml", EntryCategory.TASK_CONFIG, 80, 400
            ),
            ArchiveEntry(
                "ImportTask-2/Log-3/result.log", EntryCategory.EXECUTION_LOG, 30, 150
            ),
            ArchiveEntry(
                "ODSResults/ODSResult-4/result.pptx",
                EntryCategory.ODS_RESULT,
                200,
                1000,
            ),
        ]
        inventory = _make_inventory(entries)
        # Only some entries processed
        processed = {
            "project.xml",
            "CodeTask-1/code.sas",
            "ImportTask-2/ImportTask-2.xml",
        }

        summary, unprocessed, warning = validate_completeness(inventory, processed)

        assert summary.total_entries == 6
        # 3 processed + 1 empty directory = 4 processed
        assert summary.processed_entries == 4
        assert summary.unprocessed_entries == 2
        assert len(unprocessed) == 2
        unprocessed_paths = {e.path for e in unprocessed}
        assert "ImportTask-2/Log-3/result.log" in unprocessed_paths
        assert "ODSResults/ODSResult-4/result.pptx" in unprocessed_paths
        assert warning is True

    def test_returns_correct_types(self):
        """Verify the return types match the expected tuple signature."""
        entries = [
            ArchiveEntry("project.xml", EntryCategory.PROJECT_XML, 100, 500),
        ]
        inventory = _make_inventory(entries)
        processed = {"project.xml"}

        result = validate_completeness(inventory, processed)

        assert isinstance(result, tuple)
        assert len(result) == 3
        assert isinstance(result[0], CompletenessSummary)
        assert isinstance(result[1], list)
        assert isinstance(result[2], bool)

    def test_unprocessed_entries_preserve_order(self):
        """Unprocessed entries are reported in the same order as inventory."""
        entries = [
            ArchiveEntry("z_file.txt", EntryCategory.UNKNOWN, 10, 50),
            ArchiveEntry("a_file.txt", EntryCategory.UNKNOWN, 20, 100),
            ArchiveEntry("m_file.txt", EntryCategory.UNKNOWN, 30, 150),
        ]
        inventory = _make_inventory(entries)
        processed: set[str] = set()

        _, unprocessed, _ = validate_completeness(inventory, processed)

        assert [e.path for e in unprocessed] == [
            "z_file.txt",
            "a_file.txt",
            "m_file.txt",
        ]
