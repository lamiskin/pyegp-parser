"""Property-based tests for metadata extraction with optional fields.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7**

Uses Hypothesis to generate project XML documents where random subsets of
metadata attributes, project settings fields, and parameters are present.
Verifies that all present fields are extracted correctly and absent fields
are None.
"""

import xml.etree.ElementTree as ET

from hypothesis import given, settings
from hypothesis import strategies as st

from pyegp_parser.models.project import (
    Parameter,
)
from pyegp_parser.parsers.project_parser import parse_project_xml

# ---------------------------------------------------------------------------
# Strategies for generating optional field values
# ---------------------------------------------------------------------------

# Safe text that won't break XML attributes (no <, >, &, ", ')
_safe_xml_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N"),
        blacklist_characters="<>&\"'\x00\r\n",
    ),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip() != "")

# ISO 8601-like timestamp strings
_timestamp = st.builds(
    lambda y, m, d, h, mi, s: f"{y:04d}-{m:02d}-{d:02d}T{h:02d}:{mi:02d}:{s:02d}",
    st.integers(min_value=2000, max_value=2030),
    st.integers(min_value=1, max_value=12),
    st.integers(min_value=1, max_value=28),
    st.integers(min_value=0, max_value=23),
    st.integers(min_value=0, max_value=59),
    st.integers(min_value=0, max_value=59),
)

# Boolean values as strings (how they appear in EGP XML)
_bool_str = st.sampled_from(["True", "False"])

# Integer values as strings
_int_str = st.integers(min_value=0, max_value=10000).map(str)

# Project metadata attributes on the root ProjectCollection element
_ROOT_ATTRS = {
    "EGVersion": _safe_xml_text,
    "Type": _safe_xml_text,
}

# Project metadata attributes on the first Element
_ELEMENT_ATTRS = {
    "Label": _safe_xml_text,
    "ID": _safe_xml_text,
    "CreatedOn": _timestamp,
    "ModifiedOn": _timestamp,
    "ModifiedBy": _safe_xml_text,
    "ModifiedByEGID": _safe_xml_text,
    "ModifiedByEGVer": _safe_xml_text,
}

# ProjectSettings fields and their value strategies
_SETTINGS_FIELDS = {
    "UseRelativePaths": _bool_str,
    "SubmitToGrid": _bool_str,
    "QueueSubmitsForServer": _bool_str,
    "ActionOnError": _safe_xml_text,
    "ShowProjectLogWarningMessage": _bool_str,
    "RemoveOlderProjectLogItems": _bool_str,
    "ExportProjectLogThenClear": _bool_str,
    "ProjectLogExportFilename": _safe_xml_text,
    "ProjectLogExportLocation": _safe_xml_text,
    "ProjectLogMaxSize": _int_str,
    "ClearProjectLogOnExit": _bool_str,
}

# Mapping from XML setting names to Python dataclass field names
_SETTINGS_FIELD_MAP = {
    "UseRelativePaths": "use_relative_paths",
    "SubmitToGrid": "submit_to_grid",
    "QueueSubmitsForServer": "queue_submits_for_server",
    "ActionOnError": "action_on_error",
    "ShowProjectLogWarningMessage": "show_project_log_warning_message",
    "RemoveOlderProjectLogItems": "remove_older_project_log_items",
    "ExportProjectLogThenClear": "export_project_log_then_clear",
    "ProjectLogExportFilename": "project_log_export_filename",
    "ProjectLogExportLocation": "project_log_export_location",
    "ProjectLogMaxSize": "project_log_max_size",
    "ClearProjectLogOnExit": "clear_project_log_on_exit",
}

# Which settings fields are boolean vs string vs int
_BOOL_SETTINGS = {
    "UseRelativePaths",
    "SubmitToGrid",
    "QueueSubmitsForServer",
    "ShowProjectLogWarningMessage",
    "RemoveOlderProjectLogItems",
    "ExportProjectLogThenClear",
    "ClearProjectLogOnExit",
}
_INT_SETTINGS = {"ProjectLogMaxSize"}
_STR_SETTINGS = {
    "ActionOnError",
    "ProjectLogExportFilename",
    "ProjectLogExportLocation",
}


