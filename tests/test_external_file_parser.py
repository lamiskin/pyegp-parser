"""Unit tests for the external file list parser.

Covers:
1. Full parsing with all fields populated (Req 4.1, 4.2, 4.3)
2. ValueError when DNA is absent (Req 4.4)
3. ValueError when DNA is malformed (Req 4.4)
4. Empty list when ExternalFileList section is absent (Req 4.5)
5. Multiple external files
6. ShortCutList handling (empty, single, multiple)
7. Element metadata extraction with InputIDs
"""

import xml.etree.ElementTree as ET

import pytest

from pyegp_parser.models.external_file import ExternalFileItem
from pyegp_parser.parsers.data_parser import parse_external_file_list
from pyegp_parser.parsers.dna_parser import DNADescriptor

# --- Test XML fixtures ---

FULL_EXTERNAL_FILE_XML = """\
<ProjectCollection>
  <ExternalFileList>
    <ExternalFile>
      <Element Label="input.csv" Type="SAS.EG.ProjectElements.ExternalFile" ID="ef-001"
               CreatedOn="2023-01-01T00:00:00" ModifiedOn="2023-06-01T12:00:00"
               ModifiedBy="admin" ModifiedByEGID="EG01" ModifiedByEGVer="8.1"
               HasSerializationError="False">
        <InputIDs>
          <ID>input-1</ID>
        </InputIDs>
      </Element>
      <ShortCutList>
        <ShortCutID>shortcut-001</ShortCutID>
      </ShortCutList>
      <FileTypeType>CSV</FileTypeType>
      <DNA>&lt;DNA&gt;&lt;Type&gt;SAS.Files.FileDef&lt;/Type&gt;&lt;Name&gt;input.csv&lt;/Name&gt;&lt;Version&gt;1.0&lt;/Version&gt;&lt;FullPath&gt;C:\\Data\\input.csv&lt;/FullPath&gt;&lt;/DNA&gt;</DNA>
    </ExternalFile>
  </ExternalFileList>
</ProjectCollection>"""

MULTIPLE_FILES_XML = """\
<ProjectCollection>
  <ExternalFileList>
    <ExternalFile>
      <Element Label="file1.csv" Type="SAS.EG.ProjectElements.ExternalFile" ID="ef-001" />
      <FileTypeType>CSV</FileTypeType>
      <DNA>&lt;DNA&gt;&lt;Type&gt;SAS.Files.FileDef&lt;/Type&gt;&lt;Name&gt;file1.csv&lt;/Name&gt;&lt;Version&gt;1.0&lt;/Version&gt;&lt;FullPath&gt;C:\\file1.csv&lt;/FullPath&gt;&lt;/DNA&gt;</DNA>
    </ExternalFile>
    <ExternalFile>
      <Element Label="file2.xlsx" Type="SAS.EG.ProjectElements.ExternalFile" ID="ef-002" />
      <ShortCutList>
        <ShortCutID>sc-A</ShortCutID>
        <ShortCutID>sc-B</ShortCutID>
      </ShortCutList>
      <FileTypeType>XLSX</FileTypeType>
      <DNA>&lt;DNA&gt;&lt;Type&gt;SAS.Files.FileDef&lt;/Type&gt;&lt;Name&gt;file2.xlsx&lt;/Name&gt;&lt;Version&gt;2.0&lt;/Version&gt;&lt;FullPath&gt;D:\\file2.xlsx&lt;/FullPath&gt;&lt;/DNA&gt;</DNA>
    </ExternalFile>
  </ExternalFileList>
</ProjectCollection>"""

NO_EXTERNAL_FILE_LIST_XML = """\
<ProjectCollection>
  <Elements>
    <Element Label="test" ID="e1" />
  </Elements>
</ProjectCollection>"""

MISSING_DNA_XML = """\
<ProjectCollection>
  <ExternalFileList>
    <ExternalFile>
      <Element Label="no_dna.csv" Type="SAS.EG.ProjectElements.ExternalFile" ID="ef-bad" />
      <FileTypeType>CSV</FileTypeType>
    </ExternalFile>
  </ExternalFileList>
</ProjectCollection>"""

MALFORMED_DNA_XML = """\
<ProjectCollection>
  <ExternalFileList>
    <ExternalFile>
      <Element Label="bad_dna.csv" Type="SAS.EG.ProjectElements.ExternalFile" ID="ef-malformed" />
      <FileTypeType>CSV</FileTypeType>
      <DNA>this is not valid xml at all { } &lt; &gt;</DNA>
    </ExternalFile>
  </ExternalFileList>
</ProjectCollection>"""

EMPTY_DNA_XML = """\
<ProjectCollection>
  <ExternalFileList>
    <ExternalFile>
      <Element Label="empty_dna.csv" Type="SAS.EG.ProjectElements.ExternalFile" ID="ef-empty" />
      <FileTypeType>CSV</FileTypeType>
      <DNA>   </DNA>
    </ExternalFile>
  </ExternalFileList>
</ProjectCollection>"""

