"""Unit tests for the element parser.

Tests cover:
- Full extraction of Elements collection with all metadata fields
- Absent Elements section returns empty list
- Document order preservation across multiple elements
- Type classification for all known categories
- Unknown type classification preserves original_type
- Absent metadata fields default to None
- InputIDs extraction from child nodes
- HasSerializationError boolean parsing
- Empty type string classifies as Unknown
- Elements with no Type attribute classify as Unknown
"""

import xml.etree.ElementTree as ET

from pyegp_parser.models.elements import ElementCategory
from pyegp_parser.parsers.element_parser import parse_elements

# --- Fixtures ---


FULL_ELEMENTS_XML = """\
<ProjectCollection>
  <Elements>
    <Element Type="SAS.EG.ProjectElements.ProcessFlowContainer"
             Label="Process Flow"
             ID="pf-001"
             Container=""
             CreatedOn="2023-01-15T10:30:00"
             ModifiedOn="2023-06-20T14:45:00"
             ModifiedBy="jsmith"
             ModifiedByEGID="EG001"
             ModifiedByEGVer="8.1"
             HasSerializationError="False">
      <InputIDs>
        <ID>input-1</ID>
        <ID>input-2</ID>
      </InputIDs>
    </Element>
  </Elements>
</ProjectCollection>
"""

MULTIPLE_ELEMENTS_XML = """\
<ProjectCollection>
  <Elements>
    <Element Type="SAS.EG.ProjectElements.ProcessFlowContainer"
             Label="Main Flow" ID="pf-001" />
    <Element Type="SAS.EG.ProjectElements.Query"
             Label="My Query" ID="q-001" Container="pf-001" />
    <Element Type="SAS.EG.ProjectElements.CodeTask"
             Label="Code Task 1" ID="ct-001" Container="pf-001" />
    <Element Type="SAS.EG.ProjectElements.Log"
             Label="Log for Code Task 1" ID="log-001" Container="pf-001" />
    <Element Type="SAS.EG.ProjectElements.ShortCutToData"
             Label="Data Shortcut" ID="sc-001" Container="pf-001" />
  </Elements>
</ProjectCollection>
"""

ALL_KNOWN_TYPES_XML = """\
<ProjectCollection>
  <Elements>
    <Element Type="SAS.EG.ProjectElements.ProcessFlowContainer" ID="t1" />
    <Element Type="SAS.EG.ProjectElements.ShortCutToFile" ID="t2" />
    <Element Type="SAS.EG.ProjectElements.ShortCutToData" ID="t3" />
    <Element Type="SAS.EG.ProjectElements.Query" ID="t4" />
    <Element Type="SAS.EG.ProjectElements.ImportTask" ID="t5" />
    <Element Type="SAS.EG.ProjectElements.ExportTask" ID="t6" />
    <Element Type="SAS.EG.ProjectElements.CodeTask" ID="t7" />
    <Element Type="SAS.EG.ProjectElements.EGTask" ID="t8" />
    <Element Type="SAS.EG.ProjectElements.AppendTask" ID="t9" />
    <Element Type="SAS.EG.ProjectElements.Log" ID="t10" />
    <Element Type="SAS.EG.ProjectElements.Code" ID="t11" />
    <Element Type="SAS.EG.ProjectElements.ProjectLog" ID="t12" />
  </Elements>
</ProjectCollection>
"""

UNKNOWN_TYPE_XML = """\
<ProjectCollection>
  <Elements>
    <Element Type="SAS.EG.ProjectElements.CustomWidget" ID="unk-001" Label="Custom" />
    <Element Type="com.vendor.SpecialElement" ID="unk-002" Label="Vendor" />
  </Elements>
</ProjectCollection>
"""

NO_ELEMENTS_SECTION_XML = """\
<ProjectCollection>
  <DataList />
</ProjectCollection>
"""

EMPTY_ELEMENTS_SECTION_XML = """\
<ProjectCollection>
  <Elements />
</ProjectCollection>
"""

MINIMAL_ELEMENT_XML = """\
<ProjectCollection>
  <Elements>
    <Element ID="min-001" />
  </Elements>
</ProjectCollection>
"""

NO_TYPE_ATTRIBUTE_XML = """\
<ProjectCollection>
  <Elements>
    <Element ID="no-type-001" Label="No Type" />
  </Elements>
</ProjectCollection>
"""

