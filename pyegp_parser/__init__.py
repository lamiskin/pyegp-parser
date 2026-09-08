"""EGP Parser — Parse SAS Enterprise Guide .egp project files into structured JSON."""

import datetime
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .models.bulk import BulkResult
from .models.log_code import LogElement
from .models.project import ParsedProject

__version__ = "0.1.2"

logger = logging.getLogger(__name__)


def parse_file(
    egp_path: str | Path,
    output_dir: str | Path | None = None,
) -> ParsedProject:
    """Parse a single .egp file into a structured project object.

    Opens the archive, parses project.xml, extracts all elements and artifacts,
    validates completeness, and optionally writes JSON output.

    Args:
        egp_path: Path to the .egp file to parse.
        output_dir: Optional directory for JSON output. If None, no file is written.

    Returns:
        A ParsedProject dataclass instance containing all extracted data.

    Raises:
        FileNotFoundError: If egp_path does not exist.
        ValueError: If file is not a valid EGP archive.
    """
    from .archive import open_archive
    from .models.elements import ElementCategory
    from .models.process_flow import ProcessFlowContainer
    from .models.project import ParsedProject, SourceInfo
    from .parsers.data_parser import parse_data_list, parse_external_file_list
    from .parsers.element_parser import parse_elements
    from .parsers.external_objects_parser import parse_external_objects
    from .parsers.layout_parser import parse_open_project_view, parse_visual_layout
    from .parsers.log_code_parser import (
        extract_execution_logs,
        extract_project_log,
        parse_code_element,
        parse_log_element,
    )
    from .parsers.ods_parser import (
        extract_ods_results,
        match_ods_results_to_tasks,
    )
    from .parsers.pfd_parser import parse_process_flow
    from .parsers.project_parser import parse_project_xml
    from .parsers.query_parser import parse_query
    from .parsers.shortcut_parser import parse_shortcut
    from .parsers.task_parser import (
        parse_append_task,
        parse_code_task,
        parse_eg_task,
        parse_export_task,
        parse_import_task,
    )
    from .serializer import serialize_project
    from .validator import validate_completeness

    path = Path(egp_path).resolve()

    # Step 1: Open and validate the archive
    inventory = open_archive(path)
    try:
        # Track which paths we process for completeness validation
        processed_paths: set[str] = set()

        # Step 2: Read project.xml (handling UTF-8, UTF-16, BOM encodings)
        xml_content = _read_project_xml(inventory)
        processed_paths.add("project.xml")

        # Parse the XML root for sub-parsers that need it
        root = ET.fromstring(xml_content)

        # Step 3: Parse project metadata via project_parser
        partial_project = parse_project_xml(xml_content)

        # Step 4: Parse data list
        data_list = parse_data_list(root)

        # Step 5: Parse external files (catch ValueError for malformed DNA)
        external_files: list = []
        try:
            external_files = parse_external_file_list(root)
        except ValueError as e:
            logger.warning("Malformed external file DNA: %s", e)

        # Step 6: Parse elements
        parsed_elements = parse_elements(root)

        # Step 6b: Invoke typed parsers for each element category.
        # ValueError from typed parsers propagates to the caller — no silent
        # error swallowing. This ensures missing required sections are surfaced
        # rather than silently producing incomplete output.
        queries: list = []
        tasks: list = []
        shortcuts: list = []
        log_elements_list: list = []
        code_elements_list: list = []

        for elem in parsed_elements:
            if elem.category == ElementCategory.QUERY:
                submitable, query_model = parse_query(elem.xml_node)
                queries.append(
                    {
                        "metadata": elem.metadata,
                        "submitable": submitable,
                        "query_model": query_model,
                    }
                )
            elif elem.category == ElementCategory.IMPORT_TASK:
                # `result` is rebound to several element types across branches.
                result: Any = parse_import_task(
                    elem.xml_node, elem.metadata, archive=inventory
                )
                tasks.append(result)
            elif elem.category == ElementCategory.CODE_TASK:
                result = parse_code_task(
                    elem.xml_node, elem.metadata, archive=inventory
                )
                tasks.append(result)
            elif elem.category == ElementCategory.EG_TASK:
                result = parse_eg_task(elem.xml_node, elem.metadata, archive=inventory)
                tasks.append(result)
            elif elem.category == ElementCategory.EXPORT_TASK:
                result = parse_export_task(elem.xml_node, elem.metadata)
                tasks.append(result)
            elif elem.category == ElementCategory.APPEND_TASK:
                result = parse_append_task(elem.xml_node, elem.metadata)
                tasks.append(result)
            elif elem.category == ElementCategory.SHORTCUT_TO_DATA:
                result = parse_shortcut(elem.xml_node, elem.metadata, is_data=True)
                shortcuts.append(result)
            elif elem.category == ElementCategory.SHORTCUT_TO_FILE:
                result = parse_shortcut(elem.xml_node, elem.metadata, is_data=False)
                shortcuts.append(result)
            elif elem.category == ElementCategory.LOG:
                try:
                    result = parse_log_element(elem.xml_node, elem.metadata)
                except ValueError as e:
                    logger.warning(
                        "Failed to parse log element '%s': %s", elem.metadata.id, e
                    )
                    # Still record the element, without its display settings.
                    result = LogElement(metadata=elem.metadata)
                log_elements_list.append(result)
            elif elem.category == ElementCategory.CODE:
                result = parse_code_element(elem.xml_node, elem.metadata)
                code_elements_list.append(result)

        # Step 6c: Parse External_Objects section (ValueError propagates)
        external_objects = parse_external_objects(root)

        # Step 7: Parse process flow containers and build DAGs
        containers: list[ProcessFlowContainer] = []
        for elem in parsed_elements:
            if elem.category == ElementCategory.PROCESS_FLOW_CONTAINER:
                try:
                    dag_model = parse_process_flow(elem.xml_node)
                    containers.append(
                        ProcessFlowContainer(
                            metadata=elem.metadata,
                            dag=dag_model,
                        )
                    )
                except ValueError as e:
                    logger.warning(
                        "Failed to parse process flow for element '%s': %s",
                        elem.metadata.id,
                        e,
                    )
                    # Still record the container without a DAG
                    containers.append(
                        ProcessFlowContainer(metadata=elem.metadata, dag=None)
                    )

        # Step 8: Extract execution logs. NOTE: extraction is invoked to validate
        # the log entries (and mark them processed below), but the returned logs
        # are not currently attached to the ParsedProject.
        try:
            extract_execution_logs(inventory)
            # Mark log paths as processed
            from .archive import EntryCategory

            for entry in inventory.entries:
                if entry.category == EntryCategory.EXECUTION_LOG:
                    processed_paths.add(entry.path)
        except ValueError as e:
            logger.warning("Failed to extract execution logs: %s", e)

        # Step 9: Extract project log (catch ValueError for missing ProjectLog)
        project_log = None
        try:
            project_log = extract_project_log(inventory, root)
            # Mark project log paths as processed
            from .archive import EntryCategory

            for entry in inventory.entries:
                if entry.category == EntryCategory.PROJECT_LOG:
                    processed_paths.add(entry.path)
        except ValueError as e:
            logger.warning("Missing or invalid project log: %s", e)

        # Step 10: Extract ODS results
        ods_entries = extract_ods_results(inventory)
        ods_entries = match_ods_results_to_tasks(ods_entries, parsed_elements)
        # Mark ODS paths as processed
        from .archive import EntryCategory

        for entry in inventory.entries:
            if entry.category == EntryCategory.ODS_RESULT:
                processed_paths.add(entry.path)

        # Also mark task configs, code files as processed
        for entry in inventory.entries:
            if entry.category in (
                EntryCategory.TASK_CONFIG,
                EntryCategory.CODE_FILE,
            ):
                processed_paths.add(entry.path)

        # Step 11: Parse visual layout
        element_ids = {
            elem.metadata.id for elem in parsed_elements if elem.metadata.id is not None
        }
        visual_layout = parse_visual_layout(root, element_ids=element_ids)
        open_project_view = parse_open_project_view(root)

        # Step 12: Validate completeness
        completeness_summary, unprocessed_entries, completeness_warning = (
            validate_completeness(inventory, processed_paths)
        )

        # Step 13: Build source info (Req 15.16, 15.17)
        source = SourceInfo(
            file_path=str(path),
            file_name=path.name,
            file_size_bytes=path.stat().st_size,
            parsed_at=datetime.datetime.now().isoformat(),
            total_zip_entries=len(inventory.entries),
        )

        # Assemble the full ParsedProject with all sections populated
        # Convert ParsedElement objects to their metadata for serialization
        # (ParsedElement contains xml_node which is not JSON-serializable)
        serializable_elements = [elem.metadata for elem in parsed_elements]

        project = ParsedProject(
            source=source,
            metadata=partial_project.metadata,
            settings=partial_project.settings,
            data_list=data_list,
            external_files=external_files,
            elements=serializable_elements,
            containers=containers,
            parameters=partial_project.parameters,
            project_log=project_log,
            visual_layout=visual_layout,
            completeness_summary=completeness_summary,
            unprocessed_entries=unprocessed_entries,
            completeness_warning=completeness_warning,
            binary_entries=ods_entries,
            application_overrides=partial_project.application_overrides,
            metadata_info=partial_project.metadata_info,
            open_project_view=open_project_view,
            queries=queries,
            tasks=tasks,
            shortcuts=shortcuts,
            log_elements=log_elements_list,
            code_elements=code_elements_list,
            external_objects=external_objects,
        )

        # Step 14: Write output if output_dir is specified (Req 15.6)
        if output_dir is not None:
            out_path = Path(output_dir)
            serialize_project(project, out_path)

        return project
    finally:
        inventory.close()


