"""DNA (Data Naming Architecture) XML decoder.

Decodes DNA XML strings — potentially HTML-escaped or double-encoded — into
structured DNADescriptor objects. Handles recursive ParentDNA decoding for
nested data source hierarchies.

DNA XML is embedded within EGP project.xml elements (e.g., RawActiveDataSourceState
in DataList items, or within ExternalFile entries) and may be stored as escaped
HTML entities requiring one or more unescape passes before XML parsing.
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from html import unescape
from typing import Optional, overload


@dataclass
class DNADescriptor:
    """Structured representation of a DNA (Data Naming Architecture) descriptor.

    DNA descriptors encode hierarchical path information for SAS data sources
    and files. They may be nested via the parent_dna field to represent
    parent-child relationships in data source resolution.

    Attributes:
        type: The descriptor type (e.g., "SAS.Servers.ServerDef").
        name: The descriptor name.
        version: The descriptor version string.
        assembly: The .NET assembly reference, if present.
        factory: The factory class reference, if present.
        parent_name: Parent data source name (dataset-specific).
        display_name: Human-readable display name.
        display_path: Display path for the data source.
        server: SAS server name.
        library: SAS library reference.
        full_path: Full file system path (file-specific).
        read_only: Whether the resource is read-only.
        temp: Whether the resource is temporary.
        parent_dna: Recursively decoded parent DNA descriptor.
    """

    type: str
    name: str
    version: str
    assembly: str | None
    factory: str | None
    # Dataset-specific
    parent_name: str | None = None
    display_name: str | None = None
    display_path: str | None = None
    server: str | None = None
    library: str | None = None
    # File-specific
    full_path: str | None = None
    # Additional
    read_only: bool | None = None
    temp: bool | None = None
    # Recursive parent
    parent_dna: Optional["DNADescriptor"] = None


def decode_dna(xml_text: str) -> DNADescriptor:
    """Decode a DNA XML string (potentially HTML-escaped) into a DNADescriptor.

    The DNA may be double-encoded (HTML entities within XML CDATA).
    This function handles recursive ParentDNA decoding.

    The decoding strategy tries parsing in order:
    1. Parse the raw string as XML (common when extracted from a parent XML doc)
    2. Unescape once and parse (for HTML-escaped DNA strings)
    3. Unescape twice and parse (for double-encoded strings)

    Args:
        xml_text: The raw DNA XML text (may be HTML-escaped).

    Returns:
        DNADescriptor with all fields populated.

    Raises:
        ValueError: If the DNA XML cannot be parsed.
    """
    root = _parse_dna_xml(xml_text)

    parent_dna = None
    parent_dna_elem = root.find("ParentDNA")
    if parent_dna_elem is not None:
        parent_dna = _extract_parent_dna(parent_dna_elem)

    return DNADescriptor(
        type=_get_text(root, "Type", ""),
        name=_get_text(root, "Name", ""),
        version=_get_text(root, "Version", ""),
        assembly=_get_text(root, "Assembly"),
        factory=_get_text(root, "Factory"),
        parent_name=_get_text(root, "ParentName"),
        display_name=_get_text(root, "DisplayName"),
        display_path=_get_text(root, "DisplayPath"),
        server=_get_text(root, "Server"),
        library=_get_text(root, "Library"),
        full_path=_get_text(root, "FullPath"),
        read_only=_get_bool(root, "ReadOnly"),
        temp=_get_bool(root, "Temp"),
        parent_dna=parent_dna,
    )


def _parse_dna_xml(xml_text: str) -> ET.Element:
    """Attempt to parse DNA XML with progressive unescaping.

    Tries raw, then single-unescape, then double-unescape.

    Raises:
        ValueError: If none of the attempts succeed.
    """
    # Try raw first (common when already within parsed XML context)
    try:
        return ET.fromstring(xml_text)
    except ET.ParseError:
        pass

    # Try unescaping once (HTML-escaped input)
    unescaped = unescape(xml_text)
    try:
        return ET.fromstring(unescaped)
    except ET.ParseError:
        pass

    # Try unescaping twice (double-encoded)
    double_unescaped = unescape(unescaped)
    try:
        return ET.fromstring(double_unescaped)
    except ET.ParseError as e:
        raise ValueError(f"DNA XML cannot be parsed: {e}") from e


def _extract_parent_dna(parent_dna_elem: ET.Element) -> "DNADescriptor | None":
    """Extract the ParentDNA from an element.

    Handles two cases:
    1. ParentDNA has text content (escaped XML string) - decode recursively
    2. ParentDNA has child elements (XML parser already decoded entities) -
       serialize child back to string and decode recursively
    """
    # Case 1: text content (the XML entities were preserved as text)
    if parent_dna_elem.text and parent_dna_elem.text.strip():
        return decode_dna(parent_dna_elem.text.strip())

    # Case 2: child elements (the XML parser decoded the entities into elements)
    children = list(parent_dna_elem)
    if children:
        # Serialize the first child element back to string
        child_xml = ET.tostring(children[0], encoding="unicode")
        return decode_dna(child_xml)

    return None


@overload
def _get_text(elem: ET.Element, tag: str, default: str) -> str: ...
@overload
def _get_text(elem: ET.Element, tag: str, default: None = None) -> str | None: ...


def _get_text(elem: ET.Element, tag: str, default: str | None = None) -> str | None:
    """Get text content of a child element, returning default if absent or empty."""
    child = elem.find(tag)
    if child is None or not child.text or child.text.strip() == "":
        return default
    return child.text.strip()


def _get_bool(elem: ET.Element, tag: str) -> bool | None:
    """Get boolean from a child element's text.

    Returns None if the element is absent or empty.
    Returns True if text is 'true' (case-insensitive), False otherwise.
    """
    text = _get_text(elem, tag)
    if text is None:
        return None
    return text.lower() == "true"
