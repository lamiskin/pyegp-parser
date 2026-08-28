"""Unit tests for the project_parser module.

Tests parsing of project.xml content including metadata extraction,
settings parsing, parameters, application overrides, and metadata info.
"""

import pytest

from pyegp_parser.models.project import (
    Parameter,
    ParsedProject,
)
from pyegp_parser.parsers.project_parser import parse_project_xml

# --- Sample XML fixtures ---

MINIMAL_PROJECT_XML = """\
<?xml version="1.0" encoding="utf-8"?>
<ProjectCollection EGVersion="8.1" Type="SAS.EG.ProjectElements.Project">
  <Elements>
    <Element Type="SAS.EG.ProjectElements.ProcessFlowContainer"
             Label="My Project"
             ID="abc-123"
             CreatedOn="2023-01-15T10:30:00"
             ModifiedOn="2023-06-20T14:45:00"
             ModifiedBy="jsmith"
             ModifiedByEGID="EG001"
             ModifiedByEGVer="8.1"/>
  </Elements>
</ProjectCollection>
"""

FULL_PROJECT_XML = """\
<?xml version="1.0" encoding="utf-8"?>
<ProjectCollection EGVersion="8.1" Type="SAS.EG.ProjectElements.Project">
  <Elements>
    <Element Type="SAS.EG.ProjectElements.ProcessFlowContainer"
             Label="Full Project"
             ID="proj-001"
             CreatedOn="2022-03-10T08:00:00"
             ModifiedOn="2024-01-05T16:30:00"
             ModifiedBy="analyst1"
             ModifiedByEGID="EG100"
             ModifiedByEGVer="8.1"/>
  </Elements>
  <ProjectSettings>
    <UseRelativePaths>True</UseRelativePaths>
    <SubmitToGrid>False</SubmitToGrid>
    <QueueSubmitsForServer>True</QueueSubmitsForServer>
    <ActionOnError>StopProcessFlow</ActionOnError>
    <ShowProjectLogWarningMessage>True</ShowProjectLogWarningMessage>
    <RemoveOlderProjectLogItems>False</RemoveOlderProjectLogItems>
    <ExportProjectLogThenClear>False</ExportProjectLogThenClear>
    <ProjectLogExportFilename>export.log</ProjectLogExportFilename>
    <ProjectLogExportLocation>C:\\Logs</ProjectLogExportLocation>
    <ProjectLogMaxSize>500</ProjectLogMaxSize>
    <ClearProjectLogOnExit>True</ClearProjectLogOnExit>
  </ProjectSettings>
  <Parameters>
    <Parameter Name="env" Value="production"/>
    <Parameter Name="version" Value="2.0"/>
  </Parameters>
  <ApplicationOverrides>
    <Override Name="theme" Value="dark"/>
    <Setting Enabled="true">custom</Setting>
  </ApplicationOverrides>
  <MetaDataInfo>
    <MetaDataProviderName>SAS Metadata Server</MetaDataProviderName>
    <MetaDataHost>metadata.example.com</MetaDataHost>
    <MetaDataPort>8561</MetaDataPort>
  </MetaDataInfo>
</ProjectCollection>
"""

EMPTY_SECTIONS_XML = """\
<?xml version="1.0" encoding="utf-8"?>
<ProjectCollection EGVersion="7.1" Type="SAS.EG.ProjectElements.Project">
  <Elements/>
</ProjectCollection>
"""

NO_ELEMENTS_XML = """\
<?xml version="1.0" encoding="utf-8"?>
<ProjectCollection EGVersion="8.1" Type="SAS.EG.ProjectElements.Project">
</ProjectCollection>
"""


class TestParseProjectXml:
    """Tests for the parse_project_xml function."""

    def test_malformed_xml_raises_value_error(self):
        """Malformed XML raises ValueError (requirement 2.8)."""
        with pytest.raises(ValueError, match="Malformed XML"):
            parse_project_xml("<not valid xml>>>")

    def test_empty_string_raises_value_error(self):
        """Empty string input raises ValueError."""
        with pytest.raises(ValueError):
            parse_project_xml("")

    def test_returns_parsed_project(self):
        """parse_project_xml returns a ParsedProject instance."""
        result = parse_project_xml(MINIMAL_PROJECT_XML)
        assert isinstance(result, ParsedProject)