# ---------------------------------------------------------------------------
# Strategy: generate a random subset of fields from a dict of strategies
# ---------------------------------------------------------------------------


@st.composite
def _random_subset_fields(draw, field_strategies: dict[str, st.SearchStrategy]):
    """Draw a random subset of fields with generated values."""
    # Choose which fields to include (at least 0, up to all)
    available_keys = list(field_strategies.keys())
    included_keys = draw(
        st.lists(
            st.sampled_from(available_keys), unique=True, max_size=len(available_keys)
        )
    )
    result = {}
    for key in included_keys:
        result[key] = draw(field_strategies[key])
    return result


@st.composite
def _random_parameters(draw):
    """Generate a random list of Parameter entries (name/value pairs)."""
    count = draw(st.integers(min_value=0, max_value=5))
    params = []
    for _ in range(count):
        name = draw(_safe_xml_text)
        value = draw(_safe_xml_text)
        params.append((name, value))
    return params


@st.composite
def _project_xml_strategy(draw):
    """Generate a full project XML string with random subsets of fields.

    Returns a tuple of:
    - xml_string: The generated XML content
    - root_attrs: Dict of attributes included on ProjectCollection
    - element_attrs: Dict of attributes included on the first Element
    - settings_fields: Dict of settings field names -> values included
    - parameters: List of (name, value) tuples for Parameter entries
    """
    root_attrs = draw(_random_subset_fields(_ROOT_ATTRS))
    element_attrs = draw(_random_subset_fields(_ELEMENT_ATTRS))
    settings_fields = draw(_random_subset_fields(_SETTINGS_FIELDS))
    parameters = draw(_random_parameters())

    # Build the XML
    root = ET.Element("ProjectCollection")
    for attr_name, attr_value in root_attrs.items():
        root.set(attr_name, attr_value)

    # Elements section with one Element node
    elements_section = ET.SubElement(root, "Elements")
    element_node = ET.SubElement(elements_section, "Element")
    for attr_name, attr_value in element_attrs.items():
        element_node.set(attr_name, attr_value)

    # ProjectSettings section
    if settings_fields:
        settings_section = ET.SubElement(root, "ProjectSettings")
        for field_name, field_value in settings_fields.items():
            child = ET.SubElement(settings_section, field_name)
            child.text = field_value

    # Parameters section
    if parameters:
        params_section = ET.SubElement(root, "Parameters")
        for name, value in parameters:
            param_elem = ET.SubElement(params_section, "Parameter")
            param_elem.set("Name", name)
            param_elem.set("Value", value)

    xml_string = ET.tostring(root, encoding="unicode", xml_declaration=False)
    return xml_string, root_attrs, element_attrs, settings_fields, parameters


# ---------------------------------------------------------------------------
# Property 2: Metadata Extraction with Optional Fields
# ---------------------------------------------------------------------------


