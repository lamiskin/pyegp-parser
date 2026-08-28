"""Tests for task parsers (CodeTask, EGTask, ExportTask, AppendTask).

Tests cover parsing of SubmitableElement extraction, task-specific section
parsing, archive-based file reading, and graceful handling of missing files.
"""

import xml.etree.ElementTree as ET
from unittest.mock import MagicMock

import pytest

from pyegp_parser.models.base import ElementMetadata
from pyegp_parser.models.tasks import (
    AppendTaskElement,
    CodeTaskElement,
    EGTaskElement,
    ExportTaskElement,
    ImportTaskElement,
)
from pyegp_parser.parsers.task_parser import (
    parse_append_task,
    parse_code_task,
    parse_eg_task,
    parse_export_task,
    parse_import_task,
)

# --- Fixtures ---


def _make_metadata(
    element_id: str = "test-001", label: str = "Test"
) -> ElementMetadata:
    """Helper to create test ElementMetadata."""
    return ElementMetadata(
        label=label,
        type="SAS.EG.ProjectElements.CodeTask",
        id=element_id,
    )


def _make_archive_mock(files: dict[str, str] | None = None):
    """Create a mock archive that returns content for given paths.

    Args:
        files: Dict mapping archive paths to their string content.
              If a path is requested that isn't in the dict, raises KeyError.
    """
    if files is None:
        files = {}

    mock = MagicMock()

    def get_content_side_effect(path, encoding="utf-8"):
        if path in files:
            return files[path]
        raise KeyError(f"Entry not found: {path}")

    mock.get_content.side_effect = get_content_side_effect
    return mock


# --- CodeTask Tests ---


class TestParseCodeTask:
    """Tests for parse_code_task function."""

    def test_basic_code_task_with_archive(self):
        """CodeTask reads code from archive at CodeTask-{ID}/code.sas."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.CodeTask" Label="My Code" ID="ct-001">
            <SubmitableElement>
                <Server>SASApp</Server>
                <HASERROR>False</HASERROR>
            </SubmitableElement>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = _make_metadata("ct-001", "My Code")
        archive = _make_archive_mock(
            {"CodeTask-ct-001/code.sas": "proc print data=work.test; run;"}
        )

        result = parse_code_task(node, metadata, archive=archive)

        assert isinstance(result, CodeTaskElement)
        assert result.metadata == metadata
        assert result.submitable is not None
        assert result.submitable.server == "SASApp"
        assert result.submitable.has_error is False
        assert result.code_content == "proc print data=work.test; run;"

    def test_code_task_missing_code_file(self):
        """CodeTask sets code to None with warning if file missing."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.CodeTask" Label="Missing Code" ID="ct-002">
            <SubmitableElement>
                <Server>SASApp</Server>
            </SubmitableElement>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = _make_metadata("ct-002", "Missing Code")
        archive = _make_archive_mock({})  # empty archive

        result = parse_code_task(node, metadata, archive=archive)

        assert result.code_content is None

    def test_code_task_no_archive(self):
        """CodeTask with no archive returns None for code."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.CodeTask" Label="No Archive" ID="ct-003">
            <SubmitableElement>
                <Server>SASApp</Server>
            </SubmitableElement>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = _make_metadata("ct-003", "No Archive")

        result = parse_code_task(node, metadata, archive=None)

        assert result.code_content is None
        assert result.submitable is not None
        assert result.submitable.server == "SASApp"

    def test_code_task_no_submitable_element(self):
        """CodeTask with missing SubmitableElement returns default."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.CodeTask" Label="Bare" ID="ct-004">
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = _make_metadata("ct-004", "Bare")

        result = parse_code_task(node, metadata, archive=None)

        assert result.submitable is not None
        assert result.submitable.server is None

    def test_code_task_missing_file_logs_warning(self, caplog):
        """CodeTask logs a warning when code file is missing from archive (Req 10.2)."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.CodeTask" Label="Missing" ID="ct-005">
            <SubmitableElement>
                <Server>SASApp</Server>
            </SubmitableElement>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = _make_metadata("ct-005", "Missing")
        archive = _make_archive_mock({})

        import logging

        with caplog.at_level(logging.WARNING):
            result = parse_code_task(node, metadata, archive=archive)

        assert result.code_content is None
        assert "CodeTask-ct-005/code.sas" in caplog.text

    def test_code_task_multiline_code(self):
        """CodeTask reads multiline SAS code correctly."""
        code = "proc sql;\n  select * from work.test;\nquit;\n"
        xml = """
        <Element Type="SAS.EG.ProjectElements.CodeTask" Label="Multi" ID="ct-006">
            <SubmitableElement>
                <Server>SASApp</Server>
            </SubmitableElement>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = _make_metadata("ct-006", "Multi")
        archive = _make_archive_mock(
            {
                "CodeTask-ct-006/code.sas": code,
            }
        )

        result = parse_code_task(node, metadata, archive=archive)

        assert result.code_content == code


