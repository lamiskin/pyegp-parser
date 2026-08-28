"""Unit tests for the DataList parser.

Tests cover:
- Full DataList extraction with all fields populated
- Missing DataList section returns empty list
- Absent/empty RawActiveDataSourceState sets decoded_dna to None
- Absent ShortCutList returns empty list
- Multiple Data items are all extracted
- Absent Element metadata fields default to None
- InputIDs extraction from Element child nodes
- HasSerializationError boolean parsing
"""

import xml.etree.ElementTree as ET

from pyegp_parser.parsers.data_parser import parse_data_list
from pyegp_parser.parsers.dna_parser import DNADescriptor

# --- Fixtures ---


FULL_DATA_LIST_XML = """\
<ProjectCollection>
  <DataList>
    <Data>
      <Element Label="WORK.MYDATA" Type="SAS.EG.ProjectElements.DataSet"
               ID="data-001" Container="container-1"
               CreatedOn="2023-01-01T00:00:00" ModifiedOn="2023-06-01T12:00:00"
               ModifiedBy="admin" ModifiedByEGID="EG01" ModifiedByEGVer="8.1"
               HasSerializationError="False">
        <InputIDs>
          <ID>input-1</ID>
          <ID>input-2</ID>
        </InputIDs>
      </Element>
      <Server>SASApp</Server>
      <ActiveDataSource>ds-ref</ActiveDataSource>
      <DisplayName>WORK.MYDATA</DisplayName>
      <Table>MYDATA</Table>
      <RawActiveDataSourceState>&lt;DNA&gt;&lt;Type&gt;SAS.Servers.ServerDef&lt;/Type&gt;&lt;Name&gt;SASApp&lt;/Name&gt;&lt;Version&gt;1.0&lt;/Version&gt;&lt;/DNA&gt;</RawActiveDataSourceState>
      <DataSourceState>state-1</DataSourceState>
      <TableState>Active</TableState>
      <MemberType>DATA</MemberType>
      <ShortCutList>
        <ShortCutID>shortcut-001</ShortCutID>
        <ShortCutID>shortcut-002</ShortCutID>
      </ShortCutList>
    </Data>
  </DataList>
</ProjectCollection>
"""

MINIMAL_DATA_XML = """\
<ProjectCollection>
  <DataList>
    <Data>
      <Element ID="data-minimal" />
      <Table>SIMPLE</Table>
    </Data>
  </DataList>
</ProjectCollection>
"""

NO_DATA_LIST_XML = """\
<ProjectCollection>
  <Elements />
</ProjectCollection>
"""

EMPTY_RAW_STATE_XML = """\
<ProjectCollection>
  <DataList>
    <Data>
      <Element ID="data-empty-state" />
      <RawActiveDataSourceState></RawActiveDataSourceState>
    </Data>
  </DataList>
</ProjectCollection>
"""

ABSENT_RAW_STATE_XML = """\
<ProjectCollection>
  <DataList>
    <Data>
      <Element ID="data-no-state" />
      <Table>NOTAB</Table>
    </Data>
  </DataList>
</ProjectCollection>
"""

MULTIPLE_DATA_XML = """\
<ProjectCollection>
  <DataList>
    <Data>
      <Element ID="data-A" Label="First" />
      <Table>TABLE_A</Table>
    </Data>
    <Data>
      <Element ID="data-B" Label="Second" />
      <Table>TABLE_B</Table>
    </Data>
    <Data>
      <Element ID="data-C" Label="Third" />
      <Table>TABLE_C</Table>
    </Data>
  </DataList>
</ProjectCollection>
"""

NO_ELEMENT_CHILD_XML = """\
<ProjectCollection>
  <DataList>
    <Data>
      <Server>SASApp</Server>
      <Table>ORPHAN</Table>
    </Data>
  </DataList>
</ProjectCollection>
"""

HAS_SERIALIZATION_ERROR_TRUE_XML = """\
<ProjectCollection>
  <DataList>
    <Data>
      <Element ID="data-err" HasSerializationError="True" />
    </Data>
  </DataList>
</ProjectCollection>
"""

NO_SHORTCUT_LIST_XML = """\
<ProjectCollection>
  <DataList>
    <Data>
      <Element ID="data-no-shortcuts" />
      <Table>T1</Table>
    </Data>
  </DataList>
</ProjectCollection>
"""

EMPTY_SHORTCUT_LIST_XML = """\
<ProjectCollection>
  <DataList>
    <Data>
      <Element ID="data-empty-shortcuts" />
      <ShortCutList />
    </Data>
  </DataList>
</ProjectCollection>
"""


# --- Tests ---


