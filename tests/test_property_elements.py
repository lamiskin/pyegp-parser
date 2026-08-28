"""Property-based tests for element classification and order preservation.

**Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6**

Uses Hypothesis to verify that:
- P1: Every element is assigned exactly one ElementCategory
- P2: Classification is deterministic (same Type string → same category every time)
- P3: Document order is preserved (output index matches input index)
- P4: All metadata fields that were present are correctly extracted
- P5: Absent metadata fields are None
- P6: Unknown types preserve original_type string
"""

import string
import xml.etree.ElementTree as ET

from hypothesis import given, settings
from hypothesis import strategies as st

from pyegp_parser.models.base import ElementMetadata
from pyegp_parser.models.elements import ElementCategory, classify_element_type
from pyegp_parser.parsers.element_parser import parse_elements

# ---------------------------------------------------------------------------
# Strategies for generating Element XML nodes
# ---------------------------------------------------------------------------

# Known final type segments that should map to recognized categories
_KNOWN_SEGMENTS = [
    "ProcessFlowContainer",
    "ShortCutToFile",
    "ShortCutToData",
    "Query",
    "ImportTask",
    "ExportTask",
    "CodeTask",
    "EGTask",
    "AppendTask",
    "Log",
    "Code",
    "ProjectLog",
]

# Strategy for a known type segment
_known_segment = st.sampled_from(_KNOWN_SEGMENTS)

# Strategy for random (unknown) type segments — avoid matching any known segment
_unknown_segment = st.text(
    alphabet=string.ascii_letters + string.digits + "_",
    min_size=1,
    max_size=30,
).filter(lambda s: s not in _KNOWN_SEGMENTS)

# Strategy for type segment (mix of known and unknown)
_type_segment = st.one_of(
    _known_segment,
    _unknown_segment,
)

# Strategy for prefix namespace segments (e.g. "SAS.EG.ProjectElements")
_prefix = st.one_of(
    st.just("SAS.EG.ProjectElements"),
    st.just("SAS.EG.Custom"),
    st.just("MyNamespace"),
    st.text(
        alphabet=string.ascii_letters + ".",
        min_size=1,
        max_size=40,
    ).filter(lambda s: not s.endswith(".")),
)

# Strategy for a full Type attribute string (prefix.FinalSegment)
_type_string = st.one_of(
    # Full qualified type with prefix
    st.builds(lambda p, s: f"{p}.{s}", _prefix, _type_segment),
    # Just the segment (no prefix)
    _type_segment,
    # Empty string (edge case)
    st.just(""),
)

# Strategy for an alphanumeric ID
_element_id = st.text(
    alphabet=string.ascii_letters + string.digits,
    min_size=1,
    max_size=20,
)

# Strategy for optional string fields (either a value or None via absence)
_optional_str = st.one_of(st.none(), st.text(min_size=1, max_size=50))

# Strategy for optional ISO timestamp-like strings
_optional_timestamp = st.one_of(
    st.none(),
    st.from_regex(
        r"20[0-9]{2}-[01][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-5][0-9]",
        fullmatch=True,
    ),
)

# Strategy for optional boolean
_optional_bool = st.one_of(st.none(), st.booleans())

# Strategy for InputIDs list
_input_ids_list = st.lists(
    _element_id,
    min_size=0,
    max_size=5,
)


@st.composite
def element_xml_attrs(draw):
    """Generate a dict of attributes for an Element XML node.

    Returns a tuple of (attributes_dict, expected_metadata) where:
    - attributes_dict maps attribute name -> value (only present attributes)
    - expected_metadata is the expected ElementMetadata after parsing
    """
    type_str = draw(_type_string)
    label = draw(_optional_str)
    container = draw(_optional_str)
    elem_id = draw(_element_id)
    created_on = draw(_optional_timestamp)
    modified_on = draw(_optional_timestamp)
    modified_by = draw(_optional_str)
    modified_by_eg_id = draw(_optional_str)
    modified_by_eg_ver = draw(_optional_str)
    has_serialization_error = draw(_optional_bool)
    input_ids = draw(_input_ids_list)

    # Build the XML attributes dict (only include non-None values)
    attrs = {}
    if type_str:
        attrs["Type"] = type_str
    if label is not None:
        attrs["Label"] = label
    if container is not None:
        attrs["Container"] = container
    attrs["ID"] = elem_id  # Always include ID
    if created_on is not None:
        attrs["CreatedOn"] = created_on
    if modified_on is not None:
        attrs["ModifiedOn"] = modified_on
    if modified_by is not None:
        attrs["ModifiedBy"] = modified_by
    if modified_by_eg_id is not None:
        attrs["ModifiedByEGID"] = modified_by_eg_id
    if modified_by_eg_ver is not None:
        attrs["ModifiedByEGVer"] = modified_by_eg_ver
    if has_serialization_error is not None:
        attrs["HasSerializationError"] = str(has_serialization_error).lower()

    # Build expected metadata
    expected = ElementMetadata(
        label=label,
        type=type_str if type_str else None,
        container=container,
        id=elem_id,
        created_on=created_on,
        modified_on=modified_on,
        modified_by=modified_by,
        modified_by_eg_id=modified_by_eg_id,
        modified_by_eg_ver=modified_by_eg_ver,
        has_serialization_error=has_serialization_error,
        input_ids=input_ids,
    )

    return attrs, input_ids, expected, type_str


