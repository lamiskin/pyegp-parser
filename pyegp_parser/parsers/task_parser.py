"""Parsers for task-type elements (ImportTask, CodeTask, EGTask, ExportTask, AppendTask).

Each parser extracts the SubmitableElement section (reusing the shared
parse_submitable_element function from query_parser) and any task-specific
configuration from the XML element node. For tasks that store external
files in the archive (code files, task config XML), an optional archive
parameter allows reading those artifacts.
"""

import logging
import xml.etree.ElementTree as ET
from typing import Any

from ..models.base import ElementMetadata
from ..models.tasks import (
    AppendTaskElement,
    CodeTaskElement,
    EGTaskElement,
    ExportTaskElement,
    ImportTaskElement,
)
from .query_parser import parse_submitable_element

logger = logging.getLogger(__name__)


def _element_dir(element_id: str, element_type: str) -> str:
    """Return the archive directory holding an element's external artifacts.

    Enterprise Guide stores each task's files under a folder named for the
    element, e.g. ``CodeTask-xjq1AoRtuimaEV8v/code.sas``. Real projects write
    the type prefix into the ID itself, so the folder name *is* the ID; IDs
    that arrive bare still need the prefix added. Prefixing unconditionally
    would look for ``CodeTask-CodeTask-.../code.sas`` and silently find nothing.
    """
    prefix = f"{element_type}-"
    if element_id.startswith(prefix):
        return element_id
    return f"{prefix}{element_id}"


def parse_import_task(
    element_node: ET.Element,
    metadata: ElementMetadata,
    archive=None,
) -> ImportTaskElement:
    """Parse an ImportTask element.

    Extracts the SubmitableElement section, EGTask section (Task_CLSID,
    CurrentViewType, Obs, FirstObs, GeneratesCodeFlag, GenerateOutputDataNames,
    InputDatalist, VarNameParameters), and ImportTask section (Parent reference).
    Optionally reads Task_Config XML from the archive.

    Args:
        element_node: The <Element> XML node for the ImportTask.
        metadata: Pre-extracted ElementMetadata for this element.
        archive: Optional ArchiveInventory to read Task_Config from.

    Returns:
        ImportTaskElement with all extracted fields populated.

    Raises:
        ValueError: If EGTask or ImportTask section missing, or Task_Config malformed.
    """
    element_id = metadata.id or "unknown"

    # Parse SubmitableElement (reuse from query_parser)
    submitable = parse_submitable_element(element_node)

    # Parse EGTask section (required)
    eg_task_node = element_node.find("EGTask")
    if eg_task_node is None:
        raise ValueError(
            f"ImportTask element '{element_id}' is missing required EGTask section"
        )

    eg_task_clsid = _get_child_text(eg_task_node, "Task_CLSID")
    current_view_type = _get_child_text(eg_task_node, "CurrentViewType")
    obs = _get_child_int(eg_task_node, "Obs")
    first_obs = _get_child_int(eg_task_node, "FirstObs")
    generates_code_flag = _get_child_bool(eg_task_node, "GeneratesCodeFlag")
    generate_output_data_names = _get_child_text(
        eg_task_node, "GenerateOutputDataNames"
    )
    var_name_parameters = _get_child_text(eg_task_node, "VarNameParameters")

    # Parse InputDatalist
    input_data_list = _parse_input_data_list(eg_task_node)

    # Parse ImportTask section (required)
    import_task_node = element_node.find("ImportTask")
    if import_task_node is None:
        raise ValueError(
            f"ImportTask element '{element_id}' is missing required ImportTask section"
        )

    parent_elem = import_task_node.find("Parent")
    parent_id: str | None = None
    if parent_elem is not None and parent_elem.text and parent_elem.text.strip():
        parent_id = parent_elem.text.strip()

    # Read Task_Config from archive if available
    task_config: Any = None
    if archive is not None and element_id != "unknown":
        config_dir = _element_dir(element_id, "ImportTask")
        config_path = f"{config_dir}/{config_dir}.xml"
        try:
            config_content = archive.get_content(config_path)
            task_config = _parse_task_config_xml(
                config_content, element_id, "ImportTask"
            )
        except (KeyError, FileNotFoundError):
            logger.warning(
                "ImportTask '%s': task config not found at '%s'",
                element_id,
                config_path,
            )
            task_config = None

    return ImportTaskElement(
        metadata=metadata,
        submitable=submitable,
        eg_task_clsid=eg_task_clsid,
        current_view_type=current_view_type,
        obs=obs,
        first_obs=first_obs,
        generates_code_flag=generates_code_flag,
        generate_output_data_names=generate_output_data_names,
        input_data_list=input_data_list,
        var_name_parameters=var_name_parameters,
        parent_id=parent_id,
        task_config=task_config,
    )


