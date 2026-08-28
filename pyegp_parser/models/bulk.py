"""Bulk processing models for directory-level EGP file parsing.

Defines the dataclasses that represent the result of parsing multiple .egp
files from a directory, including per-file success/failure tracking and
summary statistics.

Requirements: 19.3, 19.4, 19.5
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BulkFileSuccess:
    """A successfully parsed EGP file in a bulk operation.

    Attributes:
        file_path: Absolute path to the source .egp file.
        project: The parsed project object (ParsedProject instance).
    """

    file_path: str
    project: Any = None  # ParsedProject — uses Any to avoid circular imports


@dataclass
class BulkFileFailure:
    """A failed EGP file parse in a bulk operation.

    Attributes:
        file_path: Absolute path to the .egp file that failed.
        error_message: Description of the parsing failure.
    """

    file_path: str
    error_message: str


@dataclass
class BulkSummary:
    """Summary statistics for a bulk parsing operation.

    Attributes:
        total_files: Total number of .egp files discovered.
        success_count: Number of files parsed successfully.
        failure_count: Number of files that failed to parse.
    """

    total_files: int = 0
    success_count: int = 0
    failure_count: int = 0


@dataclass
class BulkResult:
    """Complete result of a bulk directory parsing operation.

    Contains the lists of successful and failed parses plus aggregate summary.

    Attributes:
        successes: List of successfully parsed file results.
        failures: List of file parse failures with error details.
        summary: Aggregate counts of discovered, succeeded, and failed files.
    """

    successes: list[BulkFileSuccess] = field(default_factory=list)
    failures: list[BulkFileFailure] = field(default_factory=list)
    summary: BulkSummary = field(default_factory=BulkSummary)