class TestParseDataListFullExtraction:
    """Test full extraction of a complete Data item with all fields."""

    def test_extracts_element_metadata(self):
        root = ET.fromstring(FULL_DATA_LIST_XML)
        items = parse_data_list(root)

        assert len(items) == 1
        elem = items[0].element
        assert elem.label == "WORK.MYDATA"
        assert elem.type == "SAS.EG.ProjectElements.DataSet"
        assert elem.id == "data-001"
        assert elem.container == "container-1"
        assert elem.created_on == "2023-01-01T00:00:00"
        assert elem.modified_on == "2023-06-01T12:00:00"
        assert elem.modified_by == "admin"
        assert elem.modified_by_eg_id == "EG01"
        assert elem.modified_by_eg_ver == "8.1"
        assert elem.has_serialization_error is False

    def test_extracts_input_ids(self):
        root = ET.fromstring(FULL_DATA_LIST_XML)
        items = parse_data_list(root)

        assert items[0].element.input_ids == ["input-1", "input-2"]

    def test_extracts_data_model_fields(self):
        root = ET.fromstring(FULL_DATA_LIST_XML)
        items = parse_data_list(root)

        model = items[0].data_model
        assert model.server == "SASApp"
        assert model.active_data_source == "ds-ref"
        assert model.display_name == "WORK.MYDATA"
        assert model.table == "MYDATA"
        assert model.data_source_state == "state-1"
        assert model.table_state == "Active"
        assert model.member_type == "DATA"

    def test_decodes_dna_from_raw_state(self):
        root = ET.fromstring(FULL_DATA_LIST_XML)
        items = parse_data_list(root)

        model = items[0].data_model
        assert model.raw_active_data_source_state is not None
        assert model.decoded_dna is not None
        assert isinstance(model.decoded_dna, DNADescriptor)
        assert model.decoded_dna.type == "SAS.Servers.ServerDef"
        assert model.decoded_dna.name == "SASApp"
        assert model.decoded_dna.version == "1.0"

    def test_extracts_shortcut_list(self):
        root = ET.fromstring(FULL_DATA_LIST_XML)
        items = parse_data_list(root)

        assert items[0].shortcut_list == ["shortcut-001", "shortcut-002"]


class TestParseDataListAbsentSections:
    """Test handling of absent or empty sections."""

    def test_absent_data_list_returns_empty(self):
        root = ET.fromstring(NO_DATA_LIST_XML)
        items = parse_data_list(root)

        assert items == []

    def test_empty_raw_state_sets_dna_to_none(self):
        root = ET.fromstring(EMPTY_RAW_STATE_XML)
        items = parse_data_list(root)

        assert len(items) == 1
        assert items[0].data_model.decoded_dna is None

    def test_absent_raw_state_sets_dna_to_none(self):
        root = ET.fromstring(ABSENT_RAW_STATE_XML)
        items = parse_data_list(root)

        assert len(items) == 1
        assert items[0].data_model.decoded_dna is None
        assert items[0].data_model.raw_active_data_source_state is None

    def test_absent_shortcut_list_returns_empty(self):
        root = ET.fromstring(NO_SHORTCUT_LIST_XML)
        items = parse_data_list(root)

        assert items[0].shortcut_list == []

    def test_empty_shortcut_list_returns_empty(self):
        root = ET.fromstring(EMPTY_SHORTCUT_LIST_XML)
        items = parse_data_list(root)

        assert items[0].shortcut_list == []


class TestParseDataListMultipleItems:
    """Test extraction of multiple Data items."""

    def test_extracts_all_items(self):
        root = ET.fromstring(MULTIPLE_DATA_XML)
        items = parse_data_list(root)

        assert len(items) == 3

    def test_preserves_order(self):
        root = ET.fromstring(MULTIPLE_DATA_XML)
        items = parse_data_list(root)

        assert items[0].element.id == "data-A"
        assert items[0].element.label == "First"
        assert items[1].element.id == "data-B"
        assert items[1].element.label == "Second"
        assert items[2].element.id == "data-C"
        assert items[2].element.label == "Third"

    def test_extracts_table_for_each(self):
        root = ET.fromstring(MULTIPLE_DATA_XML)
        items = parse_data_list(root)

        assert items[0].data_model.table == "TABLE_A"
        assert items[1].data_model.table == "TABLE_B"
        assert items[2].data_model.table == "TABLE_C"


class TestParseDataListAbsentFields:
    """Test that absent metadata fields default to None (requirement 3.7)."""

    def test_minimal_data_item(self):
        root = ET.fromstring(MINIMAL_DATA_XML)
        items = parse_data_list(root)

        assert len(items) == 1
        elem = items[0].element
        assert elem.id == "data-minimal"
        assert elem.label is None
        assert elem.type is None
        assert elem.container is None
        assert elem.created_on is None
        assert elem.modified_on is None
        assert elem.modified_by is None
        assert elem.modified_by_eg_id is None
        assert elem.modified_by_eg_ver is None
        assert elem.has_serialization_error is None
        assert elem.input_ids == []

    def test_absent_data_model_fields(self):
        root = ET.fromstring(MINIMAL_DATA_XML)
        items = parse_data_list(root)

        model = items[0].data_model
        assert model.server is None
        assert model.active_data_source is None
        assert model.display_name is None
        assert model.table == "SIMPLE"
        assert model.raw_active_data_source_state is None
        assert model.data_source_state is None
        assert model.table_state is None
        assert model.member_type is None
        assert model.decoded_dna is None

    def test_no_element_child_returns_empty_metadata(self):
        root = ET.fromstring(NO_ELEMENT_CHILD_XML)
        items = parse_data_list(root)

        assert len(items) == 1
        elem = items[0].element
        assert elem.id is None
        assert elem.label is None
        assert items[0].data_model.table == "ORPHAN"


class TestParseDataListHasSerializationError:
    """Test HasSerializationError boolean attribute parsing."""

    def test_false_value(self):
        root = ET.fromstring(FULL_DATA_LIST_XML)
        items = parse_data_list(root)

        assert items[0].element.has_serialization_error is False

    def test_true_value(self):
        root = ET.fromstring(HAS_SERIALIZATION_ERROR_TRUE_XML)
        items = parse_data_list(root)

        assert items[0].element.has_serialization_error is True

    def test_absent_value(self):
        root = ET.fromstring(MINIMAL_DATA_XML)
        items = parse_data_list(root)

        assert items[0].element.has_serialization_error is None
