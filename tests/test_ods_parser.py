"""Tests for ODS results and binary entry tracking.

Tests cover:
- Extracting ODS result entries from inventory
- Extracting unknown/unclassified entries
- Matching ODS results to tasks via JobRecipe ODSResultsList
- ValueError for corrupt/unreadable ZIP entry metadata
- No binary content extraction to disk
"""

from unittest.mock import MagicMock

import pytest

from pyegp_parser.archive import ArchiveEntry, ArchiveInventory, EntryCategory
from pyegp_parser.models.base import ElementMetadata
from pyegp_parser.models.project import BinaryEntry
from pyegp_parser.models.tasks import CodeTaskElement, SubmitableElement
from pyegp_parser.parsers.ods_parser import (
    extract_ods_results,
    extract_unknown_entries,
    match_ods_results_to_tasks,
)


def _make_inventory(entries: list[ArchiveEntry]) -> ArchiveInventory:
    """Create a mock ArchiveInventory with given entries."""
    mock_zip = MagicMock()
    return ArchiveInventory(entries=entries, zip_file=mock_zip)


class TestExtractODSResults:
    """Tests for extract_ods_results function."""

    def test_basic_ods_result(self):
        """ODS result entries are recorded with path, size, and extension."""
        entries = [
            ArchiveEntry(
                path="ODSResults/ODSResult-ABC123/result.pptx",
                category=EntryCategory.ODS_RESULT,
                compressed_size=1024,
                uncompressed_size=2048,
            ),
        ]
        inventory = _make_inventory(entries)

        results = extract_ods_results(inventory)

        assert len(results) == 1
        assert results[0].path == "ODSResults/ODSResult-ABC123/result.pptx"
        assert results[0].compressed_size == 1024
        assert results[0].file_extension == ".pptx"
        assert results[0].task_id is None

    def test_multiple_ods_results(self):
        """Multiple ODS result entries are all extracted."""
        entries = [
            ArchiveEntry(
                path="ODSResults/ODSResult-A1/result.pptx",
                category=EntryCategory.ODS_RESULT,
                compressed_size=100,
                uncompressed_size=200,
            ),
            ArchiveEntry(
                path="ODSResults/ODSResult-B2/output.html",
                category=EntryCategory.ODS_RESULT,
                compressed_size=300,
                uncompressed_size=600,
            ),
            ArchiveEntry(
                path="ODSResults/ODSResult-C3/report.pdf",
                category=EntryCategory.ODS_RESULT,
                compressed_size=500,
                uncompressed_size=1000,
            ),
        ]
        inventory = _make_inventory(entries)

        results = extract_ods_results(inventory)

        assert len(results) == 3
        assert results[0].file_extension == ".pptx"
        assert results[1].file_extension == ".html"
        assert results[2].file_extension == ".pdf"

    def test_ignores_non_ods_entries(self):
        """Only ODS_RESULT category entries are extracted."""
        entries = [
            ArchiveEntry(
                path="project.xml",
                category=EntryCategory.PROJECT_XML,
                compressed_size=500,
                uncompressed_size=1000,
            ),
            ArchiveEntry(
                path="ODSResults/ODSResult-X1/result.pptx",
                category=EntryCategory.ODS_RESULT,
                compressed_size=200,
                uncompressed_size=400,
            ),
            ArchiveEntry(
                path="unknown_file.txt",
                category=EntryCategory.UNKNOWN,
                compressed_size=50,
                uncompressed_size=100,
            ),
        ]
        inventory = _make_inventory(entries)

        results = extract_ods_results(inventory)

        assert len(results) == 1
        assert results[0].path == "ODSResults/ODSResult-X1/result.pptx"

    def test_empty_inventory(self):
        """Empty inventory returns empty list."""
        inventory = _make_inventory([])

        results = extract_ods_results(inventory)

        assert results == []

    def test_no_extension(self):
        """ODS result with no file extension gets empty string."""
        entries = [
            ArchiveEntry(
                path="ODSResults/ODSResult-X1/result",
                category=EntryCategory.ODS_RESULT,
                compressed_size=100,
                uncompressed_size=200,
            ),
        ]
        inventory = _make_inventory(entries)

        results = extract_ods_results(inventory)

        assert results[0].file_extension == ""

    def test_corrupt_entry_empty_path(self):
        """ValueError raised for entry with empty path."""
        entries = [
            ArchiveEntry(
                path="",
                category=EntryCategory.ODS_RESULT,
                compressed_size=100,
                uncompressed_size=200,
            ),
        ]
        inventory = _make_inventory(entries)

        with pytest.raises(ValueError, match="empty path"):
            extract_ods_results(inventory)

    def test_corrupt_entry_negative_size(self):
        """ValueError raised for entry with negative compressed size."""
        entries = [
            ArchiveEntry(
                path="ODSResults/ODSResult-X1/result.pptx",
                category=EntryCategory.ODS_RESULT,
                compressed_size=-1,
                uncompressed_size=200,
            ),
        ]
        inventory = _make_inventory(entries)

        with pytest.raises(ValueError, match="negative compressed size"):
            extract_ods_results(inventory)


