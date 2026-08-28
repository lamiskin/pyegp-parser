"""Property 13: Bulk Discovery and Aggregation.

Generate directories with N .egp files (mix valid/invalid); verify discovery
of all N and successes + failures equals N.

Validates: Requirements 19.1, 19.3, 19.4, 19.5
"""

import tempfile
import zipfile
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from pyegp_parser.bulk import discover_egp_files, process_directory

# --- Strategies ---


def _create_valid_egp(path: Path) -> None:
    """Create a valid .egp file (ZIP with project.xml)."""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(
            "project.xml",
            '<?xml version="1.0"?><ProjectCollection EGVersion="8.1" Type="Project">'
            "<Elements></Elements></ProjectCollection>",
        )


def _create_invalid_egp(path: Path, variant: str) -> None:
    """Create an invalid .egp file based on variant type."""
    if variant == "not_zip":
        # Write random bytes — not a valid ZIP
        path.write_bytes(b"This is not a zip file at all!")
    elif variant == "no_project_xml":
        # Valid ZIP but missing project.xml
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("readme.txt", "no project.xml here")
    elif variant == "empty":
        # Empty file
        path.write_bytes(b"")
    else:
        # Corrupt ZIP header
        path.write_bytes(b"PK\x03\x04" + b"\x00" * 50)


@st.composite
def bulk_directory_layout(draw):
    """Generate a directory layout specification with N .egp files.

    Returns a tuple of (list of (relative_path, is_valid), total_count).
    """
    # Generate between 1 and 15 files
    n_files = draw(st.integers(min_value=1, max_value=15))

    files = []
    for i in range(n_files):
        # Decide if the file is valid or invalid
        is_valid = draw(st.booleans())

        # Generate subdirectory depth (0 = root, up to 3 levels)
        depth = draw(st.integers(min_value=0, max_value=2))
        parts = []
        for _ in range(depth):
            part = draw(
                st.text(
                    alphabet=st.characters(
                        whitelist_categories=("Ll",),
                        whitelist_characters="_",
                    ),
                    min_size=1,
                    max_size=5,
                )
            )
            parts.append(part)

        # Generate filename
        filename = f"project_{i}.egp"
        rel_path = Path(*parts, filename) if parts else Path(filename)

        # Pick invalid variant
        variant = None
        if not is_valid:
            variant = draw(
                st.sampled_from(["not_zip", "no_project_xml", "empty", "corrupt"])
            )

        files.append((str(rel_path), is_valid, variant))

    return files


def _setup_directory(tmp_dir: Path, file_specs: list) -> int:
    """Create .egp files in tmp_dir based on specs. Returns count of files created."""
    count = 0
    for rel_path_str, is_valid, variant in file_specs:
        rel_path = Path(rel_path_str)
        full_path = tmp_dir / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)

        if is_valid:
            _create_valid_egp(full_path)
        else:
            _create_invalid_egp(full_path, variant)
        count += 1

    return count


# --- Property Tests ---


class TestBulkDiscoveryProperty:
    """Property 13: Bulk Discovery and Aggregation."""

    @given(file_specs=bulk_directory_layout())
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_discovers_all_egp_files(self, file_specs):
        """All N .egp files in a directory are discovered.

        **Validates: Requirements 19.1**
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            n = _setup_directory(tmp_path, file_specs)

            discovered = discover_egp_files(tmp_path)

            # Discovery must find exactly N files
            assert len(discovered) == n, (
                f"Expected {n} files discovered, got {len(discovered)}"
            )

    @given(file_specs=bulk_directory_layout())
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_discovered_files_are_sorted(self, file_specs):
        """Discovered files are in lexicographic order by full path.

        **Validates: Requirements 19.1**
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            _setup_directory(tmp_path, file_specs)

            discovered = discover_egp_files(tmp_path)

            # Verify sorted order
            paths_as_str = [str(p) for p in discovered]
            assert paths_as_str == sorted(paths_as_str)

    @given(file_specs=bulk_directory_layout())
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_successes_plus_failures_equals_total(self, file_specs):
        """For N discovered files, successes + failures == N.

        **Validates: Requirements 19.3, 19.4, 19.5**
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            n = _setup_directory(tmp_path, file_specs)

            result = process_directory(tmp_path)

            # Core property: every file is accounted for
            total_processed = len(result.successes) + len(result.failures)
            assert total_processed == n, (
                f"Expected successes + failures == {n}, "
                f"got {len(result.successes)} + {len(result.failures)} = {total_processed}"
            )

            # Summary must match
            assert result.summary.total_files == n
            assert result.summary.success_count == len(result.successes)
            assert result.summary.failure_count == len(result.failures)
            assert result.summary.success_count + result.summary.failure_count == n
