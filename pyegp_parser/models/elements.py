"""Element type classification logic for EGP project elements."""

from enum import Enum


class ElementCategory(Enum):
    """Classification categories for EGP project elements.

    Each element in project.xml has a Type attribute with a dot-separated
    fully-qualified name. Classification is based on the final segment.
    """

    PROCESS_FLOW_CONTAINER = "ProcessFlowContainer"
    SHORTCUT_TO_FILE = "ShortCutToFile"
    SHORTCUT_TO_DATA = "ShortCutToData"
    QUERY = "Query"
    IMPORT_TASK = "ImportTask"
    EXPORT_TASK = "ExportTask"
    CODE_TASK = "CodeTask"
    EG_TASK = "EGTask"
    APPEND_TASK = "AppendTask"
    LOG = "Log"
    CODE = "Code"
    PROJECT_LOG = "ProjectLog"
    UNKNOWN = "Unknown"


def classify_element_type(type_string: str) -> ElementCategory:
    """Classify an element by the final segment of its Type attribute.

    Takes the fully-qualified type string (e.g.
    "SAS.EG.ProjectElements.ProcessFlowContainer") and returns the
    matching ElementCategory based on the last dot-separated segment.

    Args:
        type_string: The element's Type attribute value.

    Returns:
        The corresponding ElementCategory, or UNKNOWN if the final
        segment does not match any known category.
    """
    if not type_string:
        return ElementCategory.UNKNOWN
    final_segment = type_string.rsplit(".", 1)[-1]
    try:
        return ElementCategory(final_segment)
    except ValueError:
        return ElementCategory.UNKNOWN