class TestExtractUnknownEntries:
    """Tests for extract_unknown_entries function."""

    def test_basic_unknown_entry(self):
        """Unknown entries are recorded with path and size."""
        entries = [
            ArchiveEntry(
                path="some/random/file.dat",
                category=EntryCategory.UNKNOWN,
                compressed_size=256,
                uncompressed_size=512,
            ),
        ]
        inventory = _make_inventory(entries)

        results = extract_unknown_entries(inventory)

        assert len(results) == 1
        assert results[0].path == "some/random/file.dat"
        assert results[0].compressed_size == 256

    def test_ignores_classified_entries(self):
        """Only UNKNOWN category entries are extracted."""
        entries = [
            ArchiveEntry(
                path="project.xml",
                category=EntryCategory.PROJECT_XML,
                compressed_size=500,
                uncompressed_size=1000,
            ),
            ArchiveEntry(
                path="ODSResults/ODSResult-X1/result.pptx",
                category=EntryCategory.ODS_RESULT,
                compressed_size=200,
                uncompressed_size=400,
            ),
            ArchiveEntry(
                path="random.bin",
                category=EntryCategory.UNKNOWN,
                compressed_size=50,
                uncompressed_size=100,
            ),
        ]
        inventory = _make_inventory(entries)

        results = extract_unknown_entries(inventory)

        assert len(results) == 1
        assert results[0].path == "random.bin"

    def test_empty_inventory(self):
        """Empty inventory returns empty list."""
        inventory = _make_inventory([])

        results = extract_unknown_entries(inventory)

        assert results == []

    def test_multiple_unknown_entries(self):
        """Multiple unknown entries are all captured."""
        entries = [
            ArchiveEntry(
                path=".git/config",
                category=EntryCategory.UNKNOWN,
                compressed_size=30,
                uncompressed_size=60,
            ),
            ArchiveEntry(
                path="metadata.json",
                category=EntryCategory.UNKNOWN,
                compressed_size=100,
                uncompressed_size=200,
            ),
        ]
        inventory = _make_inventory(entries)

        results = extract_unknown_entries(inventory)

        assert len(results) == 2
        assert results[0].path == ".git/config"
        assert results[1].path == "metadata.json"


