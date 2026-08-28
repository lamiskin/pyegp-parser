"""Data models for ExternalFileList items.

These models represent external file references extracted from the ExternalFileList
section of an EGP project.xml. Each ExternalFileItem contains Element metadata,
a file type, shortcut references, and a DNA descriptor describing the file's
location and properties.
"""

from dataclasses import dataclass, field

from ..parsers.dna_parser import DNADescriptor
from .base import ElementMetadata


@dataclass
class ExternalFileItem:
    """An external file reference from the ExternalFileList section.

    Represents a single external file dependency within the EGP project,
    combining element metadata with file-specific information including
    the DNA descriptor that encodes the file's full path and hierarchy.

    Attributes:
        element: Standard element metadata (label, id, type, etc.).
        shortcut_list: List of ShortCutID references for this external file.
        file_type_type: The file type classification (e.g., "CSV", "XLSX").
        raw_dna: The raw DNA XML string before decoding.
        decoded_dna: Decoded DNA descriptor with file path and hierarchy.
    """

    element: ElementMetadata | None = None
    shortcut_list: list[str] = field(default_factory=list)
    file_type_type: str | None = None
    raw_dna: str | None = None
    decoded_dna: DNADescriptor | None = None
