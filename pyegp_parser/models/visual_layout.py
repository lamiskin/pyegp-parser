"""Visual layout models for EGP process flow display configuration.

This module defines dataclasses representing the spatial arrangement
of process flow nodes, including their positions, sizes, styles,
and the overall view settings (zoom, grid, margins).

Related requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7
"""

from dataclasses import dataclass, field


@dataclass
class TaskGraphic:
    """A visual representation of a task node in the process flow layout.

    Contains position, size, style, and reference to the corresponding
    project Element. All fields are optional to handle partial XML data.

    Attributes:
        type: The graphic type identifier.
        id: Unique identifier for this graphic.
        line_width: Width of the border line.
        fill: Fill color or pattern.
        pos_x: Horizontal position (X coordinate).
        pos_y: Vertical position (Y coordinate).
        width: Width of the graphic.
        height: Height of the graphic.
        rotation: Rotation angle.
        visible: Whether the graphic is visible.
        border: Border style or color.
        auto_size: Whether the graphic auto-sizes.
        removable: Whether the graphic can be removed.
        child: Child graphic reference.
        selected: Whether the graphic is currently selected.
        label: Display label text.
        element: Reference to the associated Element ID.
    """

    type: str | None = None
    id: str | None = None
    line_width: str | None = None
    fill: str | None = None
    pos_x: str | None = None
    pos_y: str | None = None
    width: str | None = None
    height: str | None = None
    rotation: str | None = None
    visible: str | None = None
    border: str | None = None
    auto_size: str | None = None
    removable: str | None = None
    child: str | None = None
    selected: str | None = None
    label: str | None = None
    element: str | None = None


@dataclass
class ProcessFlowControlState:
    """Visual layout state for a single process flow container.

    Contains the container reference, display settings (zoom, grid, etc.),
    and the list of TaskGraphic entries defining node positions.

    Attributes:
        container_id: The ID of the associated ProcessFlowContainer element.
        zoom: The zoom level of the process flow view.
        show_grid: Whether the grid is displayed.
        show_margins: Whether margins are displayed.
        align: Alignment setting for the view.
        task_graphics: List of TaskGraphic entries for this container.
    """

    container_id: str | None = None
    zoom: str | None = None
    show_grid: str | None = None
    show_margins: str | None = None
    align: str | None = None
    task_graphics: list[TaskGraphic] = field(default_factory=list)


@dataclass
class TreeItem:
    """An item in the OpenProjectView tree.

    Represents a node in the project tree view with its expansion state.

    Attributes:
        id: The ID of the tree item (references an Element or container).
        is_expanded: Whether the tree item is expanded in the view.
    """

    id: str | None = None
    is_expanded: bool | None = None


@dataclass
class VisualLayout:
    """Top-level visual layout container for the entire project.

    Groups all ProcessFlowControlState entries and provides access
    to the complete visual layout information.

    Attributes:
        process_flow_states: List of ProcessFlowControlState entries.
        warnings: Warnings generated during layout parsing (e.g., unresolved refs).
    """

    process_flow_states: list[ProcessFlowControlState] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