class TestMatchODSResultsToTasks:
    """Tests for match_ods_results_to_tasks function."""

    def test_match_via_job_recipe(self):
        """ODS result matched to task via JobRecipe ODSResultsList."""
        ods_entries = [
            BinaryEntry(
                path="ODSResults/ODSResult-R1/result.pptx",
                compressed_size=1024,
                file_extension=".pptx",
                task_id=None,
            ),
        ]
        # Create a task element with matching ODSResultsList
        task = CodeTaskElement(
            metadata=ElementMetadata(id="T1"),
            submitable=SubmitableElement(
                job_recipe={"ODSResultsList": [{"ID": "R1", "Type": "pptx"}]}
            ),
        )

        matched = match_ods_results_to_tasks(ods_entries, [task])

        assert len(matched) == 1
        assert matched[0].task_id == "T1"
        assert matched[0].path == "ODSResults/ODSResult-R1/result.pptx"

    def test_no_match_keeps_none(self):
        """ODS result without matching task retains task_id=None."""
        ods_entries = [
            BinaryEntry(
                path="ODSResults/ODSResult-UNMATCHED/result.pptx",
                compressed_size=1024,
                file_extension=".pptx",
                task_id=None,
            ),
        ]
        task = CodeTaskElement(
            metadata=ElementMetadata(id="T1"),
            submitable=SubmitableElement(
                job_recipe={"ODSResultsList": [{"ID": "OTHER", "Type": "pptx"}]}
            ),
        )

        matched = match_ods_results_to_tasks(ods_entries, [task])

        assert len(matched) == 1
        assert matched[0].task_id is None

    def test_multiple_tasks_multiple_results(self):
        """Multiple ODS results matched to different tasks."""
        ods_entries = [
            BinaryEntry(
                path="ODSResults/ODSResult-R1/result.pptx",
                compressed_size=100,
                file_extension=".pptx",
                task_id=None,
            ),
            BinaryEntry(
                path="ODSResults/ODSResult-R2/output.html",
                compressed_size=200,
                file_extension=".html",
                task_id=None,
            ),
        ]
        task1 = CodeTaskElement(
            metadata=ElementMetadata(id="T1"),
            submitable=SubmitableElement(
                job_recipe={"ODSResultsList": [{"ID": "R1", "Type": "pptx"}]}
            ),
        )
        task2 = CodeTaskElement(
            metadata=ElementMetadata(id="T2"),
            submitable=SubmitableElement(
                job_recipe={"ODSResultsList": [{"ID": "R2", "Type": "html"}]}
            ),
        )

        matched = match_ods_results_to_tasks(ods_entries, [task1, task2])

        assert matched[0].task_id == "T1"
        assert matched[1].task_id == "T2"

    def test_element_without_submitable(self):
        """Elements without submitable are safely skipped."""
        ods_entries = [
            BinaryEntry(
                path="ODSResults/ODSResult-R1/result.pptx",
                compressed_size=100,
                file_extension=".pptx",
                task_id=None,
            ),
        ]
        # An object without submitable attribute
        element = MagicMock(spec=[])

        matched = match_ods_results_to_tasks(ods_entries, [element])

        assert len(matched) == 1
        assert matched[0].task_id is None

    def test_element_with_none_job_recipe(self):
        """Elements with None job_recipe are safely skipped."""
        ods_entries = [
            BinaryEntry(
                path="ODSResults/ODSResult-R1/result.pptx",
                compressed_size=100,
                file_extension=".pptx",
                task_id=None,
            ),
        ]
        task = CodeTaskElement(
            metadata=ElementMetadata(id="T1"),
            submitable=SubmitableElement(job_recipe=None),
        )

        matched = match_ods_results_to_tasks(ods_entries, [task])

        assert len(matched) == 1
        assert matched[0].task_id is None

    def test_element_with_empty_ods_results_list(self):
        """Elements with empty ODSResultsList are safely handled."""
        ods_entries = [
            BinaryEntry(
                path="ODSResults/ODSResult-R1/result.pptx",
                compressed_size=100,
                file_extension=".pptx",
                task_id=None,
            ),
        ]
        task = CodeTaskElement(
            metadata=ElementMetadata(id="T1"),
            submitable=SubmitableElement(job_recipe={"ODSResultsList": []}),
        )

        matched = match_ods_results_to_tasks(ods_entries, [task])

        assert len(matched) == 1
        assert matched[0].task_id is None

    def test_does_not_extract_content(self):
        """Verify that no binary content is read from the archive.

        The match function only works with metadata already extracted
        from the inventory — it never calls get_bytes or get_content.
        """
        # This test verifies the design: match_ods_results_to_tasks
        # takes BinaryEntry objects (metadata only) and element objects,
        # never an ArchiveInventory — so no content extraction is possible.
        ods_entries = [
            BinaryEntry(
                path="ODSResults/ODSResult-R1/result.pptx",
                compressed_size=100,
                file_extension=".pptx",
                task_id=None,
            ),
        ]
        task = CodeTaskElement(
            metadata=ElementMetadata(id="T1"),
            submitable=SubmitableElement(
                job_recipe={"ODSResultsList": [{"ID": "R1", "Type": "pptx"}]}
            ),
        )

        # This succeeds without any archive access
        matched = match_ods_results_to_tasks(ods_entries, [task])
        assert matched[0].task_id == "T1"
