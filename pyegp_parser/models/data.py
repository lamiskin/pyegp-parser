"""Data models for DataList items and their associated DataModel metadata.

These models represent SAS dataset references extracted from the DataList section
of an EGP project.xml. Each DataItem contains Element metadata, a DataModel
describing the dataset's location and properties, and a list of shortcut IDs.
"""

from dataclasses import dataclass, field

from ..parsers.dna_parser import DNADescriptor
from .base import ElementMetadata


@dataclass
class DataModel:
    """Metadata describing a SAS dataset.

    Contains server, library, table, and state information for a dataset
    reference within an EGP project.

    Attributes:
        server: The SAS server where the dataset resides.
        active_data_source: The active data source identifier.
        display_name: Human-readable display name for the dataset.
        table: The table/member name.
        raw_active_data_source_state: Raw XML DNA string (before decoding).
        data_source_state: The data source state descriptor.
        table_state: The table state descriptor.
        member_type: The SAS member type (e.g., "DATA", "VIEW").
        decoded_dna: Decoded DNA descriptor from RawActiveDataSourceState.
    """

    server: str | None = None
    active_data_source: str | None = None
    display_name: str | None = None
    table: str | None = None
    raw_active_data_source_state: str | None = None
    data_source_state: str | None = None
    table_state: str | None = None
    member_type: str | None = None
    decoded_dna: DNADescriptor | None = None


@dataclass
class DataItem:
    """A data item from the DataList section.

    Represents a single dataset reference within the EGP project, combining
    element metadata with dataset-specific information.

    Attributes:
        element: Standard element metadata (label, id, type, etc.).
        data_model: Dataset metadata (server, library, table, DNA).
        shortcut_list: List of ShortCutID references for this data item.
    """

    element: ElementMetadata | None = None
    data_model: DataModel | None = None
    shortcut_list: list[str] = field(default_factory=list)