def _read_project_xml(inventory) -> str:
    """Read project.xml from the archive, handling UTF-8, UTF-16, and BOM encodings.

    Tries UTF-8 first, then falls back to UTF-16 and UTF-8-sig (BOM) if needed.

    Args:
        inventory: The open ArchiveInventory.

    Returns:
        The decoded XML content string.

    Raises:
        ValueError: If project.xml cannot be decoded with any supported encoding.
    """
    raw_bytes = inventory.get_bytes("project.xml")

    # Try UTF-8 BOM first (utf-8-sig handles BOM transparently)
    if raw_bytes.startswith(b"\xef\xbb\xbf"):
        return raw_bytes.decode("utf-8-sig")

    # Try UTF-16 BOM (both LE and BE)
    if raw_bytes.startswith(b"\xff\xfe") or raw_bytes.startswith(b"\xfe\xff"):
        return raw_bytes.decode("utf-16")

    # Default: try UTF-8
    try:
        return raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        pass

    # Fallback: try UTF-16 without BOM
    try:
        return raw_bytes.decode("utf-16")
    except UnicodeDecodeError:
        pass

    raise ValueError(
        "project.xml cannot be decoded: tried UTF-8, UTF-8-sig, and UTF-16"
    )


def parse_directory(
    directory: str | Path,
    output_dir: str | Path | None = None,
) -> BulkResult:
    """Parse all .egp files in a directory recursively.

    Discovers .egp files, parses each independently, and returns a structured
    result with successes, failures, and summary counts.

    Args:
        directory: Root directory to search for .egp files.
        output_dir: Optional directory for JSON output. If None, no file is written.

    Returns:
        A BulkResult dataclass instance with successes, failures, and summary.

    Raises:
        ValueError: If directory does not exist or is not a directory.
    """
    from .bulk import process_directory

    return process_directory(directory, output_dir=output_dir)
