"""Property-based tests for ZIP entry classification completeness.

**Validates: Requirements 1.1, 1.5, 1.6**

Uses Hypothesis to verify that every ZIP entry path is classified into exactly
one EntryCategory, and that when a ZIP archive is opened via open_archive(),
the total classified entries equals the total number of entries in the archive.
"""

import string
import zipfile

from hypothesis import given, settings
from hypothesis import strategies as st

from pyegp_parser.archive import EntryCategory, open_archive
from pyegp_parser.classifier import classify_entry

# ---------------------------------------------------------------------------
# Strategies for generating ZIP entry paths
# ---------------------------------------------------------------------------

# Strategy for random path segments
_segment = st.text(
    alphabet=string.ascii_letters + string.digits + "_-. ",
    min_size=1,
    max_size=30,
)

# Strategy for alphanumeric IDs (as used in EGP archives)
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

# Strategy: paths matching known categories
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
    lambda eid, fname: f"ODSResults/ODSResult-{eid}/{fname}",
    _entry_id,
    st.from_regex(r"result\.\w{2,5}", fullmatch=True),
)

_empty_dir_path = st.builds(
    lambda seg: f"{seg}/",
    _segment,
)

# Strategy: completely random path strings (may include unicode, special chars)
_random_path = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S"),
        blacklist_characters="\x00",
    ),
    min_size=1,
    max_size=200,
)

# Strategy: edge case paths
_edge_case_path = st.one_of(
    st.just(""),  # empty string
    st.text(min_size=200, max_size=500),  # very long paths
    st.text(  # unicode characters
        alphabet=st.characters(whitelist_categories=("L", "N", "P", "S", "Z")),
        min_size=1,
        max_size=50,
    ),
    st.from_regex(r"[/\\.]{1,10}", fullmatch=True),  # special path-like chars
)

# Combined strategy that mixes valid patterns and random paths
_any_entry_path = st.one_of(
    _project_xml_path,
    _task_config_path,
    _code_file_path,
    _execution_log_path,
    _project_log_path,
    _ods_result_path,
    _empty_dir_path,
    _random_path,
    _edge_case_path,
)


# ---------------------------------------------------------------------------
# Property 1: Every path maps to exactly one EntryCategory
# ---------------------------------------------------------------------------


class TestClassificationCompleteness:
    """**Validates: Requirements 1.1, 1.5, 1.6**"""

    @given(path=_any_entry_path)
    @settings(max_examples=500)
    def test_every_path_gets_exactly_one_category(self, path: str):
        """Every generated path must map to exactly one EntryCategory value.

        This verifies that classify_entry is a total function: it never raises
        an exception and always returns a valid EntryCategory enum member.
        """
        result = classify_entry(path)

        # Result must be a valid EntryCategory enum member
        assert isinstance(result, EntryCategory), (
            f"classify_entry({path!r}) returned {result!r}, not an EntryCategory"
        )
        # Result must be one of the known category values
        assert result in EntryCategory, (
            f"classify_entry({path!r}) returned unknown category: {result}"
        )

    @given(path=_any_entry_path)
    @settings(max_examples=300)
    def test_classification_is_deterministic(self, path: str):
        """Classifying the same path multiple times must return the same result."""
        result1 = classify_entry(path)
        result2 = classify_entry(path)
        assert result1 == result2, (
            f"Non-deterministic classification for {path!r}: {result1} vs {result2}"
        )

    @given(
        paths=st.lists(
            _any_entry_path.filter(lambda p: p != "" and "\x00" not in p),
            min_size=1,
            max_size=50,
            unique=True,
        )
    )
    @settings(max_examples=200)
    def test_zip_archive_total_classified_equals_total_entries(
        self, paths: list[str], tmp_path_factory
    ):
        """When creating a ZIP with N random paths and opening with open_archive(),
        the total classified entries must equal N.

        This requires project.xml to be present for the archive to be valid.
        """
        # Ensure project.xml is included (required by open_archive)
        all_paths = list(set(paths) | {"project.xml"})
        n = len(all_paths)

        # Create a real ZIP in a temp directory
        tmp_dir = tmp_path_factory.mktemp("zip_test")
        zip_path = tmp_dir / "test.egp"

        with zipfile.ZipFile(zip_path, "w") as zf:
            for p in all_paths:
                # Write dummy content; directory entries get empty content
                if p.endswith("/"):
                    zf.writestr(p, "")
                else:
                    zf.writestr(p, f"content of {p}")

        # Open with our archive module
        inventory = open_archive(zip_path)
        try:
            # Total classified entries must equal total entries
            assert len(inventory.entries) == n, (
                f"Expected {n} entries, got {len(inventory.entries)}"
            )

            # Every entry must have a valid category
            for entry in inventory.entries:
                assert isinstance(entry.category, EntryCategory), (
                    f"Entry {entry.path!r} has invalid category: {entry.category!r}"
                )

            # Count by category — sum must equal total
            categorized_count = sum(
                1 for e in inventory.entries if isinstance(e.category, EntryCategory)
            )
            assert categorized_count == n, (
                f"Categorized count {categorized_count} != total entries {n}"
            )
        finally:
            inventory.close()