HAS_SERIALIZATION_ERROR_XML = """\
<ProjectCollection>
  <Elements>
    <Element Type="SAS.EG.ProjectElements.Query" ID="err-001" HasSerializationError="True" />
    <Element Type="SAS.EG.ProjectElements.Query" ID="err-002" HasSerializationError="False" />
    <Element Type="SAS.EG.ProjectElements.Query" ID="err-003" />
  </Elements>
</ProjectCollection>
"""

INPUT_IDS_XML = """\
<ProjectCollection>
  <Elements>
    <Element Type="SAS.EG.ProjectElements.CodeTask" ID="ct-ids" Label="With Inputs">
      <InputIDs>
        <ID>dep-001</ID>
        <ID>dep-002</ID>
        <ID>dep-003</ID>
      </InputIDs>
    </Element>
    <Element Type="SAS.EG.ProjectElements.CodeTask" ID="ct-no-ids" Label="No Inputs" />
  </Elements>
</ProjectCollection>
"""

EMPTY_INPUT_IDS_XML = """\
<ProjectCollection>
  <Elements>
    <Element Type="SAS.EG.ProjectElements.Query" ID="q-empty-ids">
      <InputIDs />
    </Element>
  </Elements>
</ProjectCollection>
"""


# --- Tests ---


class TestParseElementsFullExtraction:
    """Test full extraction of a complete element with all metadata fields."""

    def test_extracts_all_metadata_fields(self):
        root = ET.fromstring(FULL_ELEMENTS_XML)
        elements = parse_elements(root)

        assert len(elements) == 1
        elem = elements[0]
        assert elem.metadata.label == "Process Flow"
        assert elem.metadata.type == "SAS.EG.ProjectElements.ProcessFlowContainer"
        assert elem.metadata.id == "pf-001"
        assert elem.metadata.container == ""
        assert elem.metadata.created_on == "2023-01-15T10:30:00"
        assert elem.metadata.modified_on == "2023-06-20T14:45:00"
        assert elem.metadata.modified_by == "jsmith"
        assert elem.metadata.modified_by_eg_id == "EG001"
        assert elem.metadata.modified_by_eg_ver == "8.1"
        assert elem.metadata.has_serialization_error is False

    def test_extracts_input_ids(self):
        root = ET.fromstring(FULL_ELEMENTS_XML)
        elements = parse_elements(root)

        assert elements[0].metadata.input_ids == ["input-1", "input-2"]

    def test_classifies_as_process_flow_container(self):
        root = ET.fromstring(FULL_ELEMENTS_XML)
        elements = parse_elements(root)

        assert elements[0].category == ElementCategory.PROCESS_FLOW_CONTAINER

    def test_preserves_xml_node_reference(self):
        root = ET.fromstring(FULL_ELEMENTS_XML)
        elements = parse_elements(root)

        assert elements[0].xml_node is not None
        assert elements[0].xml_node.get("ID") == "pf-001"

    def test_original_type_is_none_for_known_categories(self):
        root = ET.fromstring(FULL_ELEMENTS_XML)
        elements = parse_elements(root)

        assert elements[0].original_type is None


class TestParseElementsDocumentOrder:
    """Test that document order is preserved (requirement 5.6)."""

    def test_preserves_document_order(self):
        root = ET.fromstring(MULTIPLE_ELEMENTS_XML)
        elements = parse_elements(root)

        assert len(elements) == 5
        assert elements[0].metadata.id == "pf-001"
        assert elements[1].metadata.id == "q-001"
        assert elements[2].metadata.id == "ct-001"
        assert elements[3].metadata.id == "log-001"
        assert elements[4].metadata.id == "sc-001"

    def test_labels_preserved_in_order(self):
        root = ET.fromstring(MULTIPLE_ELEMENTS_XML)
        elements = parse_elements(root)

        labels = [e.metadata.label for e in elements]
        assert labels == [
            "Main Flow",
            "My Query",
            "Code Task 1",
            "Log for Code Task 1",
            "Data Shortcut",
        ]


