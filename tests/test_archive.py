"""Tests for pyegp_parser.archive and pyegp_parser.classifier modules."""

import zipfile
from pathlib import Path

import pytest

from pyegp_parser.archive import (
    ArchiveEntry,
    ArchiveInventory,
    EntryCategory,
    open_archive,
)
from pyegp_parser.classifier import classify_entry

# ---------------------------------------------------------------------------
# classify_entry tests
# ---------------------------------------------------------------------------


class TestClassifyEntry:
    """Tests for the classify_entry function."""

    def test_project_xml(self):
        assert classify_entry("project.xml") == EntryCategory.PROJECT_XML

    def test_project_xml_in_subdir_is_unknown(self):
        assert classify_entry("sub/project.xml") == EntryCategory.UNKNOWN

    def test_task_config_import_task(self):
        assert (
            classify_entry("ImportTask-ABC123/ImportTask-ABC123.xml")
            == EntryCategory.TASK_CONFIG
        )

    def test_task_config_eg_task(self):
        assert (
            classify_entry("EGTask-xyz99/EGTask-xyz99.xml") == EntryCategory.TASK_CONFIG
        )

    def test_task_config_mismatched_type_is_unknown(self):
        # TaskType in folder doesn't match TaskType in filename
        assert (
            classify_entry("ImportTask-ABC123/EGTask-ABC123.xml")
            == EntryCategory.UNKNOWN
        )

    def test_task_config_mismatched_id_is_unknown(self):
        # ID in folder doesn't match ID in filename
        assert (
            classify_entry("ImportTask-ABC123/ImportTask-XYZ789.xml")
            == EntryCategory.UNKNOWN
        )

    def test_code_file(self):
        assert classify_entry("CodeTask-ABC123/code.sas") == EntryCategory.CODE_FILE

    def test_execution_log(self):
        assert (
            classify_entry("ImportTask-ABC123/Log-DEF456/result.log")
            == EntryCategory.EXECUTION_LOG
        )

    def test_execution_log_code_task(self):
        assert (
            classify_entry("CodeTask-A1/Log-B2/result.log")
            == EntryCategory.EXECUTION_LOG
        )

    def test_project_log(self):
        assert (
            classify_entry("ProjectLog-ABC123/ProjectLog-ABC123/result.log")
            == EntryCategory.PROJECT_LOG
        )

    def test_project_log_mismatched_id_is_unknown(self):
        assert (
            classify_entry("ProjectLog-ABC123/ProjectLog-XYZ789/result.log")
            == EntryCategory.UNKNOWN
        )

    def test_ods_result(self):
        assert (
            classify_entry("ODSResults/ODSResult-ABC123/result.pptx")
            == EntryCategory.ODS_RESULT
        )

    def test_ods_result_nested_file(self):
        assert (
            classify_entry("ODSResults/ODSResult-X1/subdir/file.html")
            == EntryCategory.ODS_RESULT
        )

    def test_empty_directory(self):
        assert classify_entry("somedir/") == EntryCategory.EMPTY_DIRECTORY

    def test_empty_directory_nested(self):
        assert classify_entry("a/b/c/") == EntryCategory.EMPTY_DIRECTORY

    def test_unknown_random_file(self):
        assert classify_entry("readme.txt") == EntryCategory.UNKNOWN

    def test_unknown_nested_file(self):
        assert classify_entry("data/output/results.csv") == EntryCategory.UNKNOWN


# ---------------------------------------------------------------------------
# open_archive tests
# ---------------------------------------------------------------------------


def _create_zip(tmp_path: Path, entries: dict[str, bytes | str]) -> Path:
    """Helper: create a ZIP file at tmp_path with the given entries."""
    zip_path = tmp_path / "test.egp"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for name, content in entries.items():
            if isinstance(content, str):
                content = content.encode("utf-8")
            zf.writestr(name, content)
    return zip_path


