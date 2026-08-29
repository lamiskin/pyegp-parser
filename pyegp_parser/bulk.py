"""Bulk directory processing for EGP files.

Discovers all .egp files recursively within a directory, parses each
independently, records successes and failures, and optionally writes
per-file JSON outputs preserving subdirectory structure.

Requirements: 19.1, 19.2, 19.3, 19.4, 19.5, 19.6, 19.7
"""

from pathlib import Path

from .models.bulk import BulkFileFailure, BulkFileSuccess, BulkResult, BulkSummary


def discover_egp_files(directory: Path) -> list[Path]:
    """Discover all .egp files recursively, sorted lexicographically by full path.

    Args:
        directory: Root directory to search.

    Returns:
        Sorted list of Path objects pointing to .egp files.

    Raises:
        ValueError: If directory does not exist or is not a directory.
    """
    if not directory.exists():
        raise ValueError(f"Invalid directory path: '{directory}' does not exist")
    if not directory.is_dir():
        raise ValueError(f"Invalid directory path: '{directory}' is not a directory")
    egp_files = list(directory.rglob("*.egp"))
    # Sort lexicographically by full path string for consistent ordering
    egp_files.sort(key=str)
    return egp_files


def _get_parse_file():
    """Lazy import of parse_file to avoid circular dependencies."""
    import pyegp_parser

    return pyegp_parser.parse_file


def process_directory(
    directory: str | Path,
    output_dir: str | Path | None = None,
) -> BulkResult:
    """Parse all .egp files in a directory recursively.

    Discovers .egp files, parses each independently, and collects results.
    If output_dir is provided, writes per-file JSON outputs preserving
    subdirectory structure relative to the input directory.

    Args:
        directory: Root directory to scan for .egp files.
        output_dir: Optional directory for per-file JSON output.
            Output paths preserve subdirectory structure:
            {output_dir}/{relative_path_stem}.json

    Returns:
        BulkResult with successes, failures, and summary counts.

    Raises:
        ValueError: If directory does not exist or is not a directory.
    """
    parse_file = _get_parse_file()

    directory = Path(directory).resolve()

    # Validate directory and discover files (raises ValueError if invalid)
    egp_files = discover_egp_files(directory)

    output_path = Path(output_dir).resolve() if output_dir else None

    successes: list[BulkFileSuccess] = []
    failures: list[BulkFileFailure] = []

    for egp_file in egp_files:
        try:
            # Determine per-file output directory if output_dir is specified
            file_output_dir = None
            if output_path is not None:
                # Preserve subdirectory structure relative to input directory
                relative = egp_file.relative_to(directory)
                # Use stem (filename without extension) as the output subdirectory
                file_output_dir = output_path / relative.parent / relative.stem

            project = parse_file(egp_file, output_dir=file_output_dir)
            successes.append(
                BulkFileSuccess(
                    file_path=str(egp_file),
                    project=project,
                )
            )
        except Exception as e:
            failures.append(
                BulkFileFailure(
                    file_path=str(egp_file),
                    error_message=str(e),
                )
            )

    summary = BulkSummary(
        total_files=len(egp_files),
        success_count=len(successes),
        failure_count=len(failures),
    )

    return BulkResult(
        successes=successes,
        failures=failures,
        summary=summary,
    )
