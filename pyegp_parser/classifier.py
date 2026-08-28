"""Path pattern matching for ZIP entry classification."""

import re

from .archive import EntryCategory

# Compiled regex patterns for categories that don't need backreference validation
_SIMPLE_PATTERNS: dict[EntryCategory, re.Pattern] = {
    EntryCategory.PROJECT_XML: re.compile(r"^project\.xml$"),
    EntryCategory.CODE_FILE: re.compile(r"^CodeTask-(?P<id>[A-Za-z0-9]+)/code\.sas$"),
    EntryCategory.EXECUTION_LOG: re.compile(
        r"^(?P<task_type>\w+)-(?P<task_id>[A-Za-z0-9]+)/Log-(?P<log_id>[A-Za-z0-9]+)/result\.log$"
    ),
    EntryCategory.ODS_RESULT: re.compile(
        r"^ODSResults/ODSResult-(?P<id>[A-Za-z0-9]+)/.*$"
    ),
}

# Patterns that require backreference-like validation (checked via function)
_TASK_CONFIG_PATTERN = re.compile(
    r"^(?P<task_type>\w+)-(?P<id>[A-Za-z0-9]+)/(?P<repeat_type>\w+)-(?P<repeat_id>[A-Za-z0-9]+)\.xml$"
)

_PROJECT_LOG_PATTERN = re.compile(
    r"^ProjectLog-(?P<id>[A-Za-z0-9]+)/ProjectLog-(?P<repeat_id>[A-Za-z0-9]+)/result\.log$"
)


def classify_entry(path: str) -> EntryCategory:
    """Classify a ZIP entry path into its category.

    Empty directory entries (ending with '/') are classified as EMPTY_DIRECTORY.
    Paths matching known patterns get their respective category.
    All other paths are classified as UNKNOWN.
    """
    if path.endswith("/"):
        return EntryCategory.EMPTY_DIRECTORY

    # Check simple patterns first
    for category, pattern in _SIMPLE_PATTERNS.items():
        if pattern.match(path):
            return category

    # Check TASK_CONFIG with backreference validation:
    # Pattern: {TaskType}-{ID}/{TaskType}-{ID}.xml (type and ID must repeat)
    m = _TASK_CONFIG_PATTERN.match(path)
    if (
        m
        and m.group("task_type") == m.group("repeat_type")
        and m.group("id") == m.group("repeat_id")
    ):
        return EntryCategory.TASK_CONFIG

    # Check PROJECT_LOG with backreference validation:
    # Pattern: ProjectLog-{ID}/ProjectLog-{ID}/result.log (ID must repeat)
    m = _PROJECT_LOG_PATTERN.match(path)
    if m and m.group("id") == m.group("repeat_id"):
        return EntryCategory.PROJECT_LOG

    return EntryCategory.UNKNOWN
