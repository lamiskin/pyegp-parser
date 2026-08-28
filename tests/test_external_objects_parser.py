"""Unit tests for the External_Objects parser.

Tests the parsing of ExternalObject entries from the External_Objects
section of project.xml, including both child-text-element and attribute-based
formats, error handling, and edge cases.
"""

import xml.etree.ElementTree as ET

import pytest

from pyegp_parser.parsers.external_objects_parser import parse_external_objects


class TestParseExternalObjectsAbsentSection:
    """Tests for when the External_Objects section is absent."""

    def test_absent_section_returns_empty_list(self):
        """If External_Objects section is absent, return empty list (not error)."""
        root = ET.fromstring("<ProjectCollection></ProjectCollection>")
        result = parse_external_objects(root)
        assert result == []

    def test_empty_root_returns_empty_list(self):
        """Empty root with no children returns empty list."""
        root = ET.fromstring("<ProjectCollection/>")
        result = parse_external_objects(root)
        assert result == []


class TestParseExternalObjectsChildTextFormat:
    """Tests for ExternalObject entries using child text element format."""

    def test_single_object_all_fields(self):
        """Parse a single ExternalObject with all named fields as child elements."""
        xml = """<ProjectCollection>
          <External_Objects>
            <ExternalObject>
              <Name>SAS_Library</Name>
              <Type>Library</Type>
              <Path>/opt/sas/saslib</Path>
              <Description>Production SAS library</Description>
            </ExternalObject>
          </External_Objects>
        </ProjectCollection>"""
        root = ET.fromstring(xml)
        result = parse_external_objects(root)

        assert len(result) == 1
        obj = result[0]
        assert obj.name == "SAS_Library"
        assert obj.type == "Library"
        assert obj.path == "/opt/sas/saslib"
        assert obj.description == "Production SAS library"
        assert obj.metadata == {}

    def test_object_with_additional_metadata(self):
        """Extra child elements are captured in the metadata dict."""
        xml = """<ProjectCollection>
          <External_Objects>
            <ExternalObject>
              <Name>DataFile</Name>
              <Type>File</Type>
              <Path>/data/input.csv</Path>
              <Format>CSV</Format>
              <Encoding>UTF-8</Encoding>
            </ExternalObject>
          </External_Objects>
        </ProjectCollection>"""
        root = ET.fromstring(xml)
        result = parse_external_objects(root)

        assert len(result) == 1
        obj = result[0]
        assert obj.name == "DataFile"
        assert obj.type == "File"
        assert obj.path == "/data/input.csv"
        assert obj.metadata == {"Format": "CSV", "Encoding": "UTF-8"}

    def test_multiple_objects(self):
        """Parse multiple ExternalObject entries."""
        xml = """<ProjectCollection>
          <External_Objects>
            <ExternalObject>
              <Name>Obj1</Name>
              <Type>Library</Type>
            </ExternalObject>
            <ExternalObject>
              <Name>Obj2</Name>
              <Type>File</Type>
              <Path>/tmp/data.sas7bdat</Path>
            </ExternalObject>
            <ExternalObject>
              <Name>Obj3</Name>
              <Type>Connection</Type>
              <Description>Database connection</Description>
            </ExternalObject>
          </External_Objects>
        </ProjectCollection>"""
        root = ET.fromstring(xml)
        result = parse_external_objects(root)

        assert len(result) == 3
        assert result[0].name == "Obj1"
        assert result[0].type == "Library"
        assert result[1].name == "Obj2"
        assert result[1].path == "/tmp/data.sas7bdat"
        assert result[2].name == "Obj3"
        assert result[2].description == "Database connection"

    def test_name_only_minimal_object(self):
        """An object with only a Name is valid (other fields optional)."""
        xml = """<ProjectCollection>
          <External_Objects>
            <ExternalObject>
              <Name>MinimalObj</Name>
            </ExternalObject>
          </External_Objects>
        </ProjectCollection>"""
        root = ET.fromstring(xml)
        result = parse_external_objects(root)

        assert len(result) == 1
        obj = result[0]
        assert obj.name == "MinimalObj"
        assert obj.type is None
        assert obj.path is None
        assert obj.description is None
        assert obj.metadata == {}