def _build_element_xml(attrs: dict, input_ids: list[str]) -> ET.Element:
    """Build an Element XML node with given attributes and InputIDs."""
    elem = ET.Element("Element", attrib=attrs)
    if input_ids:
        ids_elem = ET.SubElement(elem, "InputIDs")
        for id_val in input_ids:
            id_node = ET.SubElement(ids_elem, "ID")
            id_node.text = id_val
    return elem


def _build_project_xml(element_nodes: list[ET.Element]) -> ET.Element:
    """Build a minimal project.xml root with Elements section."""
    root = ET.Element("ProjectCollection")
    elements_section = ET.SubElement(root, "Elements")
    for node in element_nodes:
        elements_section.append(node)
    return root


# ---------------------------------------------------------------------------
# Strategy for a sequence of elements
# ---------------------------------------------------------------------------


@st.composite
def element_sequence(draw):
    """Generate a sequence of Element XML data for property testing.

    Returns a list of (attrs, input_ids, expected_metadata, type_string) tuples.
    """
    n = draw(st.integers(min_value=1, max_value=20))
    items = []
    for _ in range(n):
        item = draw(element_xml_attrs())
        items.append(item)
    return items


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------


class TestElementClassificationAndOrderPreservation:
    """**Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6**"""

    @given(data=element_sequence())
    @settings(max_examples=300)
    def test_p1_every_element_assigned_exactly_one_category(self, data):
        """P1: Every element is assigned exactly one ElementCategory.

        No element should be left unclassified or assigned multiple categories.
        """
        element_nodes = [_build_element_xml(attrs, ids) for attrs, ids, _, _ in data]
        root = _build_project_xml(element_nodes)
        parsed = parse_elements(root)

        assert len(parsed) == len(data)
        for elem in parsed:
            assert isinstance(elem.category, ElementCategory), (
                f"Element got non-ElementCategory: {elem.category!r}"
            )
            # Must be exactly one of the enum values
            assert elem.category in ElementCategory, (
                f"Element category {elem.category} not in ElementCategory enum"
            )

    @given(type_str=_type_string)
    @settings(max_examples=500)
    def test_p2_classification_is_deterministic(self, type_str):
        """P2: Classification is deterministic — same Type string always gives
        the same category regardless of how many times it is classified.
        """
        result1 = classify_element_type(type_str)
        result2 = classify_element_type(type_str)
        result3 = classify_element_type(type_str)

        assert result1 == result2 == result3, (
            f"Non-deterministic classification for {type_str!r}: "
            f"{result1}, {result2}, {result3}"
        )

    @given(data=element_sequence())
    @settings(max_examples=300)
    def test_p3_document_order_preserved(self, data):
        """P3: Document order is preserved — output index matches input index.

        The parser must return elements in the same order they appear in the XML.
        """
        element_nodes = [_build_element_xml(attrs, ids) for attrs, ids, _, _ in data]
        root = _build_project_xml(element_nodes)
        parsed = parse_elements(root)

        assert len(parsed) == len(data), (
            f"Expected {len(data)} elements, got {len(parsed)}"
        )

        # Verify order by matching IDs
        for i, (attrs, _, expected, _) in enumerate(data):
            assert parsed[i].metadata.id == expected.id, (
                f"Element at index {i}: expected ID={expected.id!r}, "
                f"got {parsed[i].metadata.id!r}"
            )

    @given(data=element_sequence())
    @settings(max_examples=300)
    def test_p4_present_metadata_fields_correctly_extracted(self, data):
        """P4: All metadata fields that were present are correctly extracted.

        Every attribute set on the XML node must appear correctly in the
        parsed ElementMetadata.
        """
        element_nodes = [_build_element_xml(attrs, ids) for attrs, ids, _, _ in data]
        root = _build_project_xml(element_nodes)
        parsed = parse_elements(root)

        for i, (attrs, input_ids, expected, _) in enumerate(data):
            meta = parsed[i].metadata

            # Check each field that was explicitly set
            if "Label" in attrs:
                assert meta.label == attrs["Label"], f"Element {i}: label mismatch"
            if "Type" in attrs:
                assert meta.type == attrs["Type"], f"Element {i}: type mismatch"
            if "Container" in attrs:
                assert meta.container == attrs["Container"], (
                    f"Element {i}: container mismatch"
                )
            if "ID" in attrs:
                assert meta.id == attrs["ID"], f"Element {i}: id mismatch"
            if "CreatedOn" in attrs:
                assert meta.created_on == attrs["CreatedOn"], (
                    f"Element {i}: created_on mismatch"
                )
            if "ModifiedOn" in attrs:
                assert meta.modified_on == attrs["ModifiedOn"], (
                    f"Element {i}: modified_on mismatch"
                )
            if "ModifiedBy" in attrs:
                assert meta.modified_by == attrs["ModifiedBy"], (
                    f"Element {i}: modified_by mismatch"
                )
            if "ModifiedByEGID" in attrs:
                assert meta.modified_by_eg_id == attrs["ModifiedByEGID"], (
                    f"Element {i}: modified_by_eg_id mismatch"
                )
            if "ModifiedByEGVer" in attrs:
                assert meta.modified_by_eg_ver == attrs["ModifiedByEGVer"], (
                    f"Element {i}: modified_by_eg_ver mismatch"
                )
            if "HasSerializationError" in attrs:
                expected_bool = attrs["HasSerializationError"] == "true"
                assert meta.has_serialization_error == expected_bool, (
                    f"Element {i}: has_serialization_error mismatch"
                )

            # InputIDs must match exactly
            assert meta.input_ids == input_ids, (
                f"Element {i}: input_ids mismatch. "
                f"Expected {input_ids!r}, got {meta.input_ids!r}"
            )

    @given(data=element_sequence())
    @settings(max_examples=300)
    def test_p5_absent_metadata_fields_are_none(self, data):
        """P5: Absent metadata fields are None.

        Any attribute NOT set on the XML node must be None in the parsed output.
        """
        element_nodes = [_build_element_xml(attrs, ids) for attrs, ids, _, _ in data]
        root = _build_project_xml(element_nodes)
        parsed = parse_elements(root)

        for i, (attrs, input_ids, _, _) in enumerate(data):
            meta = parsed[i].metadata

            if "Label" not in attrs:
                assert meta.label is None, (
                    f"Element {i}: label should be None but got {meta.label!r}"
                )
            if "Type" not in attrs:
                assert meta.type is None, (
                    f"Element {i}: type should be None but got {meta.type!r}"
                )
            if "Container" not in attrs:
                assert meta.container is None, (
                    f"Element {i}: container should be None but got {meta.container!r}"
                )
            if "CreatedOn" not in attrs:
                assert meta.created_on is None, (
                    f"Element {i}: created_on should be None"
                )
            if "ModifiedOn" not in attrs:
                assert meta.modified_on is None, (
                    f"Element {i}: modified_on should be None"
                )
            if "ModifiedBy" not in attrs:
                assert meta.modified_by is None, (
                    f"Element {i}: modified_by should be None"
                )
            if "ModifiedByEGID" not in attrs:
                assert meta.modified_by_eg_id is None, (
                    f"Element {i}: modified_by_eg_id should be None"
                )
            if "ModifiedByEGVer" not in attrs:
                assert meta.modified_by_eg_ver is None, (
                    f"Element {i}: modified_by_eg_ver should be None"
                )
            if "HasSerializationError" not in attrs:
                assert meta.has_serialization_error is None, (
                    f"Element {i}: has_serialization_error should be None"
                )
            if not input_ids:
                assert meta.input_ids == [], (
                    f"Element {i}: input_ids should be empty list"
                )

    @given(data=element_sequence())
    @settings(max_examples=300)
    def test_p6_unknown_types_preserve_original_type(self, data):
        """P6: Unknown types preserve original_type string.

        When a type's final segment doesn't match any known category, the
        ParsedElement.original_type must contain the full Type string.
        For known types, original_type must be None.
        """
        element_nodes = [_build_element_xml(attrs, ids) for attrs, ids, _, _ in data]
        root = _build_project_xml(element_nodes)
        parsed = parse_elements(root)

        for i, (attrs, _, _, type_str) in enumerate(data):
            elem = parsed[i]
            category = classify_element_type(type_str)

            if category == ElementCategory.UNKNOWN and type_str:
                # Unknown elements must preserve the full type string
                assert elem.original_type == type_str, (
                    f"Element {i}: Unknown type should preserve original_type="
                    f"{type_str!r}, got {elem.original_type!r}"
                )
            else:
                # Known elements must have original_type=None
                assert elem.original_type is None, (
                    f"Element {i}: Known type should have original_type=None, "
                    f"got {elem.original_type!r}"
                )
