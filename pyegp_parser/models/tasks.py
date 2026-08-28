"""Task element models for EGP project task types."""

from dataclasses import dataclass, field
from typing import Any

from .base import ElementMetadata


@dataclass
class SubmitableElement:
    """Configuration for task execution.

    Contains server submission settings, error state, and execution
    metadata shared across all submitable task types.
    """

    use_global_options: bool | None = None
    server: str | None = None
    has_error: bool | None = None
    has_warning: bool | None = None
    ods_style_overrides: dict | None = None
    expected_output_data_list: list = field(default_factory=list)
    parameters: list = field(default_factory=list)
    execution_time_span: str | None = None
    job_recipe: Any = None


@dataclass
class ImportTaskElement:
    """An import task that brings external data into the EGP project."""

    metadata: ElementMetadata | None = None
    submitable: SubmitableElement | None = None
    eg_task_clsid: str | None = None
    current_view_type: str | None = None
    obs: int | None = None
    first_obs: int | None = None
    generates_code_flag: bool | None = None
    generate_output_data_names: str | None = None
    input_data_list: list = field(default_factory=list)
    var_name_parameters: str | None = None
    parent_id: str | None = None
    task_config: Any = None
    log_content: str | None = None


@dataclass
class CodeTaskElement:
    """A code task containing user-written SAS code."""

    metadata: ElementMetadata | None = None
    submitable: SubmitableElement | None = None
    code_content: str | None = None
    log_content: str | None = None


@dataclass
class EGTaskElement:
    """A built-in Enterprise Guide task (wizard-generated)."""

    metadata: ElementMetadata | None = None
    submitable: SubmitableElement | None = None
    eg_task_clsid: str | None = None
    generates_code_flag: bool | None = None
    task_config: Any = None
    log_content: str | None = None


@dataclass
class ExportTaskElement:
    """An export task that outputs data from the EGP project."""

    metadata: ElementMetadata | None = None
    submitable: SubmitableElement | None = None
    parent_id: str | None = None
    task_config: Any = None
    log_content: str | None = None


@dataclass
class AppendTaskElement:
    """An append task that combines data from multiple sources."""

    metadata: ElementMetadata | None = None
    submitable: SubmitableElement | None = None
    parent_id: str | None = None
    input_data_refs: list = field(default_factory=list)
    task_config: Any = None
    log_content: str | None = None
