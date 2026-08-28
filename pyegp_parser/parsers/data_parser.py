"""Parsers for DataList and ExternalFileList sections from project.xml.

Provides functions to extract data items and external file references
from the project.xml root element, including DNA decoding and Element
metadata extraction.
"""

import xml.etree.ElementTree as ET

from ..models.base import ElementMetadata
from ..models.data import DataItem, DataModel
from ..models.external_file import ExternalFileItem
from .dna_parser import DNADescriptor, decode_dna


def parse_data_list(root: ET.Element) -> list[DataItem]:
    """Parse the DataList section from project.xml root element.

    Extracts all Data items with their Element metadata, DataModel fields,
    and ShortCutList references.

    Args:
        root: The root XML element (ProjectCollection) of project.xml.

    Returns:
        List of DataItem objects extracted from the DataList section.
        Returns an empty list if DataList is absent.
    """
    data_list_elem = root.find("DataList")
    if data_list_elem is None:
        return []

    items: list[DataItem] = []
    for data_elem in data_list_elem.findall("Data"):
        element_metadata = _parse_element_metadata(data_elem)
        # Ensure we always have an ElementMetadata instance (even if empty)
        if element_metadata is None:
            element_metadata = ElementMetadata()
        data_model = _parse_data_model(data_elem)
        shortcut_list = _parse_shortcut_list(data_elem)

        items.append(
            DataItem(
                element=element_metadata,
                data_model=data_model,
                shortcut_list=shortcut_list,
            )
        )

    return items


def _parse_data_model(data_elem: ET.Element) -> DataModel:
    """Extract DataModel fields from a Data element.

    Handles two layouts:
    1. EGP 8.x: DataModel is inside a nested <Data> child element
       (e.g. <Data><Element>...</Element><Data><DataModel>...</DataModel></Data></Data>)
    2. Legacy: DataModel fields are direct children of the <Data> element

    If RawActiveDataSourceState is present and non-empty, decodes the DNA
    and stores the result in decoded_dna. Otherwise, decoded_dna is None.
    """
    # EGP 8.x: Look for DataModel inside a nested <Data> child
    inner_data = data_elem.find("Data")
    if inner_data is not None:
        data_model_elem = inner_data.find("DataModel")
        if data_model_elem is not None:
            return _extract_data_model_from_element(data_model_elem)

    # Legacy: fields are direct children of the <Data> element
    # Or there's a direct DataModel child
    data_model_elem = data_elem.find("DataModel")
    if data_model_elem is not None:
        return _extract_data_model_from_element(data_model_elem)

    # Fallback: try reading fields directly from data_elem
    return _extract_data_model_from_element(data_elem)


def _extract_data_model_from_element(source: ET.Element) -> DataModel:
    """Extract DataModel fields from a source element.

    Args:
        source: Element containing Server, ActiveDataSource, etc. as children.

    Returns:
        Populated DataModel.
    """
    server = _get_child_text(source, "Server")
    active_data_source = _get_child_text(source, "ActiveDataSource")
    display_name = _get_child_text(source, "DisplayName")
    table = _get_child_text(source, "Table")
    raw_state = _get_child_text(source, "RawActiveDataSourceState")
    data_source_state = _get_child_text(source, "DataSourceState")
    table_state = _get_child_text(source, "TableState")
    member_type = _get_child_text(source, "MemberType")

    # Decode DNA if RawActiveDataSourceState is present and non-empty
    decoded_dna: DNADescriptor | None = None
    if raw_state is not None and raw_state.strip():
        decoded_dna = decode_dna(raw_state)

    return DataModel(
        server=server,
        active_data_source=active_data_source,
        display_name=display_name,
        table=table,
        raw_active_data_source_state=raw_state,
        data_source_state=data_source_state,
        table_state=table_state,
        member_type=member_type,
        decoded_dna=decoded_dna,
    )


def parse_external_file_list(root: ET.Element) -> list[ExternalFileItem]:
    """Parse the ExternalFileList section from project.xml root element.

    Extracts all ExternalFile items with their Element metadata, ShortCutList,
    FileTypeType, and decoded DNA descriptor.

    Args:
        root: The root XML element of project.xml (ProjectCollection).

    Returns:
        List of ExternalFileItem objects. Empty list if the ExternalFileList
        section is absent.

    Raises:
        ValueError: If DNA is absent or malformed for any ExternalFile item.
            The error message includes the ExternalFile ID and failure details.
    """
    external_file_list_elem = root.find("ExternalFileList")
    if external_file_list_elem is None:
        return []

    items: list[ExternalFileItem] = []

    for ext_file_elem in external_file_list_elem.findall("ExternalFile"):
        item = _parse_external_file(ext_file_elem)
        items.append(item)

    return items


