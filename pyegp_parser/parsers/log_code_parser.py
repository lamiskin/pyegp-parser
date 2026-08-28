"""Parsers for Log and Code elements, execution logs, and project log extraction.

This module handles:
- Parsing Log element metadata (Parent, LineSize, PageSize, Portrait, ConditionParent)
- Parsing Code elements (TextElement and structured Code sections)
- Extracting execution logs from {TaskType}-{ID}/Log-{ID}/result.log
- Extracting the project log from ProjectLog-{ID}/ProjectLog-{ID}/result.log
- Extracting ProjectLog element metadata (Enabled, WrittenTo) from project.xml

Requirements: 11.1-11.6, 12.1-12.5
"""

import logging
import re
import xml.etree.ElementTree as ET
from typing import Any

from ..archive import ArchiveInventory, EntryCategory
from ..models.base import ElementMetadata
from ..models.log_code import CodeElement, LogElement
from ..models.project import ProjectLogInfo

logger = logging.getLogger(__name__)

# Regex to extract IDs from execution log paths:
# {TaskType}-{TaskID}/Log-{LogID}/result.log
_EXECUTION_LOG_PATH_PATTERN = re.compile(
    r"^(?P<task_type>\w+)-(?P<task_id>[A-Za-z0-9]+)/Log-(?P<log_id>[A-Za-z0-9]+)/result\.log$"
)

# Regex to extract ID from project log paths:
# ProjectLog-{ID}/ProjectLog-{ID}/result.log
_PROJECT_LOG_PATH_PATTERN = re.compile(
    r"^ProjectLog-(?P<id>[A-Za-z0-9]+)/ProjectLog-(?P<repeat_id>[A-Za-z0-9]+)/result\.log$"
)


def parse_log_element(
    element_node: ET.Element,
    metadata: ElementMetadata,
) -> LogElement:
    """Parse a Log element from project.xml.

    Extracts the Log section including Parent, LineSize, PageSize,
    Portrait flag, and ConditionParent.

    Args:
        element_node: The <Element> XML node for the Log element.
        metadata: Pre-extracted ElementMetadata for this element.

    Returns:
        LogElement with all available fields populated.

    Raises:
        ValueError: If the Log section is absent from the element.
    """
    element_id = metadata.id or "unknown"

    log_section = element_node.find("Log")
    if log_section is None:
        raise ValueError(f"Log element '{element_id}' is missing required Log section")

    parent_id = _get_child_text(log_section, "Parent")
    line_size = _get_child_int(log_section, "LineSize")
    page_size = _get_child_int(log_section, "PageSize")
    portrait = _get_child_bool(log_section, "Portrait")
    condition_parent = _get_child_text(log_section, "ConditionParent")

    return LogElement(
        metadata=metadata,
        parent_id=parent_id,
        line_size=line_size,
        page_size=page_size,
        portrait=portrait,
        condition_parent=condition_parent,
    )


def parse_code_element(
    element_node: ET.Element,
    metadata: ElementMetadata,
) -> CodeElement:
    """Parse a Code element from project.xml.

    Extracts the TextElement section (Text, ReadOnly, DefExt) and the
    structured Code section (Parent, Libref_Code, BeginAppCode, etc.).

    Args:
        element_node: The <Element> XML node for the Code element.
        metadata: Pre-extracted ElementMetadata for this element.

    Returns:
        CodeElement with all available fields populated.

    Raises:
        ValueError: If the element contains neither TextElement nor Code section.
    """
    element_id = metadata.id or "unknown"

    # Parse TextElement section
    text_elem = element_node.find("TextElement")
    text_content: str | None = None
    read_only: bool | None = None
    def_ext: str | None = None

    if text_elem is not None:
        text_content = _get_child_text(text_elem, "Text")
        read_only = _get_child_bool(text_elem, "ReadOnly")
        def_ext = _get_child_text(text_elem, "DefExt")

    # Parse structured Code section
    code_section = element_node.find("Code")
    parent_id: str | None = None
    libref_code: str | None = None
    begin_app_code: str | None = None
    begin_user_code: str | None = None
    task_code: str | None = None
    end_user_code: str | None = None
    end_app_code: str | None = None
    libref_cl_code: str | None = None
    macro_assign_code: str | None = None
    macro_unassign_code: str | None = None

    if code_section is not None:
        parent_id = _get_child_text(code_section, "Parent")
        libref_code = _get_child_text(code_section, "Libref_Code")
        begin_app_code = _get_child_text(code_section, "BeginAppCode")
        begin_user_code = _get_child_text(code_section, "BeginUserCode")
        task_code = _get_child_text(code_section, "TaskCode")
        end_user_code = _get_child_text(code_section, "EndUserCode")
        end_app_code = _get_child_text(code_section, "EndAppCode")
        libref_cl_code = _get_child_text(code_section, "LibrefCl_Code")
        macro_assign_code = _get_child_text(code_section, "MacroAssign_Code")
        macro_unassign_code = _get_child_text(code_section, "MacroUnassign_Code")

    # Requirement 11.6: Raise if neither TextElement nor Code section present
    if text_elem is None and code_section is None:
        raise ValueError(
            f"Code element '{element_id}' has no code content "
            "(missing both TextElement and Code sections)"
        )

    return CodeElement(
        metadata=metadata,
        text=text_content,
        read_only=read_only,
        def_ext=def_ext,
        parent_id=parent_id,
        libref_code=libref_code,
        begin_app_code=begin_app_code,
        begin_user_code=begin_user_code,
        task_code=task_code,
        end_user_code=end_user_code,
        end_app_code=end_app_code,
        libref_cl_code=libref_cl_code,
        macro_assign_code=macro_assign_code,
        macro_unassign_code=macro_unassign_code,
    )


