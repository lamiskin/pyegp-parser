"""JSON serialization with deterministic output for EGP parsed projects.

Provides:
- to_dict(): Convert any dataclass hierarchy to a dict with _type fields.
- from_dict(): Reconstruct typed models from JSON-derived dicts using _type dispatch.
- serialize_project(): Write a ParsedProject to JSON with sorted keys and 2-space indent.

All output is deterministic: same input always produces identical bytes.
Round-trip consistency is guaranteed: serialize → deserialize → re-serialize yields
identical JSON.

Requirements: 15.1, 15.2, 15.6, 15.7, 15.11, 15.12, 15.15, 17.1, 17.2, 17.5
"""

import json
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

# --- Type Registry ---
# All dataclass types that can appear in the serialized output.
# Used by from_dict() to dispatch on _type field values.
from .archive import ArchiveEntry, EntryCategory
from .models.base import ElementMetadata
from .models.bulk import BulkFileFailure, BulkFileSuccess, BulkResult, BulkSummary
from .models.data import DataItem, DataModel
from .models.elements import ElementCategory
from .models.external_file import ExternalFileItem
from .models.log_code import CodeElement, LogElement
from .models.process_flow import Connection, DAGModel, ProcessFlowContainer
from .models.project import (
    BinaryEntry,
    CompletenessSummary,
    Parameter,
    ParsedProject,
    ProjectLogInfo,
    ProjectMetadata,
    ProjectSettings,
    SourceInfo,
    UnprocessedEntry,
)
from .models.query import (
    Calculation,
    Expression,
    FilterNode,
    GroupItem,
    InputTable,
    JoinItem,
    OrderItem,
    QueryBuilderTablePosition,
    QueryModel,
    ResultItem,
)
from .models.shortcut import ShortCutToData, ShortCutToFile
from .models.tasks import (
    AppendTaskElement,
    CodeTaskElement,
    EGTaskElement,
    ExportTaskElement,
    ImportTaskElement,
    SubmitableElement,
)
from .models.visual_layout import (
    ProcessFlowControlState,
    TaskGraphic,
    TreeItem,
    VisualLayout,
)
from .parsers.dna_parser import DNADescriptor
from .redaction import redact as redact_output

# Build the type registry mapping _type names to their dataclass constructors
_TYPE_REGISTRY: dict[str, type] = {}


def _register_types() -> None:
    """Populate the type registry with all known dataclass types."""
    types_to_register = [
        # Base
        ElementMetadata,
        # Archive
        ArchiveEntry,
        # Bulk
        BulkFileFailure,
        BulkFileSuccess,
        BulkResult,
        BulkSummary,
        # Data
        DataItem,
        DataModel,
        # External file
        ExternalFileItem,
        # Log and Code
        CodeElement,
        LogElement,
        # Process flow
        Connection,
        DAGModel,
        ProcessFlowContainer,
        # Project
        BinaryEntry,
        CompletenessSummary,
        Parameter,
        ParsedProject,
        ProjectLogInfo,
        ProjectMetadata,
        ProjectSettings,
        SourceInfo,
        UnprocessedEntry,
        # Query
        Calculation,
        Expression,
        FilterNode,
        GroupItem,
        InputTable,
        JoinItem,
        OrderItem,
        QueryBuilderTablePosition,
        QueryModel,
        ResultItem,
        # Shortcuts
        ShortCutToData,
        ShortCutToFile,
        # Tasks
        AppendTaskElement,
        CodeTaskElement,
        EGTaskElement,
        ExportTaskElement,
        ImportTaskElement,
        SubmitableElement,
        # Visual layout
        ProcessFlowControlState,
        TaskGraphic,
        TreeItem,
        VisualLayout,
        # DNA
        DNADescriptor,
    ]
    for cls in types_to_register:
        _TYPE_REGISTRY[cls.__name__] = cls


_register_types()