def _parse_external_file(ext_file_elem: ET.Element) -> ExternalFileItem:
    """Parse a single ExternalFile element into an ExternalFileItem.

    Handles two layouts:
    1. EGP 8.x: metadata in <Element> child, other fields in nested <ExternalFile> child
       (e.g. <ExternalFile><Element>...</Element><ExternalFile><DNA>...</DNA></ExternalFile></ExternalFile>)
    2. Legacy: all fields are direct children of the <ExternalFile> element

    Args:
        ext_file_elem: The <ExternalFile> XML element.

    Returns:
        Populated ExternalFileItem.

    Raises:
        ValueError: If DNA is absent or malformed.
    """
    element = _parse_element_metadata(ext_file_elem)
    shortcut_list = _parse_shortcut_list(ext_file_elem)

    # EGP 8.x: FileTypeType and DNA are inside a nested <ExternalFile> child
    inner_ef = ext_file_elem.find("ExternalFile")
    if inner_ef is not None:
        file_type_type = _get_child_text(inner_ef, "FileTypeType")
        raw_dna = _get_child_text(inner_ef, "DNA")
        # Also try to get shortcuts from inner if not found at outer level
        if not shortcut_list:
            inner_shortcut = inner_ef.find("ShortCutList")
            if inner_shortcut is not None:
                for sc in inner_shortcut.findall("ShortCutID"):
                    if sc.text and sc.text.strip():
                        shortcut_list.append(sc.text.strip())
    else:
        # Legacy: direct children
        file_type_type = _get_child_text(ext_file_elem, "FileTypeType")
        raw_dna = _get_child_text(ext_file_elem, "DNA")

    # Requirement 4.4: Raise ValueError if DNA absent or malformed
    element_id = element.id if element else "unknown"

    if raw_dna is None:
        raise ValueError(f"ExternalFile '{element_id}' is missing required DNA element")

    try:
        decoded_dna = decode_dna(raw_dna)
    except ValueError as e:
        raise ValueError(f"ExternalFile '{element_id}' has malformed DNA: {e}") from e

    return ExternalFileItem(
        element=element,
        shortcut_list=shortcut_list,
        file_type_type=file_type_type,
        raw_dna=raw_dna,
        decoded_dna=decoded_dna,
    )


def _parse_element_metadata(parent_elem: ET.Element) -> ElementMetadata | None:
    """Extract ElementMetadata from the <Element> child of a parent element.

    Handles two layouts:
    1. EGP 8.x: metadata stored as child text elements within <Element>
       (e.g. <Element><Label>...</Label><ID>...</ID></Element>)
    2. Legacy: metadata stored as XML attributes on <Element>
       (e.g. <Element Label="..." ID="..."/>)

    Args:
        parent_elem: The parent XML element containing an <Element> child.

    Returns:
        ElementMetadata if an Element child exists, None otherwise.
    """
    elem = parent_elem.find("Element")
    if elem is None:
        return None

    # Determine layout: check if metadata is stored as child elements or attributes
    # If the Element has child elements like <Label>, <ID>, etc., use child layout
    has_child_metadata = elem.find("Label") is not None or elem.find("ID") is not None

    if has_child_metadata:
        # EGP 8.x layout: metadata as child text elements
        return _extract_metadata_from_child_elements(elem)
    else:
        # Legacy layout: metadata as attributes
        return _extract_metadata_from_attributes(elem)


