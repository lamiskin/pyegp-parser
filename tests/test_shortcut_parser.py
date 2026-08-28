"""Tests for shortcut element parsing (ShortCutToData and ShortCutToFile)."""

import xml.etree.ElementTree as ET

import pytest

from pyegp_parser.models.base import ElementMetadata
from pyegp_parser.models.shortcut import ShortCutToData, ShortCutToFile
from pyegp_parser.parsers.shortcut_parser import parse_shortcut

# --- Helper to build XML elements ---


def _make_shortcut_xml(
    element_type: str = "SAS.EG.ProjectElements.ShortCutToData",
    label: str = "WORK.MYDATA",
    element_id: str = "sc-001",
    container: str = "pf-001",
    parent_id: str | None = "data-001",
    input_ids: list[str] | None = None,
    include_inputlist: bool = True,
    include_shortcut_section: bool = True,
    user_has_explicitly_set_label: str | None = None,
) -> ET.Element:
    """Build an XML Element node simulating a ShortCut element."""
    attribs = {
        "Type": element_type,
        "Label": label,
        "ID": element_id,
        "Container": container,
    }
    element_node = ET.Element("Element", attribs)

    if include_shortcut_section:
        shortcut = ET.SubElement(element_node, "SHORTCUT")

        if parent_id is not None:
            parent_elem = ET.SubElement(shortcut, "Parent")
            parent_elem.text = parent_id

        if include_inputlist:
            input_list_elem = ET.SubElement(shortcut, "INPUTLIST")
            ids_to_add = input_ids if input_ids is not None else ["input-a", "input-b"]
            for iid in ids_to_add:
                input_id_elem = ET.SubElement(input_list_elem, "INPUTID")
                input_id_elem.text = iid

        if user_has_explicitly_set_label is not None:
            label_elem = ET.SubElement(shortcut, "UserHasExplicitlySetLabel")
            label_elem.text = user_has_explicitly_set_label

    return element_node


def _make_metadata(
    element_id: str = "sc-001", label: str = "WORK.MYDATA"
) -> ElementMetadata:
    """Create a simple ElementMetadata for testing."""
    return ElementMetadata(
        label=label,
        type="SAS.EG.ProjectElements.ShortCutToData",
        container="pf-001",
        id=element_id,
    )


# --- ShortCutToData Tests ---


class TestShortCutToDataParsing:
    """Tests for ShortCutToData element parsing."""

    def test_basic_shortcut_to_data(self):
        """Parse a complete ShortCutToData element with all required fields."""
        xml_node = _make_shortcut_xml()
        metadata = _make_metadata()

        result = parse_shortcut(xml_node, metadata, is_data=True)

        assert isinstance(result, ShortCutToData)
        assert result.metadata == metadata
        assert result.parent_id == "data-001"
        assert result.input_list == ["input-a", "input-b"]
        assert result.user_has_explicitly_set_label is None

    def test_shortcut_to_data_with_explicit_label_false(self):
        """UserHasExplicitlySetLabel = False is parsed as bool."""
        xml_node = _make_shortcut_xml(user_has_explicitly_set_label="False")
        metadata = _make_metadata()

        result = parse_shortcut(xml_node, metadata, is_data=True)

        assert result.user_has_explicitly_set_label is False

    def test_shortcut_to_data_with_explicit_label_true(self):
        """UserHasExplicitlySetLabel = True is parsed as bool."""
        xml_node = _make_shortcut_xml(user_has_explicitly_set_label="True")
        metadata = _make_metadata()

        result = parse_shortcut(xml_node, metadata, is_data=True)

        assert result.user_has_explicitly_set_label is True

    def test_shortcut_to_data_empty_input_list(self):
        """INPUTLIST with no INPUTID entries results in an empty list."""
        xml_node = _make_shortcut_xml(input_ids=[])
        metadata = _make_metadata()

        result = parse_shortcut(xml_node, metadata, is_data=True)

        assert result.input_list == []

    def test_shortcut_to_data_multiple_inputs(self):
        """INPUTLIST with multiple entries is fully captured."""
        inputs = ["id-1", "id-2", "id-3", "id-4"]
        xml_node = _make_shortcut_xml(input_ids=inputs)
        metadata = _make_metadata()

        result = parse_shortcut(xml_node, metadata, is_data=True)

        assert result.input_list == inputs

    def test_missing_shortcut_section_raises_value_error(self):
        """Missing SHORTCUT section raises ValueError."""
        xml_node = _make_shortcut_xml(include_shortcut_section=False)
        metadata = _make_metadata()

        with pytest.raises(ValueError, match="missing the SHORTCUT section"):
            parse_shortcut(xml_node, metadata, is_data=True)

    def test_missing_parent_raises_value_error(self):
        """Missing Parent reference raises ValueError."""
        xml_node = _make_shortcut_xml(parent_id=None)
        metadata = _make_metadata()

        with pytest.raises(ValueError, match="missing the Parent reference"):
            parse_shortcut(xml_node, metadata, is_data=True)

    def test_empty_parent_text_raises_value_error(self):
        """Empty Parent text raises ValueError."""
        xml_node = _make_shortcut_xml()
        # Manually set Parent text to empty
        shortcut = xml_node.find("SHORTCUT")
        parent = shortcut.find("Parent")
        parent.text = "   "
        metadata = _make_metadata()

        with pytest.raises(ValueError, match="missing the Parent reference"):
            parse_shortcut(xml_node, metadata, is_data=True)

    def test_missing_inputlist_raises_value_error(self):
        """Missing INPUTLIST raises ValueError."""
        xml_node = _make_shortcut_xml(include_inputlist=False)
        metadata = _make_metadata()

        with pytest.raises(ValueError, match="missing the INPUTLIST"):
            parse_shortcut(xml_node, metadata, is_data=True)


