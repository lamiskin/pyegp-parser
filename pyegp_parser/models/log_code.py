"""Log and Code element models for EGP projects."""

from dataclasses import dataclass

from .base import ElementMetadata


@dataclass
class LogElement:
    """A log element representing execution output display settings."""

    metadata: ElementMetadata | None = None
    parent_id: str | None = None
    line_size: int | None = None
    page_size: int | None = None
    portrait: bool | None = None
    condition_parent: str | None = None


@dataclass
class CodeElement:
    """A code element containing structured SAS code sections.

    Holds both the TextElement properties (text, read_only, def_ext)
    and the structured Code section with pre/post task code fragments.
    """

    metadata: ElementMetadata | None = None
    # TextElement section
    text: str | None = None
    read_only: bool | None = None
    def_ext: str | None = None
    # Code section
    parent_id: str | None = None
    libref_code: str | None = None
    begin_app_code: str | None = None
    begin_user_code: str | None = None
    task_code: str | None = None
    end_user_code: str | None = None
    end_app_code: str | None = None
    libref_cl_code: str | None = None
    macro_assign_code: str | None = None
    macro_unassign_code: str | None = None