def _parse_input_data_list(eg_task_node: ET.Element) -> list[str]:
    """Parse the InputDatalist section from EGTask, extracting Data IDs."""
    container = eg_task_node.find("InputDatalist")
    if container is None:
        return []

    ids: list[str] = []
    for data_elem in container.findall("Data"):
        data_id = data_elem.get("ID")
        if data_id:
            ids.append(data_id)
    return ids


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


def parse_code_task(
    element_node: ET.Element,
    metadata: ElementMetadata,
    archive=None,
) -> CodeTaskElement:
    """Parse a CodeTask element.

    Extracts the SubmitableElement section and reads the SAS code content
    from the archive at `CodeTask-{ID}/code.sas`.

    Args:
        element_node: The <Element> XML node for the CodeTask.
        metadata: Pre-extracted ElementMetadata for this element.
        archive: Optional ArchiveInventory to read code.sas from.

    Returns:
        CodeTaskElement with submitable and code_content populated.
    """
    submitable = parse_submitable_element(element_node)

    code_content: str | None = None
    element_id = metadata.id

    if archive is not None and element_id:
        code_path = f"{_element_dir(element_id, 'CodeTask')}/code.sas"
        try:
            code_content = archive.get_content(code_path)
        except (KeyError, FileNotFoundError):
            logger.warning(
                "CodeTask '%s': code file not found at '%s'",
                element_id,
                code_path,
            )
            code_content = None

    return CodeTaskElement(
        metadata=metadata,
        submitable=submitable,
        code_content=code_content,
    )


def parse_eg_task(
    element_node: ET.Element,
    metadata: ElementMetadata,
    archive=None,
) -> EGTaskElement:
    """Parse an EGTask element.

    Extracts the SubmitableElement section and the EGTask section
    (Task_CLSID, GeneratesCodeFlag). Optionally reads Task_Config XML
    from the archive at `EGTask-{ID}/EGTask-{ID}.xml`.

    Args:
        element_node: The <Element> XML node for the EGTask.
        metadata: Pre-extracted ElementMetadata for this element.
        archive: Optional ArchiveInventory to read task config from.

    Returns:
        EGTaskElement with all available fields populated.

    Raises:
        ValueError: If the Task_Config file exists but is malformed.
    """
    submitable = parse_submitable_element(element_node)

    # Extract EGTask section
    eg_task_clsid: str | None = None
    generates_code_flag: bool | None = None

    eg_task_section = element_node.find("EGTask")
    if eg_task_section is not None:
        clsid_elem = eg_task_section.find("Task_CLSID")
        if clsid_elem is not None and clsid_elem.text:
            eg_task_clsid = clsid_elem.text.strip()

        gen_code_elem = eg_task_section.find("GeneratesCodeFlag")
        if gen_code_elem is not None and gen_code_elem.text:
            generates_code_flag = gen_code_elem.text.strip().lower() == "true"

    # Read optional Task_Config from archive
    task_config: Any = None
    element_id = metadata.id

    if archive is not None and element_id:
        config_dir = _element_dir(element_id, "EGTask")
        config_path = f"{config_dir}/{config_dir}.xml"
        try:
            config_content = archive.get_content(config_path)
            task_config = _parse_task_config_xml(config_content, element_id, "EGTask")
        except (KeyError, FileNotFoundError):
            logger.warning(
                "EGTask '%s': task config not found at '%s'",
                element_id,
                config_path,
            )
            task_config = None

    return EGTaskElement(
        metadata=metadata,
        submitable=submitable,
        eg_task_clsid=eg_task_clsid,
        generates_code_flag=generates_code_flag,
        task_config=task_config,
    )