def serialize_project(project: Any, output_dir: Path, redact: bool = True) -> str:
    """Serialize a ParsedProject to JSON with deterministic output.

    - All keys sorted alphabetically at every nesting level
    - 2-space indentation
    - UTF-8 encoding
    - _type fields included for every dataclass object
    - Creates output directory recursively if needed

    Args:
        project: The ParsedProject instance to serialize.
        output_dir: Directory where project.json will be written.
        redact: Apply best-effort credential redaction to embedded SAS code and
            logs before writing. On by default, because a written `project.json`
            is the artifact most likely to be shared. Pass ``False`` only when
            you need byte-faithful code and control where the output goes.

    Returns:
        The JSON string that was written.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    data = to_dict(project)
    if redact:
        data, _ = redact_output(data)
    json_str = json.dumps(
        data,
        indent=2,
        ensure_ascii=False,
        sort_keys=True,
    )
    (output_dir / "project.json").write_text(json_str, encoding="utf-8")
    return json_str


def to_dict(obj: Any) -> Any:
    """Convert a dataclass hierarchy to a dict with _type fields.

    Handles: dataclasses, lists, dicts, Enums, None, and primitive types.
    Uses snake_case field naming (field names come directly from the dataclass
    definitions which already use snake_case).

    For dataclass instances, a "_type" key is added with the class name,
    enabling polymorphic deserialization via from_dict().

    For ParsedProject (the root), the schema_version field is also output
    as "_schema_version" to match the JSON Schema contract (Req 15.14).

    Args:
        obj: Any object to convert (dataclass, list, dict, primitive, etc.).

    Returns:
        A JSON-serializable representation of the object.
    """
    if obj is None:
        return None
    if is_dataclass(obj) and not isinstance(obj, type):
        result: dict[str, Any] = {"_type": type(obj).__name__}
        is_root = isinstance(obj, ParsedProject)
        for f in fields(obj):
            # schema_version is output as _schema_version for ParsedProject (Req 15.14)
            if is_root and f.name == "schema_version":
                continue
            value = getattr(obj, f.name)
            result[f.name] = to_dict(value)
        # Add _schema_version for ParsedProject to match JSON Schema (Req 15.14).
        # `is_root` guarantees obj is a ParsedProject, which has schema_version.
        if is_root:
            result["_schema_version"] = obj.schema_version  # type: ignore[attr-defined]
        return result
    if isinstance(obj, list):
        return [to_dict(item) for item in obj]
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in sorted(obj.items())}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, set):
        return sorted(to_dict(item) for item in obj)
    if isinstance(obj, Path):
        return str(obj)
    # Primitives: str, int, float, bool pass through directly
    return obj


def from_dict(data: Any) -> Any:
    """Reconstruct a typed model from a JSON-derived dict using _type dispatch.

    Uses the _TYPE_REGISTRY to map _type field values to their corresponding
    dataclass constructors, recursively reconstructing nested objects.

    Args:
        data: A dict (with _type field), list, or primitive value.

    Returns:
        The reconstructed dataclass instance, list, or primitive value.

    Raises:
        ValueError: If a _type value is not found in the registry.
    """
    if data is None:
        return None
    if isinstance(data, list):
        return [from_dict(item) for item in data]
    if isinstance(data, dict):
        if "_type" not in data:
            # Plain dict without _type — reconstruct as dict with recursed values
            return {k: from_dict(v) for k, v in data.items()}
        type_name = data["_type"]
        cls = _TYPE_REGISTRY.get(type_name)
        if cls is None:
            raise ValueError(
                f"Unknown _type '{type_name}' encountered during deserialization. "
                f"Known types: {sorted(_TYPE_REGISTRY.keys())}"
            )
        # Build kwargs for the dataclass constructor
        kwargs: dict[str, Any] = {}

        # Handle _schema_version → schema_version mapping for ParsedProject
        if cls is ParsedProject and "_schema_version" in data:
            kwargs["schema_version"] = data["_schema_version"]

        for f in fields(cls):
            # schema_version for ParsedProject is handled via _schema_version above
            if (
                cls is ParsedProject
                and f.name == "schema_version"
                and "schema_version" not in data
            ):
                continue
            if f.name not in data:
                # Field not in serialized data — use default
                continue
            raw_value = data[f.name]
            kwargs[f.name] = _reconstruct_field(cls, f, raw_value)
        return cls(**kwargs)
    # Primitives pass through
    return data


def _reconstruct_field(cls: type, f: Any, raw_value: Any) -> Any:
    """Reconstruct a single field value based on type annotation context.

    Handles special cases like Enum fields where the serialized value is
    a string that needs to be converted back to the Enum type.

    Args:
        cls: The parent dataclass class.
        f: The dataclass field descriptor.
        raw_value: The raw value from the JSON dict.

    Returns:
        The reconstructed field value.
    """
    if raw_value is None:
        return None

    # Check if the field type is an Enum
    field_type = f.type
    enum_cls = _resolve_enum_type(field_type)
    if enum_cls is not None and isinstance(raw_value, str):
        return enum_cls(raw_value)

    # For dicts and lists containing _type, recurse
    if isinstance(raw_value, (dict, list)):
        return from_dict(raw_value)

    # Primitives pass through
    return raw_value


def _resolve_enum_type(type_annotation: Any) -> type | None:
    """Resolve a type annotation to an Enum class, if applicable.

    Handles string annotations and Optional types.

    Args:
        type_annotation: The field's type annotation.

    Returns:
        The Enum subclass if the annotation resolves to one, else None.
    """
    # Known enum types in the project
    known_enums = {
        "EntryCategory": EntryCategory,
        "ElementCategory": ElementCategory,
    }

    if isinstance(type_annotation, str):
        # Handle string annotation like "EntryCategory"
        for name, enum_cls in known_enums.items():
            if name in type_annotation:
                return enum_cls
    elif isinstance(type_annotation, type) and issubclass(type_annotation, Enum):
        return type_annotation

    return None
