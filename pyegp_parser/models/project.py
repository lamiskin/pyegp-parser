"""Project-level metadata and root models for parsed EGP projects.

This module defines the top-level dataclasses that represent a fully parsed
EGP project, including project metadata, settings, source provenance, and
the root ParsedProject container.

All metadata fields default to None per requirement 2.7, so that absent XML
attributes do not raise errors during parsing.
"""

from dataclasses import dataclass, field
from typing import Any


def _parser_version() -> str:
    """The running package version, resolved lazily.

    Imported inside the function because ``pyegp_parser/__init__.py`` imports
    this module, so a module-level import would be circular. Deriving it keeps
    the emitted ``parser_version`` from drifting out of step with the package
    version each time a release bumps it.
    """
    from pyegp_parser import __version__

    return __version__


@dataclass
class ProjectMetadata:
    """Project-level metadata from the ProjectCollection root and project Element.

    Extracted from the root ProjectCollection element attributes (EGVersion, Type)
    and the project Element (Label, ID, CreatedOn, ModifiedOn, etc.).

    Attributes:
        eg_version: The Enterprise Guide version from the ProjectCollection root.
        type: The project type attribute.
        label: Human-readable project name.
        id: Unique project identifier.
        created_on: ISO 8601 timestamp of project creation.
        modified_on: ISO 8601 timestamp of last modification.
        modified_by: Display name of the last modifier.
        modified_by_eg_id: Enterprise Guide internal user ID of the modifier.
        modified_by_eg_ver: Enterprise Guide version used for the modification.
    """

    eg_version: str | None = None
    type: str | None = None
    label: str | None = None
    id: str | None = None
    created_on: str | None = None
    modified_on: str | None = None
    modified_by: str | None = None
    modified_by_eg_id: str | None = None
    modified_by_eg_ver: str | None = None


@dataclass
class ProjectSettings:
    """Project settings from the ProjectSettings section.

    Boolean and string settings controlling project execution behavior,
    logging configuration, and submission options.

    Attributes:
        use_relative_paths: Whether the project uses relative file paths.
        submit_to_grid: Whether tasks submit to a grid computing environment.
        queue_submits_for_server: Whether submissions are queued for the server.
        action_on_error: Behavior when an error occurs during execution.
        show_project_log_warning_message: Whether to show log warning messages.
        remove_older_project_log_items: Whether to prune old log entries.
        export_project_log_then_clear: Whether to export and clear the log.
        project_log_export_filename: Filename for exported project logs.
        project_log_export_location: Directory path for exported project logs.
        project_log_max_size: Maximum size of the project log in entries.
        clear_project_log_on_exit: Whether to clear the log when closing.
    """

    use_relative_paths: bool | None = None
    submit_to_grid: bool | None = None
    queue_submits_for_server: bool | None = None
    action_on_error: str | None = None
    show_project_log_warning_message: bool | None = None
    remove_older_project_log_items: bool | None = None
    export_project_log_then_clear: bool | None = None
    project_log_export_filename: str | None = None
    project_log_export_location: str | None = None
    project_log_max_size: int | None = None
    clear_project_log_on_exit: bool | None = None


@dataclass
class Parameter:
    """A project-level parameter with a name and value.

    Attributes:
        name: The parameter name.
        value: The parameter value.
    """

    name: str
    value: str


@dataclass
class ProjectLogInfo:
    """Project log metadata and content.

    Attributes:
        enabled: Whether the project log is enabled.
        written_to: Whether the project log has been written to.
        content: The text content of the project log file, if present.
    """

    enabled: bool | None = None
    written_to: bool | None = None
    content: str | None = None


@dataclass
class CompletenessSummary:
    """Summary of archive entry processing completeness.

    Attributes:
        total_entries: Total number of entries in the ZIP archive.
        processed_entries: Number of entries successfully processed.
        unprocessed_entries: Number of entries not processed.
    """

    total_entries: int = 0
    processed_entries: int = 0
    unprocessed_entries: int = 0