class TestMetadataExtraction:
    """Tests for metadata extraction from ProjectCollection and Element."""

    def test_eg_version_extracted(self):
        """EGVersion attribute from root is extracted (requirement 2.1)."""
        result = parse_project_xml(MINIMAL_PROJECT_XML)
        assert result.metadata.eg_version == "8.1"

    def test_type_extracted(self):
        """Type attribute from root is extracted (requirement 2.1)."""
        result = parse_project_xml(MINIMAL_PROJECT_XML)
        assert result.metadata.type == "SAS.EG.ProjectElements.Project"

    def test_element_label_extracted(self):
        """Label from first Element is extracted (requirement 2.2)."""
        result = parse_project_xml(MINIMAL_PROJECT_XML)
        assert result.metadata.label == "My Project"

    def test_element_id_extracted(self):
        """ID from first Element is extracted (requirement 2.2)."""
        result = parse_project_xml(MINIMAL_PROJECT_XML)
        assert result.metadata.id == "abc-123"

    def test_element_created_on_extracted(self):
        """CreatedOn from first Element is extracted (requirement 2.2)."""
        result = parse_project_xml(MINIMAL_PROJECT_XML)
        assert result.metadata.created_on == "2023-01-15T10:30:00"

    def test_element_modified_on_extracted(self):
        """ModifiedOn from first Element is extracted (requirement 2.2)."""
        result = parse_project_xml(MINIMAL_PROJECT_XML)
        assert result.metadata.modified_on == "2023-06-20T14:45:00"

    def test_element_modified_by_extracted(self):
        """ModifiedBy from first Element is extracted (requirement 2.2)."""
        result = parse_project_xml(MINIMAL_PROJECT_XML)
        assert result.metadata.modified_by == "jsmith"

    def test_element_modified_by_eg_id_extracted(self):
        """ModifiedByEGID from first Element is extracted (requirement 2.2)."""
        result = parse_project_xml(MINIMAL_PROJECT_XML)
        assert result.metadata.modified_by_eg_id == "EG001"

    def test_element_modified_by_eg_ver_extracted(self):
        """ModifiedByEGVer from first Element is extracted (requirement 2.2)."""
        result = parse_project_xml(MINIMAL_PROJECT_XML)
        assert result.metadata.modified_by_eg_ver == "8.1"

    def test_missing_elements_section_yields_none_fields(self):
        """When Elements section is absent, Element fields are None (req 2.7)."""
        result = parse_project_xml(NO_ELEMENTS_XML)
        assert result.metadata.eg_version == "8.1"
        assert result.metadata.label is None
        assert result.metadata.id is None
        assert result.metadata.created_on is None
        assert result.metadata.modified_on is None
        assert result.metadata.modified_by is None

    def test_empty_elements_section_yields_none_fields(self):
        """When Elements section is empty, Element fields are None (req 2.7)."""
        result = parse_project_xml(EMPTY_SECTIONS_XML)
        assert result.metadata.eg_version == "7.1"
        assert result.metadata.label is None
        assert result.metadata.id is None

    def test_root_without_eg_version_attribute(self):
        """Missing EGVersion attribute → None (requirement 2.7)."""
        xml = '<ProjectCollection Type="SAS.EG.ProjectElements.Project"><Elements/></ProjectCollection>'
        result = parse_project_xml(xml)
        assert result.metadata.eg_version is None
        assert result.metadata.type == "SAS.EG.ProjectElements.Project"


class TestSettingsExtraction:
    """Tests for ProjectSettings extraction."""

    def test_all_boolean_settings_parsed(self):
        """Boolean settings are correctly converted (requirement 2.5)."""
        result = parse_project_xml(FULL_PROJECT_XML)
        settings = result.settings
        assert settings.use_relative_paths is True
        assert settings.submit_to_grid is False
        assert settings.queue_submits_for_server is True
        assert settings.show_project_log_warning_message is True
        assert settings.remove_older_project_log_items is False
        assert settings.export_project_log_then_clear is False
        assert settings.clear_project_log_on_exit is True

    def test_string_settings_parsed(self):
        """String settings are extracted as-is (requirement 2.5)."""
        result = parse_project_xml(FULL_PROJECT_XML)
        settings = result.settings
        assert settings.action_on_error == "StopProcessFlow"
        assert settings.project_log_export_filename == "export.log"
        assert settings.project_log_export_location == "C:\\Logs"

    def test_int_settings_parsed(self):
        """Integer settings are converted correctly (requirement 2.5)."""
        result = parse_project_xml(FULL_PROJECT_XML)
        assert result.settings.project_log_max_size == 500

    def test_missing_project_settings_yields_all_none(self):
        """Missing ProjectSettings section yields all None fields (req 2.7)."""
        result = parse_project_xml(MINIMAL_PROJECT_XML)
        settings = result.settings
        assert settings.use_relative_paths is None
        assert settings.submit_to_grid is None
        assert settings.action_on_error is None
        assert settings.project_log_max_size is None

    def test_partial_settings(self):
        """Only some settings present — rest are None (requirement 2.7)."""
        xml = """\
<ProjectCollection EGVersion="8.1" Type="SAS.EG.ProjectElements.Project">
  <Elements/>
  <ProjectSettings>
    <UseRelativePaths>True</UseRelativePaths>
    <ProjectLogMaxSize>100</ProjectLogMaxSize>
  </ProjectSettings>
</ProjectCollection>"""
        result = parse_project_xml(xml)
        assert result.settings.use_relative_paths is True
        assert result.settings.project_log_max_size == 100
        assert result.settings.submit_to_grid is None
        assert result.settings.action_on_error is None


