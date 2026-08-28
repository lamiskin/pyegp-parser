"""Shortcut element models for EGP project data and file references."""

from dataclasses import dataclass, field

from .base import ElementMetadata


@dataclass
class ShortCutToData:
    """A shortcut referencing a DataList item in the EGP project.

    Shortcuts provide an indirect reference to data items within
    process flows, enabling data to be connected to tasks without
    duplicating DataList entries.

    Attributes:
        metadata: Standard element metadata.
        parent_id: ID of the referenced DataList item (from SHORTCUT/Parent).
        input_list: List of input IDs from SHORTCUT/INPUTLIST/INPUTID entries.
        user_has_explicitly_set_label: Flag indicating the user explicitly
            set the label. None if absent from XML.
    """

    metadata: ElementMetadata | None = None
    parent_id: str | None = None
    input_list: list[str] = field(default_factory=list)
    user_has_explicitly_set_label: bool | None = None


@dataclass
class ShortCutToFile:
    """A shortcut referencing an ExternalFileList item in the EGP project.

    Similar to ShortCutToData but references external file entries
    rather than internal data items.

    Attributes:
        metadata: Standard element metadata.
        parent_id: ID of the referenced ExternalFileList item (from SHORTCUT/Parent).
        input_list: List of input IDs from SHORTCUT/INPUTLIST/INPUTID entries.
        user_has_explicitly_set_label: Flag indicating the user explicitly
            set the label. None if absent from XML.
    """

    metadata: ElementMetadata | None = None
    parent_id: str | None = None
    input_list: list[str] = field(default_factory=list)
    user_has_explicitly_set_label: bool | None = None
