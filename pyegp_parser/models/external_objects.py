"""Data models for External_Objects section entries.

These models represent external object references extracted from the External_Objects
section of an EGP project.xml. Each ExternalObject contains metadata attributes
such as name, type, path, and optional descriptive fields.
"""

from dataclasses import dataclass, field


@dataclass
class ExternalObject:
    """An external object entry from the External_Objects section.

    Represents a single external object reference within the EGP project,
    capturing its identifying attributes (name, type, path) and any
    additional metadata stored as child elements or attributes.

    Attributes:
        name: The name identifier of the external object (required).
        type: The type classification of the external object (e.g., "File", "Library").
        path: The file system path or URI reference for the external object.
        description: Optional description of the external object.
        metadata: Dictionary of additional attributes/child elements not captured
            by the named fields above.
    """

    name: str
    type: str | None = None
    path: str | None = None
    description: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)
