"""Base models shared across all EGP element types."""

from dataclasses import dataclass, field


@dataclass
class ElementMetadata:
    """Standard metadata fields shared by all elements.

    Every Element in an EGP project.xml carries these fields.
    All fields default to None (per requirements 2.7, 5.3) so that
    absent XML attributes do not raise errors.

    Attributes:
        label: Human-readable name of the element.
        type: Fully-qualified type string (e.g. "SAS.EG.ProjectElements.Query").
        container: ID of the parent ProcessFlowContainer, if any.
        id: Unique identifier for this element within the project.
        created_on: ISO 8601 timestamp when the element was created.
        modified_on: ISO 8601 timestamp of last modification.
        modified_by: Display name of the user who last modified the element.
        modified_by_eg_id: Enterprise Guide internal user ID of the modifier.
        modified_by_eg_ver: Enterprise Guide version used for the modification.
        has_serialization_error: Flag indicating serialization issues.
        input_ids: List of element IDs that serve as inputs to this element.
    """

    label: str | None = None
    type: str | None = None
    container: str | None = None
    id: str | None = None
    created_on: str | None = None
    modified_on: str | None = None
    modified_by: str | None = None
    modified_by_eg_id: str | None = None
    modified_by_eg_ver: str | None = None
    has_serialization_error: bool | None = None
    input_ids: list[str] = field(default_factory=list)
