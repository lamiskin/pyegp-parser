"""Visual layout parser for EGP process flow display configuration.

Parses the ProcessFlowControlManager section from project.xml to extract
visual layout state for each process flow container, including TaskGraphic
positions/styles and view settings (zoom, grid, margins).

Also parses the OpenProjectView section for TreeItem entries.

Related requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7
"""

import xml.etree.ElementTree as ET

from ..models.visual_layout import (
    ProcessFlowControlState,
    TaskGraphic,
    TreeItem,
    VisualLayout,
)


def parse_visual_layout(
    root: ET.Element, element_ids: set[str] | None = None
) -> VisualLayout:
    """Parse the ProcessFlowControlManager section into a VisualLayout.

    Extracts all ProcessFlowControlState entries with their TaskGraphic
    children. If element_ids is provided, warns for any TaskGraphic
    Element references that don't match a known element ID.

    Args:
        root: The root XML element of project.xml (ProjectCollection).
        element_ids: Optional set of known Element IDs for reference validation.

    Returns:
        VisualLayout with all extracted process flow states and any warnings.
    """
    warnings: list[str] = []
    process_flow_states: list[ProcessFlowControlState] = []

    # Requirement 14.1: Extract ProcessFlowControlManager section
    manager = root.find("ProcessFlowControlManager")

    # Requirement 14.2: If absent, return empty collection
    if manager is None:
        return VisualLayout(process_flow_states=[], warnings=[])

    # Parse each ProcessFlowControlState entry
    for state_elem in manager.findall("ProcessFlowControlState"):
        state = _parse_control_state(state_elem, element_ids, warnings)
        process_flow_states.append(state)

    return VisualLayout(
        process_flow_states=process_flow_states,
        warnings=warnings,
    )


def parse_open_project_view(root: ET.Element) -> list[TreeItem]:
    """Parse the OpenProjectView section into a list of TreeItem entries.

    Extracts all TreeItem entries with their ID and IsExpanded state.

    Args:
        root: The root XML element of project.xml (ProjectCollection).

    Returns:
        List of TreeItem entries, or empty list if section is absent.
    """
    # Requirement 14.6 & 14.7
    open_view = root.find("OpenProjectView")
    if open_view is None:
        return []

    tree_items: list[TreeItem] = []
    for item_elem in open_view.findall("TreeItem"):
        tree_item = TreeItem(
            id=item_elem.get("ID"),
            is_expanded=_parse_bool(item_elem.get("IsExpanded")),
        )
        tree_items.append(tree_item)

    return tree_items


def _parse_control_state(
    state_elem: ET.Element,
    element_ids: set[str] | None,
    warnings: list[str],
) -> ProcessFlowControlState:
    """Parse a single ProcessFlowControlState element.

    Extracts ContainerID, Zoom, ShowGrid, ShowMargins, Align settings
    and all child TaskGraphic entries.

    Args:
        state_elem: The ProcessFlowControlState XML element.
        element_ids: Optional set of known Element IDs for validation.
        warnings: Mutable list to append warnings to.

    Returns:
        ProcessFlowControlState with all extracted data.
    """
    # Requirement 14.3: Extract container settings
    container_id = state_elem.get("ContainerID")
    zoom = state_elem.get("Zoom")
    show_grid = state_elem.get("ShowGrid")
    show_margins = state_elem.get("ShowMargins")
    align = state_elem.get("Align")

    # Requirement 14.4: Extract TaskGraphic entries
    task_graphics: list[TaskGraphic] = []
    for graphic_elem in state_elem.findall("TaskGraphic"):
        graphic = _parse_task_graphic(graphic_elem, element_ids, warnings)
        task_graphics.append(graphic)

    return ProcessFlowControlState(
        container_id=container_id,
        zoom=zoom,
        show_grid=show_grid,
        show_margins=show_margins,
        align=align,
        task_graphics=task_graphics,
    )


def _get_child_text(elem: ET.Element, tag_name: str) -> str | None:
    """Get a value by first trying child-text-element access, then attribute access.

    In EGP 8.x files, position/style values are stored as child text elements
    (e.g., <PosX>24</PosX>). In legacy files, they may be stored as XML attributes
    (e.g., PosX="24"). This helper supports both formats.

    Args:
        elem: The parent XML element to search within.
        tag_name: The tag/attribute name to look up.

    Returns:
        The text content of the child element if found, otherwise the attribute
        value, or None if neither exists.
    """
    child = elem.find(tag_name)
    if child is not None:
        return child.text
    return elem.get(tag_name)


def _parse_task_graphic(
    graphic_elem: ET.Element,
    element_ids: set[str] | None,
    warnings: list[str],
) -> TaskGraphic:
    """Parse a single TaskGraphic element.

    Extracts all position/style attributes and validates the Element
    reference if element_ids is provided. Supports both child-text-element
    format (EGP 8.x) and attribute format (legacy) for position/style fields.

    Args:
        graphic_elem: The TaskGraphic XML element.
        element_ids: Optional set of known Element IDs for validation.
        warnings: Mutable list to append warnings to.

    Returns:
        TaskGraphic with all extracted attributes.
    """
    element_ref = graphic_elem.get("Element")

    # Requirement 14.5: Warn for unresolved element references
    if element_ref and element_ids is not None and element_ref not in element_ids:
        warnings.append(
            f"TaskGraphic Element reference '{element_ref}' does not match "
            f"any known Element ID in the project"
        )

    return TaskGraphic(
        type=graphic_elem.get("Type"),
        id=graphic_elem.get("Id"),
        line_width=_get_child_text(graphic_elem, "LineWidth"),
        fill=_get_child_text(graphic_elem, "Fill"),
        pos_x=_get_child_text(graphic_elem, "PosX"),
        pos_y=_get_child_text(graphic_elem, "PosY"),
        width=_get_child_text(graphic_elem, "Width"),
        height=_get_child_text(graphic_elem, "Height"),
        rotation=_get_child_text(graphic_elem, "Rotation"),
        visible=_get_child_text(graphic_elem, "Visible"),
        border=_get_child_text(graphic_elem, "Border"),
        auto_size=_get_child_text(graphic_elem, "AutoSize"),
        removable=_get_child_text(graphic_elem, "Removable"),
        child=_get_child_text(graphic_elem, "Child"),
        selected=_get_child_text(graphic_elem, "Selected"),
        label=_get_child_text(graphic_elem, "Label"),
        element=element_ref,
    )


def _parse_bool(value: str | None) -> bool | None:
    """Parse a boolean string attribute to a Python bool.

    Args:
        value: String value (e.g., "True", "False", "true", "false").

    Returns:
        True/False for recognized values, None if value is None.
    """
    if value is None:
        return None
    return value.lower() == "true"