class TestOpenArchive:
    """Tests for the open_archive function."""

    def test_file_not_found(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError, match="not found"):
            open_archive(tmp_path / "nonexistent.egp")

    def test_invalid_zip(self, tmp_path: Path):
        bad_file = tmp_path / "not_a_zip.egp"
        bad_file.write_text("this is not a zip file")
        with pytest.raises(ValueError, match="invalid ZIP"):
            open_archive(bad_file)

    def test_missing_project_xml(self, tmp_path: Path):
        zip_path = _create_zip(tmp_path, {"readme.txt": "hello"})
        with pytest.raises(ValueError, match="missing project.xml"):
            open_archive(zip_path)

    def test_valid_archive_returns_inventory(self, tmp_path: Path):
        zip_path = _create_zip(
            tmp_path,
            {
                "project.xml": "<ProjectCollection/>",
                "CodeTask-A1/code.sas": "proc print; run;",
                "ImportTask-B2/ImportTask-B2.xml": "<config/>",
                "CodeTask-A1/Log-C3/result.log": "log content",
                "ProjectLog-D4/ProjectLog-D4/result.log": "project log",
                "ODSResults/ODSResult-E5/result.pptx": b"\x00\x01",
                "unknown_file.txt": "mystery",
            },
        )

        inventory = open_archive(zip_path)
        try:
            assert isinstance(inventory, ArchiveInventory)
            assert len(inventory.entries) == 7

            # Check categories
            categories = {e.path: e.category for e in inventory.entries}
            assert categories["project.xml"] == EntryCategory.PROJECT_XML
            assert categories["CodeTask-A1/code.sas"] == EntryCategory.CODE_FILE
            assert (
                categories["ImportTask-B2/ImportTask-B2.xml"]
                == EntryCategory.TASK_CONFIG
            )
            assert (
                categories["CodeTask-A1/Log-C3/result.log"]
                == EntryCategory.EXECUTION_LOG
            )
            assert (
                categories["ProjectLog-D4/ProjectLog-D4/result.log"]
                == EntryCategory.PROJECT_LOG
            )
            assert (
                categories["ODSResults/ODSResult-E5/result.pptx"]
                == EntryCategory.ODS_RESULT
            )
            assert categories["unknown_file.txt"] == EntryCategory.UNKNOWN
        finally:
            inventory.close()

    def test_get_content(self, tmp_path: Path):
        zip_path = _create_zip(
            tmp_path,
            {
                "project.xml": "<ProjectCollection/>",
                "CodeTask-A1/code.sas": "proc print; run;",
            },
        )
        inventory = open_archive(zip_path)
        try:
            content = inventory.get_content("CodeTask-A1/code.sas")
            assert content == "proc print; run;"
        finally:
            inventory.close()

    def test_get_bytes(self, tmp_path: Path):
        raw_bytes = b"\x00\x01\x02\x03"
        zip_path = _create_zip(
            tmp_path,
            {
                "project.xml": "<ProjectCollection/>",
                "binary.dat": raw_bytes,
            },
        )
        inventory = open_archive(zip_path)
        try:
            result = inventory.get_bytes("binary.dat")
            assert result == raw_bytes
        finally:
            inventory.close()

    def test_entries_have_sizes(self, tmp_path: Path):
        content = "Hello, world! " * 100
        zip_path = _create_zip(
            tmp_path,
            {
                "project.xml": "<ProjectCollection/>",
                "data.txt": content,
            },
        )
        inventory = open_archive(zip_path)
        try:
            data_entry = next(e for e in inventory.entries if e.path == "data.txt")
            assert data_entry.uncompressed_size == len(content.encode("utf-8"))
            # Compressed size should be smaller for repetitive content
            assert data_entry.compressed_size <= data_entry.uncompressed_size
        finally:
            inventory.close()

    def test_empty_directory_entries(self, tmp_path: Path):
        zip_path = tmp_path / "test.egp"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("project.xml", "<ProjectCollection/>")
            # Add a directory entry (ends with /)
            zf.writestr("emptydir/", "")

        inventory = open_archive(zip_path)
        try:
            dir_entry = next(e for e in inventory.entries if e.path == "emptydir/")
            assert dir_entry.category == EntryCategory.EMPTY_DIRECTORY
        finally:
            inventory.close()

    def test_archive_entry_is_frozen(self):
        entry = ArchiveEntry(
            path="test.xml",
            category=EntryCategory.UNKNOWN,
            compressed_size=100,
            uncompressed_size=200,
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            entry.path = "other.xml"  # type: ignore