NO_ELEMENT_XML = """\
<ProjectCollection>
  <ExternalFileList>
    <ExternalFile>
      <FileTypeType>CSV</FileTypeType>
      <DNA>&lt;DNA&gt;&lt;Type&gt;SAS.Files.FileDef&lt;/Type&gt;&lt;Name&gt;test&lt;/Name&gt;&lt;Version&gt;1.0&lt;/Version&gt;&lt;FullPath&gt;C:\\test&lt;/FullPath&gt;&lt;/DNA&gt;</DNA>
    </ExternalFile>
  </ExternalFileList>
</ProjectCollection>"""

DNA_WITH_PARENT_XML = """\
<ProjectCollection>
  <ExternalFileList>
    <ExternalFile>
      <Element Label="nested.csv" Type="SAS.EG.ProjectElements.ExternalFile" ID="ef-nested" />
      <FileTypeType>CSV</FileTypeType>
      <DNA>&lt;DNA&gt;&lt;Type&gt;SAS.Files.FileDef&lt;/Type&gt;&lt;Name&gt;nested.csv&lt;/Name&gt;&lt;Version&gt;1.0&lt;/Version&gt;&lt;FullPath&gt;C:\\nested.csv&lt;/FullPath&gt;&lt;ParentDNA&gt;&amp;lt;DNA&amp;gt;&amp;lt;Type&amp;gt;SAS.Servers.ServerDef&amp;lt;/Type&amp;gt;&amp;lt;Name&amp;gt;ServerA&amp;lt;/Name&amp;gt;&amp;lt;Version&amp;gt;2.0&amp;lt;/Version&amp;gt;&amp;lt;/DNA&amp;gt;&lt;/ParentDNA&gt;&lt;/DNA&gt;</DNA>
    </ExternalFile>
  </ExternalFileList>
</ProjectCollection>"""


# --- Helper ---


def _parse(xml_str: str) -> list[ExternalFileItem]:
    """Parse XML string and return external file items."""
    root = ET.fromstring(xml_str)
    return parse_external_file_list(root)


# --- Tests ---


class TestParseExternalFileListFull:
    """Test full extraction with all fields populated (Req 4.1, 4.2, 4.3)."""

    def test_extracts_element_metadata(self):
        """Req 4.1: Extract Element metadata fields."""
        items = _parse(FULL_EXTERNAL_FILE_XML)

        assert len(items) == 1
        item = items[0]
        assert item.element is not None
        assert item.element.label == "input.csv"
        assert item.element.type == "SAS.EG.ProjectElements.ExternalFile"
        assert item.element.id == "ef-001"
        assert item.element.created_on == "2023-01-01T00:00:00"
        assert item.element.modified_on == "2023-06-01T12:00:00"
        assert item.element.modified_by == "admin"
        assert item.element.modified_by_eg_id == "EG01"
        assert item.element.modified_by_eg_ver == "8.1"
        assert item.element.has_serialization_error is False

    def test_extracts_input_ids(self):
        """Req 4.1: Extract InputIDs from Element metadata."""
        items = _parse(FULL_EXTERNAL_FILE_XML)

        assert items[0].element is not None
        assert items[0].element.input_ids == ["input-1"]

    def test_extracts_shortcut_list(self):
        """Req 4.2: Extract ShortCutList."""
        items = _parse(FULL_EXTERNAL_FILE_XML)

        assert items[0].shortcut_list == ["shortcut-001"]

    def test_extracts_file_type_type(self):
        """Req 4.2: Extract FileTypeType."""
        items = _parse(FULL_EXTERNAL_FILE_XML)

        assert items[0].file_type_type == "CSV"

    def test_extracts_raw_dna(self):
        """Req 4.2: Preserve raw DNA string."""
        items = _parse(FULL_EXTERNAL_FILE_XML)

        assert items[0].raw_dna is not None
        assert "SAS.Files.FileDef" in items[0].raw_dna

    def test_decodes_dna(self):
        """Req 4.3: Decode DNA into structured DNADescriptor."""
        items = _parse(FULL_EXTERNAL_FILE_XML)

        dna = items[0].decoded_dna
        assert dna is not None
        assert isinstance(dna, DNADescriptor)
        assert dna.type == "SAS.Files.FileDef"
        assert dna.name == "input.csv"
        assert dna.version == "1.0"
        assert dna.full_path == "C:\\Data\\input.csv"

    def test_returns_external_file_item_type(self):
        items = _parse(FULL_EXTERNAL_FILE_XML)

        assert isinstance(items[0], ExternalFileItem)


