"""Property-based tests for completeness accounting validation.

**Validates: Requirements 18.1, 18.2, 18.3, 18.4**

Uses Hypothesis to verify that:
- total_entries equals the number of entries in the inventory
- processed + unprocessed equals total
- completeness_warning is True iff unprocessed_entries > 0
- empty directory entries are always counted as processed regardless of processed_paths
"""

import string
from unittest.mock import MagicMock

from hypothesis import given, settings
from hypothesis import strategies as st

from pyegp_parser.archive import ArchiveEntry, ArchiveInventory, EntryCategory
from pyegp_parser.validator import validate_completeness

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Valid path characters for generated archive paths
_path_segment = st.text(
    alphabet=string.ascii_letters + string.digits + "_-.",
    min_size=1,
    max_size=30,
)

# Strategy for generating archive paths (non-directory)
_file_path = st.builds(
    lambda seg1, seg2: f"{seg1}/{seg2}",
    _path_segment,
    _path_segment,
)

# Strategy for generating directory paths (ending with '/')
_dir_path = st.builds(
    lambda seg: f"{seg}/",
    _path_segment,
)

# Strategy for entry categories excluding EMPTY_DIRECTORY
_non_dir_category = st.sampled_from(
    [cat for cat in EntryCategory if cat != EntryCategory.EMPTY_DIRECTORY]
)

# Strategy for compressed/uncompressed sizes
_size = st.integers(min_value=0, max_value=10_000_000)


# Strategy for non-directory ArchiveEntry objects
_file_entry = st.builds(
    ArchiveEntry,
    path=_file_path,
    category=_non_dir_category,
    compressed_size=_size,
    uncompressed_size=_size,
)

# Strategy for directory ArchiveEntry objects (always EMPTY_DIRECTORY category)
_dir_entry = st.builds(
    ArchiveEntry,
    path=_dir_path,
    category=st.just(EntryCategory.EMPTY_DIRECTORY),
    compressed_size=st.just(0),
    uncompressed_size=st.just(0),
)

# Strategy for mixed lists of entries (both files and directories)
_entry_list = st.lists(
    st.one_of(_file_entry, _dir_entry),
    min_size=0,
    max_size=50,
)


# ---------------------------------------------------------------------------
# Property 12: Completeness Accounting
# ---------------------------------------------------------------------------


class TestCompletenessAccounting:
    """**Validates: Requirements 18.1, 18.2, 18.3, 18.4**"""

    @given(
        entries=_entry_list,
        data=st.data(),
    )
    @settings(max_examples=100)
    def test_total_entries_equals_inventory_count(
        self, entries: list[ArchiveEntry], data
    ):
        """total_entries in the summary must equal len(inventory.entries).

        Validates Requirement 18.3: completeness_summary.total_entries equals
        total ZIP entries in the archive.
        """
        # Build inventory with a mock zip_file
        inventory = ArchiveInventory(entries=entries, zip_file=MagicMock())

        # Generate a random subset of file entry paths as processed
        file_paths = [
            e.path for e in entries if e.category != EntryCategory.EMPTY_DIRECTORY
        ]
        if file_paths:
            processed_subset = data.draw(
                st.sets(
                    st.sampled_from(file_paths), min_size=0, max_size=len(file_paths)
                )
            )
        else:
            processed_subset = set()

        summary, unprocessed_list, warning = validate_completeness(
            inventory, processed_subset
        )

        assert summary.total_entries == len(entries), (
            f"Expected total_entries={len(entries)}, got {summary.total_entries}"
        )

    @given(
        entries=_entry_list,
        data=st.data(),
    )
    @settings(max_examples=100)
    def test_processed_plus_unprocessed_equals_total(
        self, entries: list[ArchiveEntry], data
    ):
        """processed_entries + unprocessed_entries must equal total_entries.

        Validates Requirements 18.1, 18.3: the accounting identity holds for
        every possible combination of entries and processed paths.
        """
        inventory = ArchiveInventory(entries=entries, zip_file=MagicMock())

        file_paths = [
            e.path for e in entries if e.category != EntryCategory.EMPTY_DIRECTORY
        ]
        if file_paths:
            processed_subset = data.draw(
                st.sets(
                    st.sampled_from(file_paths), min_size=0, max_size=len(file_paths)
                )
            )
        else:
            processed_subset = set()

        summary, unprocessed_list, warning = validate_completeness(
            inventory, processed_subset
        )

        assert (
            summary.processed_entries + summary.unprocessed_entries
            == summary.total_entries
        ), (
            f"Accounting mismatch: {summary.processed_entries} + "
            f"{summary.unprocessed_entries} != {summary.total_entries}"
        )

    @given(
        entries=_entry_list,
        data=st.data(),
    )
    @settings(max_examples=100)
    def test_warning_flag_matches_unprocessed_count(
        self, entries: list[ArchiveEntry], data
    ):
        """completeness_warning is True iff unprocessed_entries > 0.

        Validates Requirements 18.2, 18.4: warning is set when entries are
        unprocessed and cleared when all entries are accounted for.
        """
        inventory = ArchiveInventory(entries=entries, zip_file=MagicMock())

        file_paths = [
            e.path for e in entries if e.category != EntryCategory.EMPTY_DIRECTORY
        ]
        if file_paths:
            processed_subset = data.draw(
                st.sets(
                    st.sampled_from(file_paths), min_size=0, max_size=len(file_paths)
                )
            )
        else:
            processed_subset = set()

        summary, unprocessed_list, warning = validate_completeness(
            inventory, processed_subset
        )

        if summary.unprocessed_entries > 0:
            assert warning is True, (
                f"Expected warning=True when unprocessed_entries="
                f"{summary.unprocessed_entries}"
            )
        else:
            assert warning is False, (
                "Expected warning=False when all entries are processed"
            )

    @given(
        entries=st.lists(_dir_entry, min_size=1, max_size=20),
    )
    @settings(max_examples=100)
    def test_empty_directories_always_counted_as_processed(
        self, entries: list[ArchiveEntry]
    ):
        """Empty directory entries are always processed regardless of processed_paths.

        Validates Requirement 18.1: entries classified as EMPTY_DIRECTORY are
        automatically counted as processed since they carry no file content.
        """
        inventory = ArchiveInventory(entries=entries, zip_file=MagicMock())

        # Pass an empty set — no paths explicitly processed
        summary, unprocessed_list, warning = validate_completeness(inventory, set())

        # All directory entries should be processed
        assert summary.processed_entries == len(entries), (
            f"Expected all {len(entries)} directory entries to be processed, "
            f"got {summary.processed_entries}"
        )
        assert summary.unprocessed_entries == 0, (
            f"Expected 0 unprocessed entries for all-directory inventory, "
            f"got {summary.unprocessed_entries}"
        )
        assert warning is False, (
            "Expected no warning when all entries are empty directories"
        )
        # Verify none of the directory entries appear in unprocessed list
        assert len(unprocessed_list) == 0, (
            f"Directory entries should not appear in unprocessed list, "
            f"found {len(unprocessed_list)}"
        )
