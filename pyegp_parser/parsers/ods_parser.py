"""ODS results and binary entry tracking for EGP archives.

This module extracts ODS result entries and unknown/unclassified binary entries
from the archive inventory, recording their metadata (path, compressed size,
file extension) without extracting binary content to disk.

ODS results are matched to their owning tasks via the JobRecipe ODSResultsList
found in each task's SubmitableElement section.
"""

import os
import re
from typing import Any

from ..archive import ArchiveEntry, ArchiveInventory, EntryCategory
from ..models.project import BinaryEntry, UnprocessedEntry

# Regex to extract the ODS Result ID from the archive path
_ODS_RESULT_ID_PATTERN = re.compile(r"^ODSResults/ODSResult-(?P<id>[A-Za-z0-9]+)/.*$")


def extract_ods_results(
    inventory: ArchiveInventory,
) -> list[BinaryEntry]:
    """Extract ODS result entries from the archive inventory.

    Records each ODS_Result entry with its archive path, compressed size,
    and file extension. Does NOT extract binary content to disk.

    Args:
        inventory: The archive inventory with classified entries.

    Returns:
        List of BinaryEntry objects for all ODS_Result archive entries.

    Raises:
        ValueError: If an ODS_Result entry has corrupt/unreadable metadata
            (e.g., negative compressed size or missing path information).
    """
    ods_entries: list[BinaryEntry] = []

    for entry in inventory.entries:
        if entry.category != EntryCategory.ODS_RESULT:
            continue

        # Validate entry metadata
        _validate_entry_metadata(entry)

        # Extract file extension from the path
        file_extension = _get_file_extension(entry.path)

        ods_entries.append(
            BinaryEntry(
                path=entry.path,
                compressed_size=entry.compressed_size,
                file_extension=file_extension,
                task_id=None,  # Will be matched later
            )
        )

    return ods_entries


def extract_unknown_entries(
    inventory: ArchiveInventory,
) -> list[UnprocessedEntry]:
    """Extract unknown/unclassified entries from the archive inventory.

    Records entries that are not classified as project_xml, task_config,
    code_file, execution_log, project_log, ods_result, or empty_directory.

    Args:
        inventory: The archive inventory with classified entries.

    Returns:
        List of UnprocessedEntry objects for all UNKNOWN category entries.
    """
    unknown_entries: list[UnprocessedEntry] = []

    for entry in inventory.entries:
        if entry.category != EntryCategory.UNKNOWN:
            continue

        unknown_entries.append(
            UnprocessedEntry(
                path=entry.path,
                compressed_size=entry.compressed_size,
            )
        )

    return unknown_entries


def match_ods_results_to_tasks(
    ods_entries: list[BinaryEntry],
    elements: list[Any],
) -> list[BinaryEntry]:
    """Match ODS result entries to their owning tasks via JobRecipe ODSResultsList.

    For each ODS result entry, extracts the ODS Result ID from the archive path
    and looks for a matching ID in any task's JobRecipe ODSResultsList.

    Args:
        ods_entries: List of BinaryEntry objects for ODS results.
        elements: List of parsed element objects (tasks) that may contain
            a `submitable` attribute with a `job_recipe` dict.

    Returns:
        Updated list of BinaryEntry objects with task_id populated where
        a match was found. Entries without a match retain task_id=None.
    """
    # Build a mapping from ODS Result ID → task element ID
    ods_id_to_task_id: dict[str, str] = {}

    for element in elements:
        submitable = getattr(element, "submitable", None)
        if submitable is None:
            continue

        job_recipe = getattr(submitable, "job_recipe", None)
        if job_recipe is None or not isinstance(job_recipe, dict):
            continue

        ods_results_list = job_recipe.get("ODSResultsList")
        if not ods_results_list or not isinstance(ods_results_list, list):
            continue

        # Get the owning element's ID
        element_metadata = getattr(element, "metadata", None)
        if element_metadata is None:
            continue
        element_id = getattr(element_metadata, "id", None)
        if element_id is None:
            continue

        for ods_item in ods_results_list:
            if isinstance(ods_item, dict):
                ods_id = ods_item.get("ID")
                if ods_id:
                    ods_id_to_task_id[ods_id] = element_id

    # Match each ODS entry to its task
    matched_entries: list[BinaryEntry] = []
    for entry in ods_entries:
        task_id = _find_task_id_for_entry(entry.path, ods_id_to_task_id)
        matched_entries.append(
            BinaryEntry(
                path=entry.path,
                compressed_size=entry.compressed_size,
                file_extension=entry.file_extension,
                task_id=task_id,
            )
        )

    return matched_entries


def _find_task_id_for_entry(path: str, ods_id_to_task_id: dict[str, str]) -> str | None:
    """Extract the ODS Result ID from a path and look up the associated task.

    Args:
        path: The archive path (e.g., "ODSResults/ODSResult-ABC123/result.pptx").
        ods_id_to_task_id: Mapping from ODS Result ID to task element ID.

    Returns:
        The task element ID if matched, otherwise None.
    """
    match = _ODS_RESULT_ID_PATTERN.match(path)
    if match is None:
        return None

    ods_id = match.group("id")
    return ods_id_to_task_id.get(ods_id)


def _validate_entry_metadata(entry: ArchiveEntry) -> None:
    """Validate that an archive entry has readable metadata.

    Args:
        entry: The archive entry to validate.

    Raises:
        ValueError: If the entry metadata is corrupt or unreadable
            (empty path or negative compressed size).
    """
    if not entry.path:
        raise ValueError("Corrupt ZIP entry metadata: entry has empty path")
    if entry.compressed_size < 0:
        raise ValueError(
            f"Corrupt ZIP entry metadata: entry '{entry.path}' has "
            f"negative compressed size ({entry.compressed_size})"
        )


def _get_file_extension(path: str) -> str:
    """Extract file extension from a path, including the dot.

    Args:
        path: File path string.

    Returns:
        The file extension including the dot (e.g., ".pptx"),
        or empty string if no extension.
    """
    _, ext = os.path.splitext(path)
    return ext