def _extract_metadata_from_child_elements(elem: ET.Element) -> ElementMetadata:
    """Extract metadata from child text elements (EGP 8.x layout).

    Args:
        elem: The <Element> node with metadata as child text elements.

    Returns:
        ElementMetadata with fields populated from child elements.
    """
    # Parse InputIDs - can be plain text (single ID or comma-separated) or child <ID> elements
    input_ids: list[str] = []
    input_ids_elem = elem.find("InputIDs")
    if input_ids_elem is not None:
        # Check for child <ID> elements first
        id_children = input_ids_elem.findall("ID")
        if id_children:
            for id_elem in id_children:
                if id_elem.text and id_elem.text.strip():
                    input_ids.append(id_elem.text.strip())
        elif input_ids_elem.text and input_ids_elem.text.strip():
            # Plain text content (single ID or comma-separated)
            for id_str in input_ids_elem.text.strip().split(","):
                id_str = id_str.strip()
                if id_str:
                    input_ids.append(id_str)

    # Parse HasSerializationError boolean
    has_error_str = _get_child_text(elem, "HasSerializationError")
    has_serialization_error: bool | None = None
    if has_error_str is not None:
        has_serialization_error = has_error_str.lower() == "true"

    return ElementMetadata(
        label=_get_child_text(elem, "Label"),
        type=_get_child_text(elem, "Type"),
        container=_get_child_text(elem, "Container"),
        id=_get_child_text(elem, "ID"),
        created_on=_get_child_text(elem, "CreatedOn"),
        modified_on=_get_child_text(elem, "ModifiedOn"),
        modified_by=_get_child_text(elem, "ModifiedBy"),
        modified_by_eg_id=_get_child_text(elem, "ModifiedByEGID"),
        modified_by_eg_ver=_get_child_text(elem, "ModifiedByEGVer"),
        has_serialization_error=has_serialization_error,
        input_ids=input_ids,
    )


def _extract_metadata_from_attributes(elem: ET.Element) -> ElementMetadata:
    """Extract metadata from XML attributes (legacy layout).

    Args:
        elem: The <Element> node with metadata as XML attributes.

    Returns:
        ElementMetadata with fields populated from attributes.
    """
    # Parse InputIDs child element
    input_ids: list[str] = []
    input_ids_elem = elem.find("InputIDs")
    if input_ids_elem is not None:
        for id_elem in input_ids_elem.findall("ID"):
            if id_elem.text and id_elem.text.strip():
                input_ids.append(id_elem.text.strip())

    # Parse HasSerializationError boolean
    has_error_str = elem.get("HasSerializationError")
    has_serialization_error: bool | None = None
    if has_error_str is not None:
        has_serialization_error = has_error_str.lower() == "true"

    return ElementMetadata(
        label=elem.get("Label"),
        type=elem.get("Type"),
        container=elem.get("Container"),
        id=elem.get("ID"),
        created_on=elem.get("CreatedOn"),
        modified_on=elem.get("ModifiedOn"),
        modified_by=elem.get("ModifiedBy"),
        modified_by_eg_id=elem.get("ModifiedByEGID"),
        modified_by_eg_ver=elem.get("ModifiedByEGVer"),
        has_serialization_error=has_serialization_error,
        input_ids=input_ids,
    )


def _parse_shortcut_list(parent_elem: ET.Element) -> list[str]:
    """Extract ShortCutList IDs from a parent element.

    Handles two layouts:
    1. EGP 8.x: ShortCutList is inside a nested child element with same tag name
       (e.g. <Data><Data><ShortCutList>...</ShortCutList></Data></Data>
        or <ExternalFile><ExternalFile><ShortCutList>...</ShortCutList></ExternalFile></ExternalFile>)
    2. Legacy: ShortCutList is a direct child of parent_elem

    Args:
        parent_elem: The parent XML element.

    Returns:
        List of shortcut ID strings. Empty list if absent.
    """
    # First try direct child
    shortcut_list_elem = parent_elem.find("ShortCutList")

    # If not found directly, look in nested child with same tag name
    if shortcut_list_elem is None:
        inner = parent_elem.find(parent_elem.tag)
        if inner is not None:
            shortcut_list_elem = inner.find("ShortCutList")

    # Also check inside nested <Data> or <ExternalFile> child (EGP 8.x layout)
    if shortcut_list_elem is None:
        for tag in ("Data", "ExternalFile"):
            inner = parent_elem.find(tag)
            if inner is not None:
                shortcut_list_elem = inner.find("ShortCutList")
                if shortcut_list_elem is not None:
                    break

    if shortcut_list_elem is None:
        return []

    shortcuts: list[str] = []
    for shortcut_elem in shortcut_list_elem.findall("ShortCutID"):
        if shortcut_elem.text and shortcut_elem.text.strip():
            shortcuts.append(shortcut_elem.text.strip())

    return shortcuts


def _get_child_text(parent: ET.Element, tag: str) -> str | None:
    """Get text content of a child element, returning None if absent or empty."""
    child = parent.find(tag)
    if child is None or child.text is None or child.text.strip() == "":
        return None
    return child.text.strip()
