"""Parser for project.xml content from EGP archives.

Extracts project-level metadata, settings, parameters, application overrides,
and metadata info from the ProjectCollection root element and its child sections.

Raises ValueError for malformed XML that cannot be parsed.
All absent optional fields default to None per requirement 2.7.
"""

import xml.etree.ElementTree as ET
from typing import Any

from pyegp_parser.models.project import (
    Parameter,
    ParsedProject,
    ProjectMetadata,
    ProjectSettings,
)


def parse_project_xml(xml_content: str) -> ParsedProject:
    """Parse project.xml content into a ParsedProject.

    Args:
        xml_content: The raw XML string from project.xml.

    Returns:
        ParsedProject populated with metadata, settings, parameters,
        application_overrides, and metadata_info.

    Raises:
        ValueError: If the XML content is malformed and cannot be parsed.
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        raise ValueError(f"Malformed XML: {e}") from e

    metadata = _parse_metadata(root)
    settings = _parse_settings(root)
    parameters = _parse_parameters(root)
    application_overrides = _parse_application_overrides(root)
    metadata_info = _parse_metadata_info(root)

    return ParsedProject(
        metadata=metadata,
        settings=settings,
        parameters=parameters,
        application_overrides=application_overrides,
        metadata_info=metadata_info,
    )


def _parse_metadata(root: ET.Element) -> ProjectMetadata:
    """Extract metadata from the ProjectCollection root and its Element child.

    Reads EGVersion and Type from root attributes, then looks for project
    metadata in two possible locations:
    1. EGP 8.x: Direct <Element> child of root with metadata as child text elements
       (e.g. <ProjectCollection><Element><Label>...</Label></Element></ProjectCollection>)
    2. Legacy: First <Element> inside <Elements> section with metadata as attributes
       (e.g. <Elements><Element Label="..." ID="..."/></Elements>)
    """
    eg_version = root.get("EGVersion")
    project_type = root.get("Type")

    label = None
    element_id = None
    created_on = None
    modified_on = None
    modified_by = None
    modified_by_eg_id = None
    modified_by_eg_ver = None

    # Strategy 1: EGP 8.x — direct <Element> child of root with child text elements
    root_element = root.find("Element")
    if root_element is not None:
        # Check if this Element has child text elements (8.x layout)
        label = _get_text(root_element, "Label")
        element_id = _get_text(root_element, "ID")
        created_on = _get_text(root_element, "CreatedOn")
        modified_on = _get_text(root_element, "ModifiedOn")
        modified_by = _get_text(root_element, "ModifiedBy")
        modified_by_eg_id = _get_text(root_element, "ModifiedByEGID")
        modified_by_eg_ver = _get_text(root_element, "ModifiedByEGVer")

    # Strategy 2: Legacy — if root <Element> didn't yield metadata, try Elements/Element
    if label is None and element_id is None:
        elements_section = root.find("Elements")
        if elements_section is not None:
            first_element = elements_section.find("Element")
            if first_element is not None:
                # Try attributes (legacy format)
                label = first_element.get("Label") or _get_text(first_element, "Label")
                element_id = first_element.get("ID") or _get_text(first_element, "ID")
                created_on = first_element.get("CreatedOn") or _get_text(
                    first_element, "CreatedOn"
                )
                modified_on = first_element.get("ModifiedOn") or _get_text(
                    first_element, "ModifiedOn"
                )
                modified_by = first_element.get("ModifiedBy") or _get_text(
                    first_element, "ModifiedBy"
                )
                modified_by_eg_id = first_element.get("ModifiedByEGID") or _get_text(
                    first_element, "ModifiedByEGID"
                )
                modified_by_eg_ver = first_element.get("ModifiedByEGVer") or _get_text(
                    first_element, "ModifiedByEGVer"
                )

    return ProjectMetadata(
        eg_version=eg_version,
        type=project_type,
        label=label,
        id=element_id,
        created_on=created_on,
        modified_on=modified_on,
        modified_by=modified_by,
        modified_by_eg_id=modified_by_eg_id,
        modified_by_eg_ver=modified_by_eg_ver,
    )


def _parse_settings(root: ET.Element) -> ProjectSettings:
    """Extract project settings from the XML.

    EGP 8.x stores settings as direct child elements of the root
    (e.g. <UseRelativePaths>false</UseRelativePaths>).
    Legacy format may use a <ProjectSettings> wrapper section.

    Converts boolean string values ("True"/"False") to Python bools,
    integer strings to int, and preserves string values as-is.
    """
    # Try legacy format first (settings wrapped in a ProjectSettings section);
    # in EGP 8.x settings are direct children of root.
    settings_elem = root.find("ProjectSettings")
    source = settings_elem if settings_elem is not None else root

    return ProjectSettings(
        use_relative_paths=_get_bool(source, "UseRelativePaths"),
        submit_to_grid=_get_bool(source, "SubmitToGrid"),
        queue_submits_for_server=_get_bool(source, "QueueSubmitsForServer"),
        action_on_error=_get_text(source, "ActionOnError"),
        show_project_log_warning_message=_get_bool(
            source, "ShowProjectLogWarningMessage"
        ),
        remove_older_project_log_items=_get_bool(source, "RemoveOlderProjectLogItems"),
        export_project_log_then_clear=_get_bool(source, "ExportProjectLogThenClear"),
        project_log_export_filename=_get_text(source, "ProjectLogExportFilename"),
        project_log_export_location=_get_text(source, "ProjectLogExportLocation"),
        project_log_max_size=_get_int(source, "ProjectLogMaxSize"),
        clear_project_log_on_exit=_get_bool(source, "ClearProjectLogOnExit"),
    )


def _parse_parameters(root: ET.Element) -> list[Parameter]:
    """Extract parameters from the Parameters collection.

    Each Parameter element has Name and Value attributes.
    """
    params_section = root.find("Parameters")
    if params_section is None:
        return []

    parameters = []
    for param_elem in params_section.findall("Parameter"):
        name = param_elem.get("Name")
        value = param_elem.get("Value")
        if name is not None and value is not None:
            parameters.append(Parameter(name=name, value=value))

    return parameters


def _parse_application_overrides(root: ET.Element) -> dict[str, Any] | None:
    """Extract ApplicationOverrides section as a structured dict.

    Preserves all child elements and attributes. Returns None if the
    section is absent.
    """
    overrides_elem = root.find("ApplicationOverrides")
    if overrides_elem is None:
        return None

    return _element_to_dict(overrides_elem)


def _parse_metadata_info(root: ET.Element) -> dict[str, str | None] | None:
    """Extract MetaDataInfo section fields.

    Extracts MetaDataProviderName, MetaDataHost, and MetaDataPort.
    Returns None if the section is absent.
    """
    info_elem = root.find("MetaDataInfo")
    if info_elem is None:
        return None

    return {
        "metadata_provider_name": _get_text(info_elem, "MetaDataProviderName"),
        "metadata_host": _get_text(info_elem, "MetaDataHost"),
        "metadata_port": _get_text(info_elem, "MetaDataPort"),
    }


# --- Helper functions ---


def _get_text(parent: ET.Element, tag: str) -> str | None:
    """Get text content of a child element, returning None if absent or empty."""
    child = parent.find(tag)
    if child is None or child.text is None or child.text.strip() == "":
        return None
    return child.text.strip()


def _get_bool(parent: ET.Element, tag: str) -> bool | None:
    """Get a boolean value from a child element's text content.

    Converts "True"/"False" strings (case-insensitive) to Python bools.
    Returns None if the element is absent or has no text.
    """
    text = _get_text(parent, tag)
    if text is None:
        return None
    return text.lower() == "true"


def _get_int(parent: ET.Element, tag: str) -> int | None:
    """Get an integer value from a child element's text content.

    Returns None if the element is absent, has no text, or cannot be
    converted to an integer.
    """
    text = _get_text(parent, tag)
    if text is None:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _element_to_dict(elem: ET.Element) -> dict[str, Any]:
    """Recursively convert an XML element to a dictionary representation.

    Preserves attributes, text content, and child elements as nested dicts.
    """
    result: dict[str, Any] = {}

    # Include attributes
    if elem.attrib:
        result["_attributes"] = dict(elem.attrib)

    # Include text content
    if elem.text and elem.text.strip():
        result["_text"] = elem.text.strip()

    # Include child elements
    children: dict[str, Any] = {}
    for child in elem:
        child_dict = _element_to_dict(child)
        tag = child.tag
        if tag in children:
            # Convert to list if multiple children with same tag
            if not isinstance(children[tag], list):
                children[tag] = [children[tag]]
            children[tag].append(child_dict)
        else:
            children[tag] = child_dict

    result.update(children)
    return result