# --- ShortCutToFile Tests ---


class TestShortCutToFileParsing:
    """Tests for ShortCutToFile element parsing."""

    def test_basic_shortcut_to_file(self):
        """Parse a complete ShortCutToFile element with all required fields."""
        xml_node = _make_shortcut_xml(
            element_type="SAS.EG.ProjectElements.ShortCutToFile",
            label="MyFile.csv",
            element_id="scf-001",
            parent_id="file-001",
            input_ids=["input-x"],
        )
        metadata = ElementMetadata(
            label="MyFile.csv",
            type="SAS.EG.ProjectElements.ShortCutToFile",
            container="pf-001",
            id="scf-001",
        )

        result = parse_shortcut(xml_node, metadata, is_data=False)

        assert isinstance(result, ShortCutToFile)
        assert result.metadata == metadata
        assert result.parent_id == "file-001"
        assert result.input_list == ["input-x"]
        assert result.user_has_explicitly_set_label is None

    def test_shortcut_to_file_with_explicit_label_false(self):
        """UserHasExplicitlySetLabel = False parsed correctly for file shortcut."""
        xml_node = _make_shortcut_xml(
            element_type="SAS.EG.ProjectElements.ShortCutToFile",
            parent_id="file-002",
            user_has_explicitly_set_label="False",
        )
        metadata = ElementMetadata(id="sc-001")

        result = parse_shortcut(xml_node, metadata, is_data=False)

        assert isinstance(result, ShortCutToFile)
        assert result.user_has_explicitly_set_label is False

    def test_shortcut_to_file_with_explicit_label_true(self):
        """UserHasExplicitlySetLabel = True parsed correctly for file shortcut."""
        xml_node = _make_shortcut_xml(
            element_type="SAS.EG.ProjectElements.ShortCutToFile",
            parent_id="file-003",
            user_has_explicitly_set_label="True",
        )
        metadata = ElementMetadata(id="sc-001")

        result = parse_shortcut(xml_node, metadata, is_data=False)

        assert isinstance(result, ShortCutToFile)
        assert result.user_has_explicitly_set_label is True

    def test_shortcut_to_file_missing_shortcut_section(self):
        """Missing SHORTCUT section for file shortcut raises ValueError."""
        xml_node = _make_shortcut_xml(
            element_type="SAS.EG.ProjectElements.ShortCutToFile",
            include_shortcut_section=False,
        )
        metadata = ElementMetadata(id="scf-001")

        with pytest.raises(
            ValueError, match="ShortCutToFile.*missing the SHORTCUT section"
        ):
            parse_shortcut(xml_node, metadata, is_data=False)

    def test_shortcut_to_file_missing_parent(self):
        """Missing Parent for file shortcut raises ValueError."""
        xml_node = _make_shortcut_xml(
            element_type="SAS.EG.ProjectElements.ShortCutToFile",
            parent_id=None,
        )
        metadata = ElementMetadata(id="scf-001")

        with pytest.raises(
            ValueError, match="ShortCutToFile.*missing the Parent reference"
        ):
            parse_shortcut(xml_node, metadata, is_data=False)

    def test_shortcut_to_file_missing_inputlist(self):
        """Missing INPUTLIST for file shortcut raises ValueError."""
        xml_node = _make_shortcut_xml(
            element_type="SAS.EG.ProjectElements.ShortCutToFile",
            include_inputlist=False,
        )
        metadata = ElementMetadata(id="scf-001")

        with pytest.raises(ValueError, match="ShortCutToFile.*missing the INPUTLIST"):
            parse_shortcut(xml_node, metadata, is_data=False)


# --- Edge Case Tests ---


class TestShortCutEdgeCases:
    """Edge case tests for shortcut parsing."""

    def test_whitespace_in_parent_id_is_trimmed(self):
        """Parent text with leading/trailing whitespace is trimmed."""
        xml_node = _make_shortcut_xml(parent_id="  data-123  ")
        metadata = _make_metadata()

        result = parse_shortcut(xml_node, metadata, is_data=True)

        assert result.parent_id == "data-123"

    def test_whitespace_in_input_ids_is_trimmed(self):
        """INPUTID text with whitespace is trimmed."""
        xml_node = _make_shortcut_xml(input_ids=["  id-1  ", " id-2 "])
        metadata = _make_metadata()

        result = parse_shortcut(xml_node, metadata, is_data=True)

        assert result.input_list == ["id-1", "id-2"]

    def test_empty_inputid_entries_are_skipped(self):
        """INPUTID entries with empty/whitespace-only text are skipped."""
        xml_node = _make_shortcut_xml(input_ids=["valid-id"])
        # Add an empty INPUTID entry
        input_list_elem = xml_node.find("SHORTCUT/INPUTLIST")
        empty_id = ET.SubElement(input_list_elem, "INPUTID")
        empty_id.text = "   "
        metadata = _make_metadata()

        result = parse_shortcut(xml_node, metadata, is_data=True)

        assert result.input_list == ["valid-id"]

    def test_error_message_includes_element_id(self):
        """ValueError messages include the element ID for debugging."""
        xml_node = _make_shortcut_xml(include_shortcut_section=False)
        metadata = ElementMetadata(id="my-special-id")

        with pytest.raises(ValueError, match="my-special-id"):
            parse_shortcut(xml_node, metadata, is_data=True)

    def test_unknown_element_id_in_error(self):
        """When metadata has no ID, error uses 'unknown'."""
        xml_node = _make_shortcut_xml(include_shortcut_section=False)
        metadata = ElementMetadata(id=None)

        with pytest.raises(ValueError, match="unknown"):
            parse_shortcut(xml_node, metadata, is_data=True)
