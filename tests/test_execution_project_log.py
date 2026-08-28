"""Tests for execution log and project log extraction.

Validates Requirements 12.1 through 12.5.
"""

import xml.etree.ElementTree as ET
from unittest.mock import MagicMock

import pytest

from pyegp_parser.archive import ArchiveEntry, ArchiveInventory, EntryCategory
from pyegp_parser.models.project import ProjectLogInfo
from pyegp_parser.parsers.log_code_parser import (
    extract_execution_logs,
    extract_project_log,
)


def _make_archive_entry(
    path: str,
    category: EntryCategory,
    compressed_size: int = 100,
    uncompressed_size: int = 200,
) -> ArchiveEntry:
    """Helper to create an ArchiveEntry."""
    return ArchiveEntry(
        path=path,
        category=category,
        compressed_size=compressed_size,
        uncompressed_size=uncompressed_size,
    )


def _make_inventory(
    entries: list[ArchiveEntry],
    file_contents: dict[str, str | bytes] | None = None,
) -> ArchiveInventory:
    """Create a mock ArchiveInventory with optional file content mapping."""
    mock_zip = MagicMock()
    inventory = ArchiveInventory(entries=entries, zip_file=mock_zip)

    if file_contents is not None:
        original_get_content = inventory.get_content

        def mock_get_content(path: str, encoding: str = "utf-8") -> str:
            if path in file_contents:
                content = file_contents[path]
                if isinstance(content, bytes):
                    return content.decode(encoding)
                return content
            raise KeyError(f"Entry not found: {path}")

        inventory.get_content = mock_get_content

    return inventory


class TestExtractExecutionLogs:
    """Tests for extract_execution_logs function (Requirements 12.1, 12.3, 12.4)."""

    def test_single_execution_log(self):
        """Requirement 12.1: Read log as UTF-8 string and associate by ID."""
        entries = [
            _make_archive_entry(
                "ImportTask-ABC/Log-DEF/result.log",
                EntryCategory.EXECUTION_LOG,
            ),
        ]
        file_contents = {
            "ImportTask-ABC/Log-DEF/result.log": "NOTE: Dataset created successfully.\n"
        }
        inventory = _make_inventory(entries, file_contents)

        result = extract_execution_logs(inventory)

        assert result == {"DEF": "NOTE: Dataset created successfully.\n"}

    def test_multiple_execution_logs(self):
        """Requirement 12.1: Multiple execution logs each associated by their log ID."""
        entries = [
            _make_archive_entry(
                "CodeTask-A1/Log-L1/result.log",
                EntryCategory.EXECUTION_LOG,
            ),
            _make_archive_entry(
                "ImportTask-B2/Log-L2/result.log",
                EntryCategory.EXECUTION_LOG,
            ),
            _make_archive_entry(
                "EGTask-C3/Log-L3/result.log",
                EntryCategory.EXECUTION_LOG,
            ),
        ]
        file_contents = {
            "CodeTask-A1/Log-L1/result.log": "Log content 1",
            "ImportTask-B2/Log-L2/result.log": "Log content 2",
            "EGTask-C3/Log-L3/result.log": "Log content 3",
        }
        inventory = _make_inventory(entries, file_contents)

        result = extract_execution_logs(inventory)

        assert result == {
            "L1": "Log content 1",
            "L2": "Log content 2",
            "L3": "Log content 3",
        }

    def test_no_execution_logs_returns_empty(self):
        """Requirement 12.3: When no log files exist, return empty dict."""
        entries = [
            _make_archive_entry("project.xml", EntryCategory.PROJECT_XML),
            _make_archive_entry("CodeTask-A1/code.sas", EntryCategory.CODE_FILE),
        ]
        inventory = _make_inventory(entries, {})

        result = extract_execution_logs(inventory)

        assert result == {}

    def test_utf8_decode_failure_raises_value_error(self):
        """Requirement 12.4: Raise ValueError if log cannot be decoded as UTF-8."""
        entries = [
            _make_archive_entry(
                "CodeTask-X1/Log-Y1/result.log",
                EntryCategory.EXECUTION_LOG,
            ),
        ]
        # Create an inventory where get_content raises UnicodeDecodeError
        inventory = _make_inventory(entries)
        inventory.get_content = MagicMock(
            side_effect=UnicodeDecodeError("utf-8", b"\xff\xfe", 0, 1, "invalid")
        )

        with pytest.raises(ValueError, match="cannot be decoded as UTF-8"):
            extract_execution_logs(inventory)

    def test_skips_non_execution_log_entries(self):
        """Only entries classified as EXECUTION_LOG are processed."""
        entries = [
            _make_archive_entry("project.xml", EntryCategory.PROJECT_XML),
            _make_archive_entry(
                "CodeTask-A1/Log-L1/result.log",
                EntryCategory.EXECUTION_LOG,
            ),
            _make_archive_entry(
                "ProjectLog-P1/ProjectLog-P1/result.log",
                EntryCategory.PROJECT_LOG,
            ),
        ]
        file_contents = {
            "CodeTask-A1/Log-L1/result.log": "execution log content",
        }
        inventory = _make_inventory(entries, file_contents)

        result = extract_execution_logs(inventory)

        assert result == {"L1": "execution log content"}

    def test_log_id_used_as_key_not_task_id(self):
        """Requirement 12.1: The log ID (from Log-{ID}) is used as the key."""
        entries = [
            _make_archive_entry(
                "ImportTask-TASK123/Log-ELEM456/result.log",
                EntryCategory.EXECUTION_LOG,
            ),
        ]
        file_contents = {
            "ImportTask-TASK123/Log-ELEM456/result.log": "some output",
        }
        inventory = _make_inventory(entries, file_contents)

        result = extract_execution_logs(inventory)

        # Key should be the log ID (ELEM456), not the task ID (TASK123)
        assert "ELEM456" in result
        assert "TASK123" not in result


