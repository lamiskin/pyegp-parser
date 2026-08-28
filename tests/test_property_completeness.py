"""Property-based tests for completeness accounting.

**Validates: Requirements 18.1, 18.2, 18.3, 18.4**

Uses Hypothesis to verify that the completeness validator correctly accounts
for all archive entries: total_entries equals ZIP count, and
processed + unprocessed equals total. Also verifies the completeness_warning
flag is set correctly (True when unprocessed > 0).
"""

import string

from hypothesis import given, settings
from hypothesis import strategies as st

from pyegp_parser.archive import ArchiveEntry, ArchiveInventory
from pyegp_parser.classifier import classify_entry
from pyegp_parser.validator import validate_completeness

# ---------------------------------------------------------------------------
# Strategies for generating archive entries
# ---------------------------------------------------------------------------

# Alphanumeric IDs used in EGP archives
_entry_id = st.text(
    alphabet=string.ascii_letters + string.digits,
    min_size=1,
    max_size=12,
)

# Task types used in EGP archives
_task_type = st.sampled_from(
    [
        "ImportTask",
        "ExportTask",
        "CodeTask",
        "EGTask",
        "AppendTask",
        "QueryTask",
    ]
)

# Strategy for generating paths with known categories
_project_xml_path = st.just("project.xml")

_task_config_path = st.builds(
    lambda tt, eid: f"{tt}-{eid}/{tt}-{eid}.xml",
    _task_type,
    _entry_id,
)

_code_file_path = st.builds(
    lambda eid: f"CodeTask-{eid}/code.sas",
    _entry_id,
)

_execution_log_path = st.builds(
    lambda tt, tid, lid: f"{tt}-{tid}/Log-{lid}/result.log",
    _task_type,
    _entry_id,
    _entry_id,
)

_project_log_path = st.builds(
    lambda eid: f"ProjectLog-{eid}/ProjectLog-{eid}/result.log",
    _entry_id,
)

_ods_result_path = st.builds(
    lambda eid, ext: f"ODSResults/ODSResult-{eid}/result.{ext}",
    _entry_id,
    st.sampled_from(["html", "pdf", "rtf", "pptx", "xlsx"]),
)

_empty_dir_path = st.builds(
    lambda seg: f"{seg}/",
    st.text(
        alphabet=string.ascii_letters + string.digits + "_-",
        min_size=1,
        max_size=20,
    ),
)

_unknown_path = st.builds(
    lambda name, ext: f"misc/{name}.{ext}",
    st.text(alphabet=string.ascii_letters + string.digits, min_size=1, max_size=20),
    st.sampled_from(["dat", "bin", "tmp", "cfg", "bak"]),
)

# Combined entry path strategy mixing various categories
_any_entry_path = st.one_of(
    _project_xml_path,
    _task_config_path,
    _code_file_path,
    _execution_log_path,
    _project_log_path,
    _ods_result_path,
    _empty_dir_path,
    _unknown_path,
)

# Strategy for compressed size
_compressed_size = st.integers(min_value=0, max_value=100_000)


def _make_archive_entry(path: str, compressed_size: int) -> ArchiveEntry:
    """Create an ArchiveEntry with classification from the classifier."""
    category = classify_entry(path)
    return ArchiveEntry(
        path=path,
        category=category,
        compressed_size=compressed_size,
        uncompressed_size=compressed_size * 2,  # arbitrary; not used by validator
    )


# Strategy for generating an ArchiveInventory with a random set of entries
_archive_inventory = st.builds(
    lambda entries_data: ArchiveInventory(
        entries=[_make_archive_entry(p, s) for p, s in entries_data],
        zip_file=None,  # Not needed for validation
    ),
    st.lists(
        st.tuples(
            _any_entry_path,
            _compressed_size,
        ),
        min_size=1,
        max_size=80,
        unique_by=lambda t: t[0],  # Unique paths
    ),
)


# Strategy for selecting a subset of paths to mark as "processed"
@st.composite
def _inventory_with_processed(draw):
    """Generate an ArchiveInventory and a random subset of processed paths."""
    inventory = draw(_archive_inventory)
    all_paths = [e.path for e in inventory.entries]

    # Decide which paths have been "processed" (random subset)
    processed_mask = draw(
        st.lists(
            st.booleans(),
            min_size=len(all_paths),
            max_size=len(all_paths),
        )
    )
    processed_paths = {
        path for path, include in zip(all_paths, processed_mask) if include
    }

    return inventory, processed_paths


# ---------------------------------------------------------------------------
# Property 12: Completeness Accounting
# ---------------------------------------------------------------------------


class TestCompletenessAccounting:
    """**Validates: Requirements 18.1, 18.2, 18.3, 18.4**"""

    @given(data=_inventory_with_processed())
    @settings(max_examples=500)
    def test_total_entries_equals_zip_count(self, data):
        """total_entries in CompletenessSummary must equal the number of entries
        in the archive inventory (i.e., the ZIP entry count).

        **Validates: Requirements 18.1**
        """
        inventory, processed_paths = data

        summary, unprocessed_list, warning = validate_completeness(
            inventory, processed_paths
        )

        assert summary.total_entries == len(inventory.entries), (
            f"total_entries ({summary.total_entries}) != "
            f"inventory entry count ({len(inventory.entries)})"
        )

    @given(data=_inventory_with_processed())
    @settings(max_examples=500)
    def test_processed_plus_unprocessed_equals_total(self, data):
        """processed_entries + unprocessed_entries must equal total_entries.

        **Validates: Requirements 18.2, 18.3**
        """
        inventory, processed_paths = data

        summary, unprocessed_list, warning = validate_completeness(
            inventory, processed_paths
        )

        assert (
            summary.processed_entries + summary.unprocessed_entries
            == summary.total_entries
        ), (
            f"processed ({summary.processed_entries}) + "
            f"unprocessed ({summary.unprocessed_entries}) != "
            f"total ({summary.total_entries})"
        )

    @given(data=_inventory_with_processed())
    @settings(max_examples=500)
    def test_completeness_warning_flag_correct(self, data):
        """completeness_warning must be True when unprocessed > 0, False otherwise.

        **Validates: Requirements 18.4**
        """
        inventory, processed_paths = data

        summary, unprocessed_list, warning = validate_completeness(
            inventory, processed_paths
        )

        if summary.unprocessed_entries > 0:
            assert warning is True, (
                f"Expected warning=True when unprocessed_entries="
                f"{summary.unprocessed_entries}"
            )
        else:
            assert warning is False, "Expected warning=False when unprocessed_entries=0"

    @given(data=_inventory_with_processed())
    @settings(max_examples=300)
    def test_unprocessed_list_length_matches_count(self, data):
        """The length of the unprocessed entries list must equal
        unprocessed_entries in the summary.

        **Validates: Requirements 18.3, 18.4**
        """
        inventory, processed_paths = data

        summary, unprocessed_list, warning = validate_completeness(
            inventory, processed_paths
        )

        assert len(unprocessed_list) == summary.unprocessed_entries, (
            f"len(unprocessed_list) ({len(unprocessed_list)}) != "
            f"summary.unprocessed_entries ({summary.unprocessed_entries})"
        )