class TestParametersExtraction:
    """Tests for Parameters collection extraction."""

    def test_parameters_extracted(self):
        """Parameters with Name and Value are extracted (requirement 2.6)."""
        result = parse_project_xml(FULL_PROJECT_XML)
        assert len(result.parameters) == 2
        assert result.parameters[0] == Parameter(name="env", value="production")
        assert result.parameters[1] == Parameter(name="version", value="2.0")

    def test_missing_parameters_yields_empty_list(self):
        """Missing Parameters section yields empty list (requirement 2.7)."""
        result = parse_project_xml(MINIMAL_PROJECT_XML)
        assert result.parameters == []

    def test_empty_parameters_section(self):
        """Empty Parameters section yields empty list."""
        xml = """\
<ProjectCollection EGVersion="8.1" Type="SAS.EG.ProjectElements.Project">
  <Elements/>
  <Parameters/>
</ProjectCollection>"""
        result = parse_project_xml(xml)
        assert result.parameters == []

    def test_parameter_missing_value_attribute_skipped(self):
        """Parameters without Value attribute are skipped."""
        xml = """\
<ProjectCollection EGVersion="8.1" Type="SAS.EG.ProjectElements.Project">
  <Elements/>
  <Parameters>
    <Parameter Name="valid" Value="yes"/>
    <Parameter Name="invalid"/>
  </Parameters>
</ProjectCollection>"""
        result = parse_project_xml(xml)
        assert len(result.parameters) == 1
        assert result.parameters[0].name == "valid"


class TestApplicationOverrides:
    """Tests for ApplicationOverrides section extraction."""

    def test_application_overrides_extracted(self):
        """ApplicationOverrides section is extracted as dict (req 2.3)."""
        result = parse_project_xml(FULL_PROJECT_XML)
        assert result.application_overrides is not None
        assert isinstance(result.application_overrides, dict)

    def test_application_overrides_preserves_children(self):
        """Child elements and attributes are preserved (requirement 2.3)."""
        result = parse_project_xml(FULL_PROJECT_XML)
        overrides = result.application_overrides
        # Should contain child elements Override and Setting
        assert "Override" in overrides
        assert "Setting" in overrides
        # Override should have attributes
        assert overrides["Override"]["_attributes"]["Name"] == "theme"
        assert overrides["Override"]["_attributes"]["Value"] == "dark"
        # Setting should have text content and attributes
        assert overrides["Setting"]["_text"] == "custom"
        assert overrides["Setting"]["_attributes"]["Enabled"] == "true"

    def test_missing_application_overrides_yields_none(self):
        """Missing ApplicationOverrides section yields None (req 2.7)."""
        result = parse_project_xml(MINIMAL_PROJECT_XML)
        assert result.application_overrides is None


class TestMetaDataInfo:
    """Tests for MetaDataInfo section extraction."""

    def test_metadata_info_extracted(self):
        """MetaDataInfo fields are extracted correctly (requirement 2.4)."""
        result = parse_project_xml(FULL_PROJECT_XML)
        assert result.metadata_info is not None
        assert result.metadata_info["metadata_provider_name"] == "SAS Metadata Server"
        assert result.metadata_info["metadata_host"] == "metadata.example.com"
        assert result.metadata_info["metadata_port"] == "8561"

    def test_missing_metadata_info_yields_none(self):
        """Missing MetaDataInfo section yields None (requirement 2.7)."""
        result = parse_project_xml(MINIMAL_PROJECT_XML)
        assert result.metadata_info is None

    def test_partial_metadata_info(self):
        """Partial MetaDataInfo — missing fields are None (req 2.7)."""
        xml = """\
<ProjectCollection EGVersion="8.1" Type="SAS.EG.ProjectElements.Project">
  <Elements/>
  <MetaDataInfo>
    <MetaDataHost>server.local</MetaDataHost>
  </MetaDataInfo>
</ProjectCollection>"""
        result = parse_project_xml(xml)
        assert result.metadata_info["metadata_host"] == "server.local"
        assert result.metadata_info["metadata_provider_name"] is None
        assert result.metadata_info["metadata_port"] is None