class TestExtractProjectLog:
    """Tests for extract_project_log function (Requirements 12.2, 12.4, 12.5)."""

    def _make_project_xml_with_project_log(
        self,
        enabled: str = "true",
        written_to: str = "true",
    ) -> ET.Element:
        """Create a minimal project.xml root with a ProjectLog element."""
        xml = f"""
        <ProjectCollection>
            <Elements>
                <Element Type="SAS.EG.ProjectElements.ProjectLog" ID="PL001">
                    <Enabled>{enabled}</Enabled>
                    <WrittenTo>{written_to}</WrittenTo>
                </Element>
            </Elements>
        </ProjectCollection>
        """
        return ET.fromstring(xml)

    def _make_project_xml_with_project_log_section(
        self,
        enabled: str = "true",
        written_to: str = "false",
    ) -> ET.Element:
        """Create project.xml root with ProjectLog flags inside a ProjectLog sub-section."""
        xml = f"""
        <ProjectCollection>
            <Elements>
                <Element Type="SAS.EG.ProjectElements.ProjectLog" ID="PL002">
                    <ProjectLog>
                        <Enabled>{enabled}</Enabled>
                        <WrittenTo>{written_to}</WrittenTo>
                    </ProjectLog>
                </Element>
            </Elements>
        </ProjectCollection>
        """
        return ET.fromstring(xml)

    def test_project_log_with_content(self):
        """Requirement 12.2: Read project log content as UTF-8 string."""
        entries = [
            _make_archive_entry(
                "ProjectLog-PL001/ProjectLog-PL001/result.log",
                EntryCategory.PROJECT_LOG,
            ),
        ]
        file_contents = {
            "ProjectLog-PL001/ProjectLog-PL001/result.log": "Project log output here.",
        }
        inventory = _make_inventory(entries, file_contents)
        root = self._make_project_xml_with_project_log()

        result = extract_project_log(inventory, root)

        assert isinstance(result, ProjectLogInfo)
        assert result.content == "Project log output here."
        assert result.enabled is True
        assert result.written_to is True

    def test_project_log_no_log_file(self):
        """Requirement 12.3: When no project log file exists, content is None."""
        entries = [
            _make_archive_entry("project.xml", EntryCategory.PROJECT_XML),
        ]
        inventory = _make_inventory(entries, {})
        root = self._make_project_xml_with_project_log(
            enabled="true", written_to="false"
        )

        result = extract_project_log(inventory, root)

        assert result.content is None
        assert result.enabled is True
        assert result.written_to is False

    def test_project_log_utf8_decode_failure_raises_value_error(self):
        """Requirement 12.4: Raise ValueError if project log cannot be decoded as UTF-8."""
        entries = [
            _make_archive_entry(
                "ProjectLog-PL001/ProjectLog-PL001/result.log",
                EntryCategory.PROJECT_LOG,
            ),
        ]
        inventory = _make_inventory(entries)
        inventory.get_content = MagicMock(
            side_effect=UnicodeDecodeError("utf-8", b"\xff\xfe", 0, 1, "invalid")
        )
        root = self._make_project_xml_with_project_log()

        with pytest.raises(ValueError, match="cannot be decoded as UTF-8"):
            extract_project_log(inventory, root)

    def test_missing_project_log_element_raises_value_error(self):
        """Requirement 12.5: Raise ValueError if ProjectLog element absent."""
        entries = []
        inventory = _make_inventory(entries, {})
        # No ProjectLog element in the XML
        root = ET.fromstring("""
        <ProjectCollection>
            <Elements>
                <Element Type="SAS.EG.ProjectElements.Code" ID="C001">
                </Element>
            </Elements>
        </ProjectCollection>
        """)

        with pytest.raises(ValueError, match="ProjectLog element is absent"):
            extract_project_log(inventory, root)

    def test_missing_elements_section_raises_value_error(self):
        """Requirement 12.5: Raise ValueError if no Elements section in project.xml."""
        entries = []
        inventory = _make_inventory(entries, {})
        root = ET.fromstring("<ProjectCollection></ProjectCollection>")

        with pytest.raises(ValueError, match="ProjectLog element is absent"):
            extract_project_log(inventory, root)

    def test_project_log_metadata_from_sub_section(self):
        """Requirement 12.5: Extract metadata from ProjectLog sub-section."""
        entries = [
            _make_archive_entry(
                "ProjectLog-PL002/ProjectLog-PL002/result.log",
                EntryCategory.PROJECT_LOG,
            ),
        ]
        file_contents = {
            "ProjectLog-PL002/ProjectLog-PL002/result.log": "log data",
        }
        inventory = _make_inventory(entries, file_contents)
        root = self._make_project_xml_with_project_log_section(
            enabled="false", written_to="true"
        )

        result = extract_project_log(inventory, root)

        assert result.enabled is False
        assert result.written_to is True
        assert result.content == "log data"

    def test_project_log_enabled_false_written_to_false(self):
        """Both flags set to false."""
        entries = []
        inventory = _make_inventory(entries, {})
        root = self._make_project_xml_with_project_log(
            enabled="false", written_to="false"
        )

        result = extract_project_log(inventory, root)

        assert result.enabled is False
        assert result.written_to is False
        assert result.content is None