# --- EGTask Tests ---


class TestParseEGTask:
    """Tests for parse_eg_task function."""

    def test_basic_eg_task_with_config(self):
        """EGTask extracts EGTask section and reads task config from archive."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.EGTask" Label="Summary Stats" ID="eg-001">
            <SubmitableElement>
                <Server>SASApp</Server>
                <HASERROR>False</HASERROR>
            </SubmitableElement>
            <EGTask>
                <Task_CLSID>{ABC-123-DEF}</Task_CLSID>
                <GeneratesCodeFlag>True</GeneratesCodeFlag>
            </EGTask>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = _make_metadata("eg-001", "Summary Stats")
        config_xml = "<TaskConfig><Setting>Value</Setting></TaskConfig>"
        archive = _make_archive_mock(
            {
                "EGTask-eg-001/EGTask-eg-001.xml": config_xml,
            }
        )

        result = parse_eg_task(node, metadata, archive=archive)

        assert isinstance(result, EGTaskElement)
        assert result.metadata == metadata
        assert result.submitable.server == "SASApp"
        assert result.eg_task_clsid == "{ABC-123-DEF}"
        assert result.generates_code_flag is True
        assert result.task_config is not None
        assert result.task_config["Setting"] == {"#text": "Value"}

    def test_eg_task_missing_config_file(self):
        """EGTask sets task_config to None if config file is missing."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.EGTask" Label="No Config" ID="eg-002">
            <SubmitableElement>
                <Server>SASApp</Server>
            </SubmitableElement>
            <EGTask>
                <Task_CLSID>{XYZ-789}</Task_CLSID>
                <GeneratesCodeFlag>False</GeneratesCodeFlag>
            </EGTask>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = _make_metadata("eg-002", "No Config")
        archive = _make_archive_mock({})

        result = parse_eg_task(node, metadata, archive=archive)

        assert result.task_config is None
        assert result.eg_task_clsid == "{XYZ-789}"
        assert result.generates_code_flag is False

    def test_eg_task_malformed_config_raises_error(self):
        """EGTask raises ValueError if config XML is malformed."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.EGTask" Label="Bad Config" ID="eg-003">
            <SubmitableElement>
                <Server>SASApp</Server>
            </SubmitableElement>
            <EGTask>
                <Task_CLSID>{BAD-001}</Task_CLSID>
                <GeneratesCodeFlag>True</GeneratesCodeFlag>
            </EGTask>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = _make_metadata("eg-003", "Bad Config")
        archive = _make_archive_mock(
            {
                "EGTask-eg-003/EGTask-eg-003.xml": "<broken><xml",
            }
        )

        with pytest.raises(ValueError, match="malformed"):
            parse_eg_task(node, metadata, archive=archive)

    def test_eg_task_no_eg_task_section(self):
        """EGTask with missing EGTask section still parses (fields are None)."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.EGTask" Label="Bare EG" ID="eg-004">
            <SubmitableElement>
                <Server>SASApp</Server>
            </SubmitableElement>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = _make_metadata("eg-004", "Bare EG")

        result = parse_eg_task(node, metadata, archive=None)

        assert result.eg_task_clsid is None
        assert result.generates_code_flag is None
        assert result.task_config is None

    def test_eg_task_no_archive(self):
        """EGTask with no archive leaves task_config as None."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.EGTask" Label="No Archive" ID="eg-005">
            <SubmitableElement>
                <Server>SASApp</Server>
            </SubmitableElement>
            <EGTask>
                <Task_CLSID>{NO-ARCH}</Task_CLSID>
                <GeneratesCodeFlag>True</GeneratesCodeFlag>
            </EGTask>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = _make_metadata("eg-005", "No Archive")

        result = parse_eg_task(node, metadata, archive=None)

        assert result.task_config is None
        assert result.eg_task_clsid == "{NO-ARCH}"

    def test_eg_task_missing_config_logs_warning(self, caplog):
        """EGTask logs warning when task config file is missing (Req 10.5/10.7)."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.EGTask" Label="Warn" ID="eg-006">
            <SubmitableElement>
                <Server>SASApp</Server>
            </SubmitableElement>
            <EGTask>
                <Task_CLSID>{WARN-001}</Task_CLSID>
                <GeneratesCodeFlag>True</GeneratesCodeFlag>
            </EGTask>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = _make_metadata("eg-006", "Warn")
        archive = _make_archive_mock({})

        import logging

        with caplog.at_level(logging.WARNING):
            result = parse_eg_task(node, metadata, archive=archive)

        assert result.task_config is None
        assert "EGTask-eg-006/EGTask-eg-006.xml" in caplog.text

    def test_eg_task_only_clsid_no_generates_flag(self):
        """EGTask with Task_CLSID but no GeneratesCodeFlag sets flag to None."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.EGTask" Label="Partial" ID="eg-007">
            <SubmitableElement>
                <Server>SASApp</Server>
            </SubmitableElement>
            <EGTask>
                <Task_CLSID>{PARTIAL-001}</Task_CLSID>
            </EGTask>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = _make_metadata("eg-007", "Partial")

        result = parse_eg_task(node, metadata, archive=None)

        assert result.eg_task_clsid == "{PARTIAL-001}"
        assert result.generates_code_flag is None


# --- ExportTask Tests ---


class TestParseExportTask:
    """Tests for parse_export_task function."""

    def test_basic_export_task(self):
        """ExportTask extracts Parent and task config from ExportTask section."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.ExportTask" Label="Export" ID="ex-001">
            <SubmitableElement>
                <Server>SASApp</Server>
                <HASWARNING>True</HASWARNING>
            </SubmitableElement>
            <ExportTask>
                <Parent>shortcut-id-1</Parent>
                <OutputFormat>CSV</OutputFormat>
                <Delimiter>,</Delimiter>
            </ExportTask>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = _make_metadata("ex-001", "Export")

        result = parse_export_task(node, metadata)

        assert isinstance(result, ExportTaskElement)
        assert result.metadata == metadata
        assert result.submitable.server == "SASApp"
        assert result.submitable.has_warning is True
        assert result.parent_id == "shortcut-id-1"
        assert result.task_config is not None
        assert result.task_config["OutputFormat"] == "CSV"
        assert result.task_config["Delimiter"] == ","

    def test_export_task_no_export_section(self):
        """ExportTask with missing ExportTask section returns None fields."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.ExportTask" Label="Bare Export" ID="ex-002">
            <SubmitableElement>
                <Server>SASApp</Server>
            </SubmitableElement>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = _make_metadata("ex-002", "Bare Export")

        result = parse_export_task(node, metadata)

        assert result.parent_id is None
        assert result.task_config is None

    def test_export_task_parent_only(self):
        """ExportTask with only Parent in ExportTask section."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.ExportTask" Label="Parent Only" ID="ex-003">
            <SubmitableElement>
                <Server>SASApp</Server>
            </SubmitableElement>
            <ExportTask>
                <Parent>sc-id-123</Parent>
            </ExportTask>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = _make_metadata("ex-003", "Parent Only")

        result = parse_export_task(node, metadata)

        assert result.parent_id == "sc-id-123"
        assert result.task_config is None  # No other config elements

    def test_export_task_with_nested_config(self):
        """ExportTask with nested config elements in ExportTask section (Req 10.5)."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.ExportTask" Label="Nested" ID="ex-004">
            <SubmitableElement>
                <Server>SASApp</Server>
            </SubmitableElement>
            <ExportTask>
                <Parent>sc-nested-1</Parent>
                <OutputFormat>Excel</OutputFormat>
                <Options>
                    <SheetName>Results</SheetName>
                    <IncludeHeader>True</IncludeHeader>
                </Options>
            </ExportTask>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = _make_metadata("ex-004", "Nested")

        result = parse_export_task(node, metadata)

        assert result.parent_id == "sc-nested-1"
        assert result.task_config is not None
        assert result.task_config["OutputFormat"] == "Excel"
        # Nested elements should be converted to dict structure
        assert "Options" in result.task_config


# --- AppendTask Tests ---


class TestParseAppendTask:
    """Tests for parse_append_task function."""

    def test_basic_append_task(self):
        """AppendTask extracts Parent and InputDataRefs."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.AppendTask" Label="Append" ID="ap-001">
            <SubmitableElement>
                <Server>SASApp</Server>
                <HASERROR>False</HASERROR>
            </SubmitableElement>
            <AppendTask>
                <Parent>shortcut-id</Parent>
                <InputDataRefs>
                    <DataRef>data-1</DataRef>
                    <DataRef>data-2</DataRef>
                    <DataRef>data-3</DataRef>
                </InputDataRefs>
            </AppendTask>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = _make_metadata("ap-001", "Append")

        result = parse_append_task(node, metadata)

        assert isinstance(result, AppendTaskElement)
        assert result.metadata == metadata
        assert result.submitable.server == "SASApp"
        assert result.submitable.has_error is False
        assert result.parent_id == "shortcut-id"
        assert result.input_data_refs == ["data-1", "data-2", "data-3"]

    def test_append_task_no_append_section(self):
        """AppendTask with missing AppendTask section returns None/empty fields."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.AppendTask" Label="Bare Append" ID="ap-002">
            <SubmitableElement>
                <Server>SASApp</Server>
            </SubmitableElement>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = _make_metadata("ap-002", "Bare Append")

        result = parse_append_task(node, metadata)

        assert result.parent_id is None
        assert result.input_data_refs == []
        assert result.task_config is None

    def test_append_task_empty_input_data_refs(self):
        """AppendTask with empty InputDataRefs returns empty list."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.AppendTask" Label="Empty Refs" ID="ap-003">
            <SubmitableElement>
                <Server>SASApp</Server>
            </SubmitableElement>
            <AppendTask>
                <Parent>sc-parent</Parent>
                <InputDataRefs>
                </InputDataRefs>
            </AppendTask>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = _make_metadata("ap-003", "Empty Refs")

        result = parse_append_task(node, metadata)

        assert result.parent_id == "sc-parent"
        assert result.input_data_refs == []

    def test_append_task_with_extra_config(self):
        """AppendTask with additional config elements beyond Parent and InputDataRefs."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.AppendTask" Label="Extra Config" ID="ap-004">
            <SubmitableElement>
                <Server>SASApp</Server>
            </SubmitableElement>
            <AppendTask>
                <Parent>sc-parent-2</Parent>
                <InputDataRefs>
                    <DataRef>data-x</DataRef>
                </InputDataRefs>
                <AppendMode>Replace</AppendMode>
            </AppendTask>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = _make_metadata("ap-004", "Extra Config")

        result = parse_append_task(node, metadata)

        assert result.parent_id == "sc-parent-2"
        assert result.input_data_refs == ["data-x"]
        assert result.task_config is not None
        assert result.task_config["AppendMode"] == "Replace"

    def test_append_task_no_submitable(self):
        """AppendTask with missing SubmitableElement returns default submitable."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.AppendTask" Label="No Sub" ID="ap-005">
            <AppendTask>
                <Parent>parent-ref</Parent>
                <InputDataRefs>
                    <DataRef>ref-1</DataRef>
                </InputDataRefs>
            </AppendTask>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = _make_metadata("ap-005", "No Sub")

        result = parse_append_task(node, metadata)

        assert result.submitable is not None
        assert result.submitable.server is None
        assert result.parent_id == "parent-ref"
        assert result.input_data_refs == ["ref-1"]


