"""Completeness validation for EGP archive parsing.

Compares the full set of archive entry paths against paths that were
explicitly processed during parsing, producing a summary of coverage
and flagging any unprocessed entries.
"""

from .archive import ArchiveInventory, EntryCategory
from .models.project import CompletenessSummary, UnprocessedEntry


def validate_completeness(
    inventory: ArchiveInventory,
    processed_paths: set[str],
) -> tuple[CompletenessSummary, list[UnprocessedEntry], bool]:
    """Compare archive inventory against processed paths.

    Empty directory entries (paths ending with '/') are automatically
    counted as processed since they carry no file content.

    Args:
        inventory: The full archive inventory with all entries classified.
        processed_paths: Set of archive paths that were explicitly processed
            during parsing.

    Returns:
        Tuple of (summary, unprocessed_entries_list, completeness_warning_flag).
        The warning flag is True if any entries were unprocessed.
    """
    total_entries = len(inventory.entries)
    unprocessed_list: list[UnprocessedEntry] = []

    for entry in inventory.entries:
        # Empty directory entries are automatically considered processed
        if entry.category == EntryCategory.EMPTY_DIRECTORY:
            continue
        if entry.path not in processed_paths:
            unprocessed_list.append(
                UnprocessedEntry(
                    path=entry.path,
                    compressed_size=entry.compressed_size,
                )
            )

    processed_count = total_entries - len(unprocessed_list)
    unprocessed_count = len(unprocessed_list)

    summary = CompletenessSummary(
        total_entries=total_entries,
        processed_entries=processed_count,
        unprocessed_entries=unprocessed_count,
    )

    completeness_warning = unprocessed_count > 0

    return summary, unprocessed_list, completeness_warning
