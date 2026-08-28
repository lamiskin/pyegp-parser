"""Parser for the External_Objects section from project.xml.

Extracts external object entries from the External_Objects section,
parsing each ExternalObject child element into a structured dataclass model.

Requirements: 2.2
"""

import xml.etree.ElementTree as ET

from ..models.external_objects import ExternalObject

# Known child element tags that map to named fields on ExternalObject
_NAMED_FIELDS = {"Name", "Type", "Path", "Description"}


def parse_external_objects(root: ET.Element) -> list[ExternalObject]:
    """Parse the External_Objects section from the project.xml root element.

    Finds the External_Objects section and parses each ExternalObject child
    element into an ExternalObject dataclass.

    Args:
        root: The root XML element (ProjectCollection) of project.xml.

    Returns:
        List of ExternalObject instances. Returns an empty list if the
        External_Objects section is absent.

    Raises:
        ValueError: If an ExternalObject entry is malformed (e.g., missing
            required Name attribute/element).
    """
    external_objects_elem = root.find("External_Objects")
    if external_objects_elem is None:
        return []

    objects: list[ExternalObject] = []
    for obj_elem in external_objects_elem.findall("ExternalObject"):
        obj = _parse_external_object(obj_elem)
        objects.append(obj)

    return objects


def _parse_external_object(obj_elem: ET.Element) -> ExternalObject:
    """Parse a single ExternalObject element into an ExternalObject dataclass.

    Supports two layouts:
    1. Child text elements: <ExternalObject><Name>foo</Name><Type>File</Type>...</ExternalObject>
    2. XML attributes: <ExternalObject Name="foo" Type="File" .../>

    Falls back from child-text-element access to attribute access for each field.

    Args:
        obj_elem: The <ExternalObject> XML element.

    Returns:
        A populated ExternalObject instance.

    Raises:
        ValueError: If the Name field is missing or empty.
    """
    name = _get_field(obj_elem, "Name")
    if not name:
        raise ValueError("ExternalObject entry is missing required 'Name' field")

    obj_type = _get_field(obj_elem, "Type")
    path = _get_field(obj_elem, "Path")
    description = _get_field(obj_elem, "Description")

    # Collect additional metadata from remaining child elements and attributes
    additional_metadata: dict[str, str] = {}

    # Gather from child elements not in _NAMED_FIELDS
    for child in obj_elem:
        if child.tag not in _NAMED_FIELDS and child.text and child.text.strip():
            additional_metadata[child.tag] = child.text.strip()

    # Gather from attributes not in _NAMED_FIELDS (case-sensitive match)
    for attr_name, attr_value in obj_elem.attrib.items():
        # Don't overwrite a value already found as a child element.
        if (
            attr_name not in _NAMED_FIELDS
            and attr_value.strip()
            and attr_name not in additional_metadata
        ):
            additional_metadata[attr_name] = attr_value.strip()

    return ExternalObject(
        name=name,
        type=obj_type,
        path=path,
        description=description,
        metadata=additional_metadata,
    )


def _get_field(elem: ET.Element, tag: str) -> str | None:
    """Get a field value, trying child-text-element access first, then attribute access.

    Args:
        elem: The parent XML element.
        tag: The field name to look up.

    Returns:
        The text value if found and non-empty, otherwise None.
    """
    # Try child text element first
    child = elem.find(tag)
    if child is not None and child.text and child.text.strip():
        return child.text.strip()

    # Fall back to attribute access
    attr_value = elem.get(tag)
    if attr_value and attr_value.strip():
        return attr_value.strip()

    return None