# --- ImportTask Tests ---


class TestParseImportTask:
    """Tests for parse_import_task function."""

    def test_basic_import_task_with_all_sections(self):
        """ImportTask extracts EGTask section, ImportTask section, and task config."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.ImportTask" Label="Import Data" ID="it-001">
            <SubmitableElement>
                <Server>SASApp</Server>
                <HASERROR>False</HASERROR>
            </SubmitableElement>
            <EGTask>
                <Task_CLSID>{IMPORT-CLSID-123}</Task_CLSID>
                <CurrentViewType>Default</CurrentViewType>
                <Obs>100</Obs>
                <FirstObs>1</FirstObs>
                <GeneratesCodeFlag>True</GeneratesCodeFlag>
                <GenerateOutputDataNames>WORK.IMPORTED</GenerateOutputDataNames>
                <VarNameParameters>ScanNameRow</VarNameParameters>
                <InputDatalist>
                    <Data ID="data-ref-1"/>
                    <Data ID="data-ref-2"/>
                </InputDatalist>
            </EGTask>
            <ImportTask>
                <Parent>shortcut-parent-id</Parent>
            </ImportTask>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = _make_metadata("it-001", "Import Data")
        config_xml = "<ImportConfig><Delimiter>,</Delimiter><HasHeader>True</HasHeader></ImportConfig>"
        archive = _make_archive_mock(
            {
                "ImportTask-it-001/ImportTask-it-001.xml": config_xml,
            }
        )

        result = parse_import_task(node, metadata, archive=archive)

        assert isinstance(result, ImportTaskElement)
        assert result.metadata == metadata
        assert result.submitable is not None
        assert result.submitable.server == "SASApp"
        assert result.submitable.has_error is False
        assert result.eg_task_clsid == "{IMPORT-CLSID-123}"
        assert result.current_view_type == "Default"
        assert result.obs == 100
        assert result.first_obs == 1
        assert result.generates_code_flag is True
        assert result.generate_output_data_names == "WORK.IMPORTED"
        assert result.var_name_parameters == "ScanNameRow"
        assert result.input_data_list == ["data-ref-1", "data-ref-2"]
        assert result.parent_id == "shortcut-parent-id"
        assert result.task_config is not None
        assert result.task_config["Delimiter"] == {"#text": ","}
        assert result.task_config["HasHeader"] == {"#text": "True"}

    def test_import_task_missing_eg_task_raises_error(self):
        """ImportTask raises ValueError if EGTask section is missing."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.ImportTask" Label="No EGTask" ID="it-002">
            <SubmitableElement>
                <Server>SASApp</Server>
            </SubmitableElement>
            <ImportTask>
                <Parent>some-parent</Parent>
            </ImportTask>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = _make_metadata("it-002", "No EGTask")

        with pytest.raises(ValueError, match="missing required EGTask section"):
            parse_import_task(node, metadata, archive=None)

    def test_import_task_missing_import_task_section_raises_error(self):
        """ImportTask raises ValueError if ImportTask section is missing."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.ImportTask" Label="No ImportTask" ID="it-003">
            <SubmitableElement>
                <Server>SASApp</Server>
            </SubmitableElement>
            <EGTask>
                <Task_CLSID>{ABC}</Task_CLSID>
                <GeneratesCodeFlag>True</GeneratesCodeFlag>
            </EGTask>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = _make_metadata("it-003", "No ImportTask")

        with pytest.raises(ValueError, match="missing required ImportTask section"):
            parse_import_task(node, metadata, archive=None)

    def test_import_task_malformed_config_raises_error(self):
        """ImportTask raises ValueError if Task_Config XML is malformed."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.ImportTask" Label="Bad Config" ID="it-004">
            <SubmitableElement>
                <Server>SASApp</Server>
            </SubmitableElement>
            <EGTask>
                <Task_CLSID>{CONFIG-BAD}</Task_CLSID>
                <GeneratesCodeFlag>True</GeneratesCodeFlag>
            </EGTask>
            <ImportTask>
                <Parent>parent-ref</Parent>
            </ImportTask>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = _make_metadata("it-004", "Bad Config")
        archive = _make_archive_mock(
            {
                "ImportTask-it-004/ImportTask-it-004.xml": "<broken><xml not closed",
            }
        )

        with pytest.raises(ValueError, match="malformed"):
            parse_import_task(node, metadata, archive=archive)

    def test_import_task_missing_config_file_sets_none(self):
        """ImportTask sets task_config to None if config file is missing from archive."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.ImportTask" Label="No Config" ID="it-005">
            <SubmitableElement>
                <Server>SASApp</Server>
            </SubmitableElement>
            <EGTask>
                <Task_CLSID>{NO-CONFIG}</Task_CLSID>
                <GeneratesCodeFlag>False</GeneratesCodeFlag>
            </EGTask>
            <ImportTask>
                <Parent>parent-ref-2</Parent>
            </ImportTask>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = _make_metadata("it-005", "No Config")
        archive = _make_archive_mock({})  # empty archive

        result = parse_import_task(node, metadata, archive=archive)

        assert result.task_config is None
        assert result.eg_task_clsid == "{NO-CONFIG}"
        assert result.parent_id == "parent-ref-2"

    def test_import_task_no_archive(self):
        """ImportTask with no archive leaves task_config as None."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.ImportTask" Label="No Archive" ID="it-006">
            <SubmitableElement>
                <Server>SASApp</Server>
            </SubmitableElement>
            <EGTask>
                <Task_CLSID>{NO-ARCH}</Task_CLSID>
                <GeneratesCodeFlag>True</GeneratesCodeFlag>
            </EGTask>
            <ImportTask>
                <Parent>parent-ref-3</Parent>
            </ImportTask>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = _make_metadata("it-006", "No Archive")

        result = parse_import_task(node, metadata, archive=None)

        assert result.task_config is None
        assert result.eg_task_clsid == "{NO-ARCH}"
        assert result.parent_id == "parent-ref-3"

    def test_import_task_empty_parent(self):
        """ImportTask with empty Parent element sets parent_id to None."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.ImportTask" Label="Empty Parent" ID="it-007">
            <SubmitableElement>
                <Server>SASApp</Server>
            </SubmitableElement>
            <EGTask>
                <Task_CLSID>{EMPTY-PARENT}</Task_CLSID>
                <GeneratesCodeFlag>True</GeneratesCodeFlag>
            </EGTask>
            <ImportTask>
                <Parent>  </Parent>
            </ImportTask>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = _make_metadata("it-007", "Empty Parent")

        result = parse_import_task(node, metadata, archive=None)

        assert result.parent_id is None

    def test_import_task_empty_input_data_list(self):
        """ImportTask with empty InputDatalist returns empty list."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.ImportTask" Label="No Inputs" ID="it-008">
            <SubmitableElement>
                <Server>SASApp</Server>
            </SubmitableElement>
            <EGTask>
                <Task_CLSID>{NO-INPUTS}</Task_CLSID>
                <GeneratesCodeFlag>True</GeneratesCodeFlag>
                <InputDatalist>
                </InputDatalist>
            </EGTask>
            <ImportTask>
                <Parent>parent-id</Parent>
            </ImportTask>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = _make_metadata("it-008", "No Inputs")

        result = parse_import_task(node, metadata, archive=None)

        assert result.input_data_list == []

    def test_import_task_no_input_data_list_section(self):
        """ImportTask with no InputDatalist section returns empty list."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.ImportTask" Label="No List" ID="it-009">
            <SubmitableElement>
                <Server>SASApp</Server>
            </SubmitableElement>
            <EGTask>
                <Task_CLSID>{NO-LIST}</Task_CLSID>
                <GeneratesCodeFlag>True</GeneratesCodeFlag>
            </EGTask>
            <ImportTask>
                <Parent>parent-id</Parent>
            </ImportTask>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = _make_metadata("it-009", "No List")

        result = parse_import_task(node, metadata, archive=None)

        assert result.input_data_list == []


# --- Archive path resolution ---


class TestPrefixedElementIds:
    """Element IDs that already carry their type prefix resolve to the right path.

    Enterprise Guide writes IDs such as ``CodeTask-xjq1AoRtuimaEV8v``. Prefixing
    those again produced ``CodeTask-CodeTask-.../code.sas``, which silently
    matched nothing and blanked every code body and task config.
    """

    def test_code_task_id_is_not_prefixed_twice(self):
        xml = """
        <Element Type="SAS.EG.ProjectElements.CodeTask" Label="Prefixed" ID="CodeTask-abc123">
            <SubmitableElement><Server>SASApp</Server></SubmitableElement>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = _make_metadata("CodeTask-abc123", "Prefixed")
        archive = _make_archive_mock({"CodeTask-abc123/code.sas": "data a; run;"})

        result = parse_code_task(node, metadata, archive=archive)

        assert result.code_content == "data a; run;"

    def test_bare_code_task_id_still_gets_its_prefix(self):
        """The pre-existing bare-ID layout keeps working."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.CodeTask" Label="Bare" ID="ct-001">
            <SubmitableElement><Server>SASApp</Server></SubmitableElement>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = _make_metadata("ct-001", "Bare")
        archive = _make_archive_mock({"CodeTask-ct-001/code.sas": "data b; run;"})

        result = parse_code_task(node, metadata, archive=archive)

        assert result.code_content == "data b; run;"

    def test_eg_task_id_is_not_prefixed_twice(self):
        xml = """
        <Element Type="SAS.EG.ProjectElements.EGTask" Label="Prefixed" ID="EGTask-abc123">
            <SubmitableElement><Server>SASApp</Server></SubmitableElement>
            <EGTask><Task_CLSID>{X}</Task_CLSID></EGTask>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = _make_metadata("EGTask-abc123", "Prefixed")
        archive = _make_archive_mock(
            {"EGTask-abc123/EGTask-abc123.xml": "<Task_Config><A>1</A></Task_Config>"}
        )

        result = parse_eg_task(node, metadata, archive=archive)

        assert result.task_config is not None

    def test_import_task_id_is_not_prefixed_twice(self):
        xml = """
        <Element Type="SAS.EG.ProjectElements.ImportTask" Label="Prefixed" ID="ImportTask-abc123">
            <SubmitableElement><Server>SASApp</Server></SubmitableElement>
            <EGTask><Task_CLSID>{X}</Task_CLSID></EGTask>
            <ImportTask><Parent>p</Parent></ImportTask>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = _make_metadata("ImportTask-abc123", "Prefixed")
        archive = _make_archive_mock(
            {
                "ImportTask-abc123/ImportTask-abc123.xml": (
                    "<Task_Config><A>1</A></Task_Config>"
                )
            }
        )

        result = parse_import_task(node, metadata, archive=archive)

        assert result.task_config is not None
