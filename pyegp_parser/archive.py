"""ZIP extraction and entry classification for EGP archives."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from zipfile import BadZipFile, ZipFile


class EntryCategory(Enum):
    """Classification categories for ZIP archive entries."""

    PROJECT_XML = "project_xml"
    TASK_CONFIG = "task_config"
    CODE_FILE = "code_file"
    EXECUTION_LOG = "execution_log"
    PROJECT_LOG = "project_log"
    ODS_RESULT = "ods_result"
    EMPTY_DIRECTORY = "empty_directory"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ArchiveEntry:
    """A single entry in the EGP ZIP archive with its classification."""

    path: str
    category: EntryCategory
    compressed_size: int
    uncompressed_size: int


@dataclass
class ArchiveInventory:
    """Collection of classified archive entries with access to the open ZIP file."""

    entries: list[ArchiveEntry]
    zip_file: ZipFile  # kept open for content reads

    def get_content(self, path: str, encoding: str = "utf-8") -> str:
        """Read a text entry from the archive.

        Args:
            path: The archive entry path to read.
            encoding: Text encoding to use (default: utf-8).

        Returns:
            Decoded text content of the entry.
        """
        return self.zip_file.read(path).decode(encoding)

    def get_bytes(self, path: str) -> bytes:
        """Read raw bytes from the archive.

        Args:
            path: The archive entry path to read.

        Returns:
            Raw bytes of the entry.
        """
        return self.zip_file.read(path)

    def close(self) -> None:
        """Close the underlying ZIP file."""
        self.zip_file.close()


def open_archive(egp_path: Path) -> ArchiveInventory:
    """Open an EGP file and classify all entries.

    Args:
        egp_path: Path to the .egp file.

    Returns:
        ArchiveInventory with classified entries and an open ZipFile handle.

    Raises:
        FileNotFoundError: If path does not exist.
        ValueError: If not a valid ZIP or missing project.xml.
    """
    # Import here to avoid circular dependency (classifier imports EntryCategory from this module)
    from .classifier import classify_entry

    path = Path(egp_path)

    if not path.exists():
        raise FileNotFoundError(f"EGP file not found: {path}")

    try:
        zf = ZipFile(path, "r")
    except BadZipFile as e:
        raise ValueError(f"Not a valid EGP archive (invalid ZIP): {path}") from e

    # Enumerate and classify all entries
    entries: list[ArchiveEntry] = []
    has_project_xml = False

    for info in zf.infolist():
        category = classify_entry(info.filename)
        if category == EntryCategory.PROJECT_XML:
            has_project_xml = True
        entries.append(
            ArchiveEntry(
                path=info.filename,
                category=category,
                compressed_size=info.compress_size,
                uncompressed_size=info.file_size,
            )
        )

    if not has_project_xml:
        zf.close()
        raise ValueError(f"Not a valid EGP archive (missing project.xml): {path}")

    return ArchiveInventory(entries=entries, zip_file=zf)