class TestParseExternalObjectsAttributeFormat:
    """Tests for ExternalObject entries using XML attribute format."""

    def test_single_object_attributes(self):
        """Parse ExternalObject with all fields as XML attributes."""
        xml = """<ProjectCollection>
          <External_Objects>
            <ExternalObject Name="AttrObj" Type="File" Path="/data/file.csv" Description="A data file"/>
          </External_Objects>
        </ProjectCollection>"""
        root = ET.fromstring(xml)
        result = parse_external_objects(root)

        assert len(result) == 1
        obj = result[0]
        assert obj.name == "AttrObj"
        assert obj.type == "File"
        assert obj.path == "/data/file.csv"
        assert obj.description == "A data file"

    def test_attribute_format_with_extra_attrs(self):
        """Extra attributes go into the metadata dict."""
        xml = """<ProjectCollection>
          <External_Objects>
            <ExternalObject Name="WithExtras" Type="DB" Server="prod-db" Port="5432"/>
          </External_Objects>
        </ProjectCollection>"""
        root = ET.fromstring(xml)
        result = parse_external_objects(root)

        assert len(result) == 1
        obj = result[0]
        assert obj.name == "WithExtras"
        assert obj.type == "DB"
        assert obj.metadata == {"Server": "prod-db", "Port": "5432"}


class TestParseExternalObjectsErrors:
    """Tests for error handling in external object parsing."""

    def test_missing_name_raises_value_error(self):
        """ExternalObject without Name raises ValueError."""
        xml = """<ProjectCollection>
          <External_Objects>
            <ExternalObject>
              <Type>File</Type>
              <Path>/data/file.csv</Path>
            </ExternalObject>
          </External_Objects>
        </ProjectCollection>"""
        root = ET.fromstring(xml)

        with pytest.raises(ValueError, match="missing required 'Name' field"):
            parse_external_objects(root)

    def test_empty_name_raises_value_error(self):
        """ExternalObject with empty Name text raises ValueError."""
        xml = """<ProjectCollection>
          <External_Objects>
            <ExternalObject>
              <Name>   </Name>
              <Type>File</Type>
            </ExternalObject>
          </External_Objects>
        </ProjectCollection>"""
        root = ET.fromstring(xml)

        with pytest.raises(ValueError, match="missing required 'Name' field"):
            parse_external_objects(root)

    def test_empty_name_attribute_raises_value_error(self):
        """ExternalObject with empty Name attribute raises ValueError."""
        xml = """<ProjectCollection>
          <External_Objects>
            <ExternalObject Name="   " Type="File"/>
          </External_Objects>
        </ProjectCollection>"""
        root = ET.fromstring(xml)

        with pytest.raises(ValueError, match="missing required 'Name' field"):
            parse_external_objects(root)

    def test_completely_empty_element_raises_value_error(self):
        """Completely empty ExternalObject element raises ValueError."""
        xml = """<ProjectCollection>
          <External_Objects>
            <ExternalObject/>
          </External_Objects>
        </ProjectCollection>"""
        root = ET.fromstring(xml)

        with pytest.raises(ValueError, match="missing required 'Name' field"):
            parse_external_objects(root)


class TestParseExternalObjectsEdgeCases:
    """Tests for edge cases and mixed formats."""

    def test_empty_external_objects_section(self):
        """External_Objects section with no children returns empty list."""
        xml = """<ProjectCollection>
          <External_Objects>
          </External_Objects>
        </ProjectCollection>"""
        root = ET.fromstring(xml)
        result = parse_external_objects(root)
        assert result == []

    def test_whitespace_in_values_is_stripped(self):
        """Whitespace around text values is stripped."""
        xml = """<ProjectCollection>
          <External_Objects>
            <ExternalObject>
              <Name>  SpacedName  </Name>
              <Type>  Library  </Type>
            </ExternalObject>
          </External_Objects>
        </ProjectCollection>"""
        root = ET.fromstring(xml)
        result = parse_external_objects(root)

        assert result[0].name == "SpacedName"
        assert result[0].type == "Library"

    def test_child_element_takes_precedence_over_attribute(self):
        """When both child element and attribute exist, child element wins."""
        xml = """<ProjectCollection>
          <External_Objects>
            <ExternalObject Name="AttrName" Type="AttrType">
              <Name>ChildName</Name>
              <Type>ChildType</Type>
            </ExternalObject>
          </External_Objects>
        </ProjectCollection>"""
        root = ET.fromstring(xml)
        result = parse_external_objects(root)

        # Child text element should take precedence
        assert result[0].name == "ChildName"
        assert result[0].type == "ChildType"