def parse_export_task(
    element_node: ET.Element,
    metadata: ElementMetadata,
) -> ExportTaskElement:
    """Parse an ExportTask element.

    Extracts the SubmitableElement section and task-specific configuration
    from the ExportTask section (Parent reference and output settings).

    Args:
        element_node: The <Element> XML node for the ExportTask.
        metadata: Pre-extracted ElementMetadata for this element.

    Returns:
        ExportTaskElement with submitable and task config populated.
    """
    submitable = parse_submitable_element(element_node)

    parent_id: str | None = None
    task_config: dict | None = None

    export_task_section = element_node.find("ExportTask")
    if export_task_section is not None:
        parent_elem = export_task_section.find("Parent")
        if parent_elem is not None and parent_elem.text:
            parent_id = parent_elem.text.strip()

        # Collect all other child elements as task config
        config_dict = _section_to_dict(export_task_section, exclude={"Parent"})
        if config_dict:
            task_config = config_dict

    return ExportTaskElement(
        metadata=metadata,
        submitable=submitable,
        parent_id=parent_id,
        task_config=task_config,
    )


def parse_append_task(
    element_node: ET.Element,
    metadata: ElementMetadata,
) -> AppendTaskElement:
    """Parse an AppendTask element.

    Extracts the SubmitableElement section and task-specific configuration
    from the AppendTask section (Parent reference and InputDataRefs).

    Args:
        element_node: The <Element> XML node for the AppendTask.
        metadata: Pre-extracted ElementMetadata for this element.

    Returns:
        AppendTaskElement with submitable and task config populated.
    """
    submitable = parse_submitable_element(element_node)

    parent_id: str | None = None
    input_data_refs: list[str] = []
    task_config: dict | None = None

    append_task_section = element_node.find("AppendTask")
    if append_task_section is not None:
        parent_elem = append_task_section.find("Parent")
        if parent_elem is not None and parent_elem.text:
            parent_id = parent_elem.text.strip()

        # Extract InputDataRefs
        input_data_refs_elem = append_task_section.find("InputDataRefs")
        if input_data_refs_elem is not None:
            for data_ref_elem in input_data_refs_elem.findall("DataRef"):
                if data_ref_elem.text and data_ref_elem.text.strip():
                    input_data_refs.append(data_ref_elem.text.strip())

        # Collect remaining config elements
        config_dict = _section_to_dict(
            append_task_section, exclude={"Parent", "InputDataRefs"}
        )
        if config_dict:
            task_config = config_dict

    return AppendTaskElement(
        metadata=metadata,
        submitable=submitable,
        parent_id=parent_id,
        input_data_refs=input_data_refs,
        task_config=task_config,
    )


def _parse_task_config_xml(xml_content: str, element_id: str, task_type: str) -> dict:
    """Parse a task configuration XML file into a dict structure.

    Args:
        xml_content: Raw XML string from the archive.
        element_id: The element ID (for error messages).
        task_type: The task type name (for error messages).

    Returns:
        Dict representation of the parsed XML.

    Raises:
        ValueError: If the XML is malformed or unreadable.
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        raise ValueError(
            f"{task_type} '{element_id}': Task_Config XML is malformed: {e}"
        ) from e

    return _element_to_dict(root)


def _element_to_dict(element: ET.Element) -> dict:
    """Recursively convert an XML element to a dict structure.

    Attributes are stored with '@' prefix. Text content stored as '#text'.
    Child elements are nested dicts or lists of dicts for repeated tags.
    """
    result: dict = {}

    # Add attributes
    if element.attrib:
        for key, value in element.attrib.items():
            result[f"@{key}"] = value

    # Add text content
    if element.text and element.text.strip():
        result["#text"] = element.text.strip()

    # Add child elements
    children: dict[str, list] = {}
    for child in element:
        child_dict = _element_to_dict(child)
        tag = child.tag
        if tag not in children:
            children[tag] = []
        children[tag].append(child_dict)

    # Flatten single-element lists
    for tag, items in children.items():
        if len(items) == 1:
            result[tag] = items[0]
        else:
            result[tag] = items

    return result


def _section_to_dict(section: ET.Element, exclude: set[str] | None = None) -> dict:
    """Convert child elements of a section to a flat dict.

    Extracts text content from immediate children, skipping those
    in the exclude set.

    Args:
        section: Parent XML element whose children to extract.
        exclude: Set of child tag names to skip.

    Returns:
        Dict mapping tag names to text values.
    """
    if exclude is None:
        exclude = set()

    result: dict = {}
    for child in section:
        if child.tag in exclude:
            continue
        if child.text and child.text.strip():
            result[child.tag] = child.text.strip()
        elif len(child) > 0:
            # Has sub-elements, convert recursively
            result[child.tag] = _element_to_dict(child)
    return result
