"""Parser for the Elements collection from project.xml.

Extracts all Element nodes from the Elements section, classifies each by
its Type attribute, and produces a list of ParsedElement objects preserving
document order.
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any

from ..models.base import ElementMetadata
from ..models.elements import ElementCategory, classify_element_type


@dataclass
class ParsedElement:
    """A parsed element with its category and raw XML node for further processing.

    Attributes:
        metadata: Standard element metadata extracted from XML attributes.
        category: Classification based on the final segment of the Type attribute.
        xml_node: Reference to the original ET.Element for type-specific parsers.
        original_type: Full Type string preserved for Unknown elements (None otherwise).
    """

    metadata: ElementMetadata
    category: ElementCategory
    xml_node: Any  # ET.Element reference for type-specific parsers
    original_type: str | None = None


def parse_elements(root: ET.Element) -> list[ParsedElement]:
    """Parse all elements from the Elements collection in document order.

    Finds the Elements section within the root ProjectCollection element,
    extracts each Element child node, classifies it by type, and returns
    the complete list preserving XML document order.

    Args:
        root: The root XML element (ProjectCollection) of project.xml.

    Returns:
        List of ParsedElement objects in document order.
        Returns empty list if Elements section is absent.
    """
    elements_section = root.find("Elements")
    if elements_section is None:
        return []

    parsed: list[ParsedElement] = []
    for element_node in elements_section.findall("Element"):
        metadata = _extract_element_metadata(element_node)
        type_string = metadata.type or ""
        category = classify_element_type(type_string)

        # Preserve original full Type string for Unknown elements
        original_type: str | None = None
        if category == ElementCategory.UNKNOWN and type_string:
            original_type = type_string

        parsed.append(
            ParsedElement(
                metadata=metadata,
                category=category,
                xml_node=element_node,
                original_type=original_type,
            )
        )

    return parsed


def _extract_element_metadata(element_node: ET.Element) -> ElementMetadata:
    """Extract standard ElementMetadata from an Element node.

    EGP files store element metadata in two possible layouts:
    1. As XML attributes directly on the <Element> node (e.g., Label="...", ID="...")
    2. As child text elements within a nested <Element> child node
       (e.g., <Element><Label>...</Label><ID>...</ID></Element>)

    This function checks both layouts, preferring child elements (layout 2)
    when present since that's the format used by real EGP 8.x files.

    Args:
        element_node: An <Element> XML node from the Elements collection.

    Returns:
        ElementMetadata with all available fields populated.
        Absent fields default to None per requirement 5.3.
    """
    # Check for nested <Element> child that contains the metadata fields
    inner_element = element_node.find("Element")

    if inner_element is not None:
        # Layout 2: metadata stored as child text elements of inner <Element>
        return _extract_metadata_from_children(inner_element, element_node)

    # Layout 1: metadata stored as attributes on the outer <Element> node
    return _extract_metadata_from_attributes(element_node)


def _extract_metadata_from_children(
    inner_element: ET.Element, outer_element: ET.Element
) -> ElementMetadata:
    """Extract metadata from child text elements of an inner <Element> node.

    Args:
        inner_element: The nested <Element> child containing metadata as text children.
        outer_element: The parent <Element> node (for Type attribute fallback).

    Returns:
        ElementMetadata with fields populated from child elements.
    """

    def _get_text(parent: ET.Element, tag: str) -> str | None:
        child = parent.find(tag)
        if child is None or child.text is None or child.text.strip() == "":
            return None
        return child.text.strip()

    # Parse InputIDs - can be a single element with comma-separated or child <ID> elements
    input_ids: list[str] = []
    input_ids_elem = inner_element.find("InputIDs")
    if input_ids_elem is not None:
        # Check for child <ID> elements first
        id_children = input_ids_elem.findall("ID")
        if id_children:
            for id_elem in id_children:
                if id_elem.text and id_elem.text.strip():
                    input_ids.append(id_elem.text.strip())
        elif input_ids_elem.text and input_ids_elem.text.strip():
            # Might be comma-separated in text content
            for id_str in input_ids_elem.text.strip().split(","):
                id_str = id_str.strip()
                if id_str:
                    input_ids.append(id_str)

    # Parse HasSerializationError boolean
    has_error_str = _get_text(inner_element, "HasSerializationError")
    has_serialization_error: bool | None = None
    if has_error_str is not None:
        has_serialization_error = has_error_str.lower() == "true"

    # Type: prefer outer element's Type attribute (the full namespace path)
    type_value = outer_element.get("Type") or _get_text(inner_element, "Type")

    return ElementMetadata(
        label=_get_text(inner_element, "Label"),
        type=type_value,
        container=_get_text(inner_element, "Container"),
        id=_get_text(inner_element, "ID"),
        created_on=_get_text(inner_element, "CreatedOn"),
        modified_on=_get_text(inner_element, "ModifiedOn"),
        modified_by=_get_text(inner_element, "ModifiedBy"),
        modified_by_eg_id=_get_text(inner_element, "ModifiedByEGID"),
        modified_by_eg_ver=_get_text(inner_element, "ModifiedByEGVer"),
        has_serialization_error=has_serialization_error,
        input_ids=input_ids,
    )


def _extract_metadata_from_attributes(element_node: ET.Element) -> ElementMetadata:
    """Extract metadata from XML attributes on the Element node (legacy layout).

    Args:
        element_node: An <Element> XML node with metadata as attributes.

    Returns:
        ElementMetadata with fields populated from attributes.
    """
    # Parse InputIDs child element
    input_ids: list[str] = []
    input_ids_elem = element_node.find("InputIDs")
    if input_ids_elem is not None:
        for id_elem in input_ids_elem.findall("ID"):
            if id_elem.text and id_elem.text.strip():
                input_ids.append(id_elem.text.strip())

    # Parse HasSerializationError boolean attribute
    has_error_str = element_node.get("HasSerializationError")
    has_serialization_error: bool | None = None
    if has_error_str is not None:
        has_serialization_error = has_error_str.lower() == "true"

    return ElementMetadata(
        label=element_node.get("Label"),
        type=element_node.get("Type"),
        container=element_node.get("Container"),
        id=element_node.get("ID"),
        created_on=element_node.get("CreatedOn"),
        modified_on=element_node.get("ModifiedOn"),
        modified_by=element_node.get("ModifiedBy"),
        modified_by_eg_id=element_node.get("ModifiedByEGID"),
        modified_by_eg_ver=element_node.get("ModifiedByEGVer"),
        has_serialization_error=has_serialization_error,
        input_ids=input_ids,
    )