class TestParseElementsClassification:
    """Test element type classification (requirements 5.4, 5.5)."""

    def test_all_known_types_classified_correctly(self):
        root = ET.fromstring(ALL_KNOWN_TYPES_XML)
        elements = parse_elements(root)

        expected = [
            ("t1", ElementCategory.PROCESS_FLOW_CONTAINER),
            ("t2", ElementCategory.SHORTCUT_TO_FILE),
            ("t3", ElementCategory.SHORTCUT_TO_DATA),
            ("t4", ElementCategory.QUERY),
            ("t5", ElementCategory.IMPORT_TASK),
            ("t6", ElementCategory.EXPORT_TASK),
            ("t7", ElementCategory.CODE_TASK),
            ("t8", ElementCategory.EG_TASK),
            ("t9", ElementCategory.APPEND_TASK),
            ("t10", ElementCategory.LOG),
            ("t11", ElementCategory.CODE),
            ("t12", ElementCategory.PROJECT_LOG),
        ]

        assert len(elements) == len(expected)
        for elem, (expected_id, expected_category) in zip(elements, expected):
            assert elem.metadata.id == expected_id
            assert elem.category == expected_category
            assert elem.original_type is None

    def test_unknown_type_preserves_full_type_string(self):
        root = ET.fromstring(UNKNOWN_TYPE_XML)
        elements = parse_elements(root)

        assert len(elements) == 2
        assert elements[0].category == ElementCategory.UNKNOWN
        assert elements[0].original_type == "SAS.EG.ProjectElements.CustomWidget"
        assert elements[1].category == ElementCategory.UNKNOWN
        assert elements[1].original_type == "com.vendor.SpecialElement"

    def test_no_type_attribute_classifies_as_unknown(self):
        root = ET.fromstring(NO_TYPE_ATTRIBUTE_XML)
        elements = parse_elements(root)

        assert len(elements) == 1
        assert elements[0].category == ElementCategory.UNKNOWN
        # No type string means original_type should be None (empty string case)
        assert elements[0].original_type is None

    def test_multiple_types_in_mixed_flow(self):
        root = ET.fromstring(MULTIPLE_ELEMENTS_XML)
        elements = parse_elements(root)

        categories = [e.category for e in elements]
        assert categories == [
            ElementCategory.PROCESS_FLOW_CONTAINER,
            ElementCategory.QUERY,
            ElementCategory.CODE_TASK,
            ElementCategory.LOG,
            ElementCategory.SHORTCUT_TO_DATA,
        ]


class TestParseElementsAbsentSections:
    """Test handling of absent or empty Elements section."""

    def test_absent_elements_section_returns_empty_list(self):
        root = ET.fromstring(NO_ELEMENTS_SECTION_XML)
        elements = parse_elements(root)

        assert elements == []

    def test_empty_elements_section_returns_empty_list(self):
        root = ET.fromstring(EMPTY_ELEMENTS_SECTION_XML)
        elements = parse_elements(root)

        assert elements == []


class TestParseElementsAbsentFields:
    """Test that absent metadata fields default to None (requirement 5.3)."""

    def test_minimal_element_defaults_to_none(self):
        root = ET.fromstring(MINIMAL_ELEMENT_XML)
        elements = parse_elements(root)

        assert len(elements) == 1
        meta = elements[0].metadata
        assert meta.id == "min-001"
        assert meta.label is None
        assert meta.type is None
        assert meta.container is None
        assert meta.created_on is None
        assert meta.modified_on is None
        assert meta.modified_by is None
        assert meta.modified_by_eg_id is None
        assert meta.modified_by_eg_ver is None
        assert meta.has_serialization_error is None
        assert meta.input_ids == []


class TestParseElementsHasSerializationError:
    """Test HasSerializationError boolean attribute parsing."""

    def test_true_value(self):
        root = ET.fromstring(HAS_SERIALIZATION_ERROR_XML)
        elements = parse_elements(root)

        assert elements[0].metadata.has_serialization_error is True

    def test_false_value(self):
        root = ET.fromstring(HAS_SERIALIZATION_ERROR_XML)
        elements = parse_elements(root)

        assert elements[1].metadata.has_serialization_error is False

    def test_absent_value(self):
        root = ET.fromstring(HAS_SERIALIZATION_ERROR_XML)
        elements = parse_elements(root)

        assert elements[2].metadata.has_serialization_error is None


class TestParseElementsInputIDs:
    """Test InputIDs extraction from Element child nodes."""

    def test_extracts_multiple_input_ids(self):
        root = ET.fromstring(INPUT_IDS_XML)
        elements = parse_elements(root)

        assert elements[0].metadata.input_ids == ["dep-001", "dep-002", "dep-003"]

    def test_absent_input_ids_returns_empty_list(self):
        root = ET.fromstring(INPUT_IDS_XML)
        elements = parse_elements(root)

        assert elements[1].metadata.input_ids == []

    def test_empty_input_ids_element_returns_empty_list(self):
        root = ET.fromstring(EMPTY_INPUT_IDS_XML)
        elements = parse_elements(root)

        assert elements[0].metadata.input_ids == []