def extract_execution_logs(
    archive: ArchiveInventory,
) -> dict[str, str]:
    """Extract all execution logs from the archive, keyed by element ID.

    Reads execution log files at paths matching
    `{TaskType}-{ID}/Log-{ID}/result.log` and returns their contents
    as UTF-8 strings, keyed by the log ID (which corresponds to the
    owning element's ID).

    Args:
        archive: The open ArchiveInventory with classified entries.

    Returns:
        Dict mapping element IDs to their log content strings.

    Raises:
        ValueError: If a log file cannot be decoded as UTF-8.
    """
    logs: dict[str, str] = {}

    for entry in archive.entries:
        if entry.category != EntryCategory.EXECUTION_LOG:
            continue

        match = _EXECUTION_LOG_PATH_PATTERN.match(entry.path)
        if match is None:
            continue

        log_id = match.group("log_id")

        try:
            content = archive.get_content(entry.path, encoding="utf-8")
        except UnicodeDecodeError as e:
            raise ValueError(
                f"Execution log at '{entry.path}' cannot be decoded as UTF-8: {e}"
            ) from e

        logs[log_id] = content

    return logs


def extract_project_log(
    archive: ArchiveInventory,
    root: ET.Element,
) -> ProjectLogInfo:
    """Extract the project log content and metadata.

    Reads the project log file from the archive at
    `ProjectLog-{ID}/ProjectLog-{ID}/result.log` and extracts the
    ProjectLog element metadata (Enabled, WrittenTo) from the parsed
    project.xml root element.

    Args:
        archive: The open ArchiveInventory with classified entries.
        root: The root XML element (ProjectCollection) of project.xml.

    Returns:
        ProjectLogInfo with metadata and content populated.

    Raises:
        ValueError: If the ProjectLog element is absent from project.xml
                    or if the log file cannot be decoded as UTF-8.
    """
    # Find the ProjectLog element in project.xml (in the Elements section)
    project_log_metadata = _find_project_log_element(root)

    # Read the project log content from the archive (if it exists)
    log_content: str | None = None
    for entry in archive.entries:
        if entry.category != EntryCategory.PROJECT_LOG:
            continue

        try:
            log_content = archive.get_content(entry.path, encoding="utf-8")
        except UnicodeDecodeError as e:
            raise ValueError(
                f"Project log at '{entry.path}' cannot be decoded as UTF-8: {e}"
            ) from e
        break  # Only one project log expected

    return ProjectLogInfo(
        enabled=project_log_metadata["enabled"],
        written_to=project_log_metadata["written_to"],
        content=log_content,
    )


def _find_project_log_element(root: ET.Element) -> dict[str, Any]:
    """Find the ProjectLog element in project.xml and extract its metadata.

    Searches the Elements section for an Element with a Type attribute
    ending in "ProjectLog" and extracts its Enabled and WrittenTo flags.

    Args:
        root: The root XML element (ProjectCollection) of project.xml.

    Returns:
        Dict with 'enabled' and 'written_to' boolean values.

    Raises:
        ValueError: If no ProjectLog element is found in the Elements section.
    """
    elements_section = root.find("Elements")
    if elements_section is None:
        raise ValueError(
            "ProjectLog element is absent from project.xml (no Elements section found)"
        )

    for element_node in elements_section.findall("Element"):
        type_attr = element_node.get("Type", "")
        # Match elements whose Type ends with "ProjectLog"
        if type_attr.rsplit(".", 1)[-1] == "ProjectLog":
            # Extract Enabled and WrittenTo from the ProjectLog section
            # or from the element's attributes/children
            enabled = _extract_project_log_flag(element_node, "Enabled")
            written_to = _extract_project_log_flag(element_node, "WrittenTo")
            return {"enabled": enabled, "written_to": written_to}

    raise ValueError(
        "ProjectLog element is absent from project.xml "
        "(no element with Type ending in 'ProjectLog' found)"
    )


def _extract_project_log_flag(element_node: ET.Element, flag_name: str) -> bool | None:
    """Extract a boolean flag from a ProjectLog element.

    Looks for the flag as a direct child element of the Element node,
    or within a ProjectLog sub-section.

    Args:
        element_node: The ProjectLog <Element> node.
        flag_name: Name of the flag to extract (e.g., "Enabled", "WrittenTo").

    Returns:
        Boolean value of the flag, or None if not found.
    """
    # Try direct child element first
    child = element_node.find(flag_name)
    if child is not None and child.text and child.text.strip():
        return child.text.strip().lower() == "true"

    # Try within a ProjectLog sub-section
    project_log_section = element_node.find("ProjectLog")
    if project_log_section is not None:
        child = project_log_section.find(flag_name)
        if child is not None and child.text and child.text.strip():
            return child.text.strip().lower() == "true"

    # Try as an attribute on the element
    attr_value = element_node.get(flag_name)
    if attr_value is not None:
        return attr_value.lower() == "true"

    return None


# --- Helper functions ---


def _get_child_text(parent: ET.Element, tag: str) -> str | None:
    """Get text content of a child element, returning None if absent or empty."""
    child = parent.find(tag)
    if child is None or child.text is None or child.text.strip() == "":
        return None
    return child.text.strip()


def _get_child_bool(parent: ET.Element, tag: str) -> bool | None:
    """Get boolean value from a child element's text content."""
    text = _get_child_text(parent, tag)
    if text is None:
        return None
    return text.lower() == "true"


def _get_child_int(parent: ET.Element, tag: str) -> int | None:
    """Get integer value from a child element's text content."""
    text = _get_child_text(parent, tag)
    if text is None:
        return None
    try:
        return int(text)
    except ValueError:
        return None