class TestParseExternalFileListMultiple:
    """Test parsing multiple external files."""

    def test_extracts_all_items(self):
        items = _parse(MULTIPLE_FILES_XML)

        assert len(items) == 2

    def test_first_item_fields(self):
        items = _parse(MULTIPLE_FILES_XML)

        assert items[0].element is not None
        assert items[0].element.label == "file1.csv"
        assert items[0].element.id == "ef-001"
        assert items[0].file_type_type == "CSV"
        assert items[0].shortcut_list == []

    def test_second_item_fields(self):
        items = _parse(MULTIPLE_FILES_XML)

        assert items[1].element is not None
        assert items[1].element.label == "file2.xlsx"
        assert items[1].element.id == "ef-002"
        assert items[1].file_type_type == "XLSX"
        assert items[1].shortcut_list == ["sc-A", "sc-B"]

    def test_dna_decoded_for_each_item(self):
        items = _parse(MULTIPLE_FILES_XML)

        assert items[0].decoded_dna is not None
        assert items[0].decoded_dna.full_path == "C:\\file1.csv"
        assert items[1].decoded_dna is not None
        assert items[1].decoded_dna.full_path == "D:\\file2.xlsx"


class TestParseExternalFileListAbsent:
    """Test empty list when ExternalFileList section absent (Req 4.5)."""

    def test_returns_empty_list(self):
        items = _parse(NO_EXTERNAL_FILE_LIST_XML)

        assert items == []

    def test_returns_list_type(self):
        items = _parse(NO_EXTERNAL_FILE_LIST_XML)

        assert isinstance(items, list)


class TestParseExternalFileListDNAAbsent:
    """Test ValueError when DNA is absent (Req 4.4)."""

    def test_raises_value_error_missing_dna(self):
        with pytest.raises(ValueError, match="ef-bad.*missing required DNA"):
            _parse(MISSING_DNA_XML)

    def test_raises_value_error_empty_dna(self):
        """Empty/whitespace-only DNA treated as absent."""
        with pytest.raises(ValueError, match="ef-empty.*missing required DNA"):
            _parse(EMPTY_DNA_XML)


class TestParseExternalFileListDNAMalformed:
    """Test ValueError when DNA is malformed (Req 4.4)."""

    def test_raises_value_error_malformed_dna(self):
        with pytest.raises(ValueError, match="ef-malformed.*malformed DNA"):
            _parse(MALFORMED_DNA_XML)

    def test_error_includes_element_id(self):
        """Error message includes the ExternalFile ID."""
        with pytest.raises(ValueError) as exc_info:
            _parse(MALFORMED_DNA_XML)
        assert "ef-malformed" in str(exc_info.value)


class TestParseExternalFileListNoElement:
    """Test parsing when Element metadata is absent."""

    def test_element_is_none(self):
        """ExternalFile without an Element child has None metadata."""
        items = _parse(NO_ELEMENT_XML)

        assert len(items) == 1
        assert items[0].element is None
        assert items[0].decoded_dna is not None

    def test_error_uses_unknown_id_when_no_element(self):
        """When no Element, missing DNA error uses 'unknown' as ID."""
        xml = """\
<ProjectCollection>
  <ExternalFileList>
    <ExternalFile>
      <FileTypeType>CSV</FileTypeType>
    </ExternalFile>
  </ExternalFileList>
</ProjectCollection>"""
        with pytest.raises(ValueError, match="unknown.*missing required DNA"):
            _parse(xml)


class TestParseExternalFileListDNAWithParent:
    """Test recursive DNA decoding with ParentDNA."""

    def test_decodes_parent_dna(self):
        items = _parse(DNA_WITH_PARENT_XML)

        assert len(items) == 1
        dna = items[0].decoded_dna
        assert dna is not None
        assert dna.type == "SAS.Files.FileDef"
        assert dna.full_path == "C:\\nested.csv"

        parent = dna.parent_dna
        assert parent is not None
        assert parent.type == "SAS.Servers.ServerDef"
        assert parent.name == "ServerA"
        assert parent.version == "2.0"


class TestParseExternalFileListShortcuts:
    """Test ShortCutList edge cases."""

    def test_absent_shortcut_list_returns_empty(self):
        """No ShortCutList element -> empty list."""
        items = _parse(MULTIPLE_FILES_XML)
        # First file has no ShortCutList
        assert items[0].shortcut_list == []

    def test_empty_shortcut_list_returns_empty(self):
        """ShortCutList present but with no children -> empty list."""
        xml = """\
<ProjectCollection>
  <ExternalFileList>
    <ExternalFile>
      <Element Label="x.csv" ID="ef-x" />
      <ShortCutList></ShortCutList>
      <FileTypeType>CSV</FileTypeType>
      <DNA>&lt;DNA&gt;&lt;Type&gt;SAS.Files.FileDef&lt;/Type&gt;&lt;Name&gt;x&lt;/Name&gt;&lt;Version&gt;1.0&lt;/Version&gt;&lt;FullPath&gt;C:\\x&lt;/FullPath&gt;&lt;/DNA&gt;</DNA>
    </ExternalFile>
  </ExternalFileList>
</ProjectCollection>"""
        items = _parse(xml)
        assert items[0].shortcut_list == []