class TestMetadataExtractionWithOptionalFields:
    """**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7**"""

    @given(data=_project_xml_strategy())
    @settings(max_examples=500)
    def test_present_fields_extracted_correctly(self, data):
        """All present fields in the generated XML are extracted with correct values."""
        xml_string, root_attrs, element_attrs, settings_fields, parameters = data

        result = parse_project_xml(xml_string)

        # --- Requirement 2.1: EGVersion and Type from root ---
        metadata = result.metadata
        assert metadata is not None

        if "EGVersion" in root_attrs:
            assert metadata.eg_version == root_attrs["EGVersion"]
        if "Type" in root_attrs:
            assert metadata.type == root_attrs["Type"]

        # --- Requirement 2.2: Element metadata ---
        if "Label" in element_attrs:
            assert metadata.label == element_attrs["Label"]
        if "ID" in element_attrs:
            assert metadata.id == element_attrs["ID"]
        if "CreatedOn" in element_attrs:
            assert metadata.created_on == element_attrs["CreatedOn"]
        if "ModifiedOn" in element_attrs:
            assert metadata.modified_on == element_attrs["ModifiedOn"]
        if "ModifiedBy" in element_attrs:
            assert metadata.modified_by == element_attrs["ModifiedBy"]
        if "ModifiedByEGID" in element_attrs:
            assert metadata.modified_by_eg_id == element_attrs["ModifiedByEGID"]
        if "ModifiedByEGVer" in element_attrs:
            assert metadata.modified_by_eg_ver == element_attrs["ModifiedByEGVer"]

        # --- Requirement 2.5: Project settings ---
        settings = result.settings
        assert settings is not None

        for xml_name, xml_value in settings_fields.items():
            py_field = _SETTINGS_FIELD_MAP[xml_name]
            actual = getattr(settings, py_field)

            if xml_name in _BOOL_SETTINGS:
                expected = xml_value.lower() == "true"
                assert actual == expected, (
                    f"Settings field {py_field}: expected {expected}, got {actual}"
                )
            elif xml_name in _INT_SETTINGS:
                expected = int(xml_value)
                assert actual == expected, (
                    f"Settings field {py_field}: expected {expected}, got {actual}"
                )
            else:
                assert actual == xml_value, (
                    f"Settings field {py_field}: expected {xml_value!r}, got {actual!r}"
                )

        # --- Requirement 2.6: Parameters ---
        assert len(result.parameters) == len(parameters)
        for i, (expected_name, expected_value) in enumerate(parameters):
            param = result.parameters[i]
            assert isinstance(param, Parameter)
            assert param.name == expected_name
            assert param.value == expected_value

    @given(data=_project_xml_strategy())
    @settings(max_examples=500)
    def test_absent_fields_are_none(self, data):
        """All absent fields in the generated XML are None (never a default string).

        **Validates: Requirement 2.7**
        """
        xml_string, root_attrs, element_attrs, settings_fields, parameters = data

        result = parse_project_xml(xml_string)
        metadata = result.metadata
        assert metadata is not None

        # Root attributes that are absent must be None
        if "EGVersion" not in root_attrs:
            assert metadata.eg_version is None
        if "Type" not in root_attrs:
            assert metadata.type is None

        # Element attributes that are absent must be None
        if "Label" not in element_attrs:
            assert metadata.label is None
        if "ID" not in element_attrs:
            assert metadata.id is None
        if "CreatedOn" not in element_attrs:
            assert metadata.created_on is None
        if "ModifiedOn" not in element_attrs:
            assert metadata.modified_on is None
        if "ModifiedBy" not in element_attrs:
            assert metadata.modified_by is None
        if "ModifiedByEGID" not in element_attrs:
            assert metadata.modified_by_eg_id is None
        if "ModifiedByEGVer" not in element_attrs:
            assert metadata.modified_by_eg_ver is None

        # Settings fields that are absent must be None
        settings_obj = result.settings
        assert settings_obj is not None
        for xml_name, py_field in _SETTINGS_FIELD_MAP.items():
            if xml_name not in settings_fields:
                actual = getattr(settings_obj, py_field)
                assert actual is None, (
                    f"Absent settings field {py_field} should be None, got {actual!r}"
                )

    @given(data=_project_xml_strategy())
    @settings(max_examples=300)
    def test_parameters_match_xml(self, data):
        """Parameters list matches what was in the XML exactly.

        **Validates: Requirement 2.6**
        """
        xml_string, root_attrs, element_attrs, settings_fields, parameters = data

        result = parse_project_xml(xml_string)

        # When no parameters section, the list should be empty
        if not parameters:
            assert result.parameters == []
        else:
            assert len(result.parameters) == len(parameters)
            for param, (expected_name, expected_value) in zip(
                result.parameters, parameters
            ):
                assert param.name == expected_name
                assert param.value == expected_value
