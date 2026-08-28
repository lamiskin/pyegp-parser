"""Parser for ShortCut elements (ShortCutToData and ShortCutToFile).

Extracts the SHORTCUT section from element XML nodes, including the Parent
reference, INPUTLIST entries, and the optional UserHasExplicitlySetLabel flag.
"""

import xml.etree.ElementTree as ET

from ..models.base import ElementMetadata
from ..models.shortcut import ShortCutToData, ShortCutToFile


def parse_shortcut(
    element_node: ET.Element, metadata: ElementMetadata, is_data: bool
) -> ShortCutToData | ShortCutToFile:
    """Parse a ShortCut element (either ShortCutToData or ShortCutToFile).

    Extracts the SHORTCUT section containing the Parent reference and
    INPUTLIST. Raises ValueError if any required component is missing.

    Args:
        element_node: The XML Element node containing the SHORTCUT section.
        metadata: Pre-extracted element metadata.
        is_data: True for ShortCutToData, False for ShortCutToFile.

    Returns:
        ShortCutToData or ShortCutToFile with all fields populated.

    Raises:
        ValueError: If SHORTCUT section, Parent reference, or INPUTLIST is missing.
    """
    element_id = metadata.id or "unknown"
    shortcut_type = "ShortCutToData" if is_data else "ShortCutToFile"

    # Extract the SHORTCUT section
    shortcut_section = element_node.find("SHORTCUT")
    if shortcut_section is None:
        raise ValueError(
            f"{shortcut_type} element '{element_id}' is missing the SHORTCUT section"
        )

    # Extract the Parent reference
    parent_elem = shortcut_section.find("Parent")
    if parent_elem is None or not parent_elem.text or not parent_elem.text.strip():
        raise ValueError(
            f"{shortcut_type} element '{element_id}' is missing the Parent reference"
        )
    parent_id = parent_elem.text.strip()

    # Extract the INPUTLIST
    input_list_elem = shortcut_section.find("INPUTLIST")
    if input_list_elem is None:
        raise ValueError(
            f"{shortcut_type} element '{element_id}' is missing the INPUTLIST"
        )

    input_list: list[str] = []
    for input_id_elem in input_list_elem.findall("INPUTID"):
        if input_id_elem.text and input_id_elem.text.strip():
            input_list.append(input_id_elem.text.strip())

    # Extract optional UserHasExplicitlySetLabel flag
    user_label_elem = shortcut_section.find("UserHasExplicitlySetLabel")
    user_has_explicitly_set_label: bool | None = None
    if user_label_elem is not None and user_label_elem.text:
        text = user_label_elem.text.strip().lower()
        if text:
            user_has_explicitly_set_label = text == "true"

    if is_data:
        return ShortCutToData(
            metadata=metadata,
            parent_id=parent_id,
            input_list=input_list,
            user_has_explicitly_set_label=user_has_explicitly_set_label,
        )
    else:
        return ShortCutToFile(
            metadata=metadata,
            parent_id=parent_id,
            input_list=input_list,
            user_has_explicitly_set_label=user_has_explicitly_set_label,
        )