@dataclass
class UnprocessedEntry:
    """An archive entry that was not processed by the parser.

    Attributes:
        path: The archive path of the unprocessed entry.
        compressed_size: The compressed size of the entry in bytes.
    """

    path: str
    compressed_size: int


@dataclass
class BinaryEntry:
    """A binary archive entry (e.g., ODS result) tracked without extraction.

    Attributes:
        path: The archive path of the binary entry.
        compressed_size: The compressed size of the entry in bytes.
        file_extension: The file extension (e.g., ".pptx").
        task_id: The associated task ID if matched via JobRecipe, else None.
    """

    path: str
    compressed_size: int
    file_extension: str
    task_id: str | None = None


@dataclass
class SourceInfo:
    """Provenance metadata about the source EGP file and parse operation.

    Attributes:
        file_path: Absolute path to the original .egp file.
        file_name: Base filename (e.g., "Row_Count_Comparison v1.egp").
        file_size_bytes: Size of the .egp file on disk in bytes.
        parsed_at: ISO 8601 timestamp of when the parse was performed.
        total_zip_entries: Total number of entries in the ZIP archive.
    """

    file_path: str
    file_name: str
    file_size_bytes: int
    parsed_at: str
    total_zip_entries: int


@dataclass
class ParsedProject:
    """Root model representing a fully parsed EGP project.

    This is the top-level container that holds all parsed data from an EGP file.
    Fields use generic types (Any, list) to avoid circular imports — downstream
    code will populate them with the appropriate typed models.

    Attributes:
        schema_version: Semantic version of the output schema format.
        parser_version: Version of the parser that produced this output.
        source: Provenance metadata about the source EGP file.
        metadata: Project-level metadata (version, type, label, etc.).
        settings: Project configuration settings.
        data_list: Parsed DataItem entries from the DataList section.
        external_files: Parsed ExternalFileItem entries.
        elements: All parsed Element objects in document order.
        containers: ProcessFlowContainer objects with their DAGs.
        parameters: Project-level Parameter entries.
        project_log: Project log metadata and content.
        visual_layout: Visual layout information for process flows.
        completeness_summary: Summary of archive processing completeness.
        unprocessed_entries: Archive entries that were not processed.
        completeness_warning: True if any entries were unprocessed.
        binary_entries: Binary entries tracked without extraction.
        application_overrides: The ApplicationOverrides section, if present.
        metadata_info: The MetaDataInfo section, if present.
        open_project_view: TreeItem entries from the OpenProjectView section.
        queries: QueryModel + metadata pairs from Query elements.
        tasks: Task-type elements with SubmitableElement and config.
        shortcuts: ShortCutToData/ShortCutToFile objects.
        log_elements: LogElement objects from Log elements.
        code_elements: CodeElement objects from Code elements.
        external_objects: Parsed External_Objects entries.
    """

    schema_version: str = "1.0.0"
    parser_version: str = field(default_factory=_parser_version)
    source: SourceInfo | None = None
    metadata: ProjectMetadata | None = None
    settings: ProjectSettings | None = None
    data_list: list = field(default_factory=list)
    external_files: list = field(default_factory=list)
    elements: list = field(default_factory=list)
    containers: list = field(default_factory=list)
    parameters: list = field(default_factory=list)
    project_log: ProjectLogInfo | None = None
    visual_layout: Any = None
    completeness_summary: CompletenessSummary | None = None
    unprocessed_entries: list = field(default_factory=list)
    completeness_warning: bool = False
    binary_entries: list = field(default_factory=list)
    application_overrides: Any = None
    metadata_info: Any = None
    open_project_view: list = field(default_factory=list)
    queries: list = field(default_factory=list)
    tasks: list = field(default_factory=list)
    shortcuts: list = field(default_factory=list)
    log_elements: list = field(default_factory=list)
    code_elements: list = field(default_factory=list)
    external_objects: list = field(default_factory=list)
