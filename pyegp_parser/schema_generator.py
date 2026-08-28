"""JSON Schema generator from dataclass introspection.

Generates a JSON Schema (Draft 2020-12) from the EGP parser's dataclass
model hierarchy, starting from ParsedProject as the root. The schema
is written to `{output_dir}/schema.json` and includes a `_schema_version`
linked to the model definitions.

The generator walks each dataclass and its fields, mapping Python types
to JSON Schema types:
  - str → string
  - int → integer
  - float → number
  - bool → boolean
  - list → array
  - dict → object
  - Optional[T] → nullable (anyOf with null)
  - Enum → enum with string values
  - Nested dataclasses → $ref to $defs

Requirements: 15.13, 15.14
"""

import dataclasses
import json
from enum import Enum
from pathlib import Path
from typing import Any, Union, get_args, get_origin, get_type_hints

from .models.base import ElementMetadata
from .models.data import DataItem, DataModel
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

# The schema version is tied to the ParsedProject model definition.
# It must be incremented when structural changes occur (Req 15.14).
_SCHEMA_VERSION = "1.0.0"

# All known model classes in the hierarchy. These are explicitly listed
# to ensure the schema includes all models even when ParsedProject uses
# bare `list` or `Any` type annotations (to avoid circular imports).
_ALL_MODEL_CLASSES: list[type] = [
    ParsedProject,
    # Base
    ElementMetadata,
    # Project
    BinaryEntry,
    CompletenessSummary,
    Parameter,
    ProjectLogInfo,
    ProjectMetadata,
    ProjectSettings,
    SourceInfo,
    UnprocessedEntry,
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


def generate_schema(output_dir: Path) -> str:
    """Generate a JSON Schema from the dataclass model hierarchy.

    Introspects ParsedProject and all reachable dataclasses to produce
    a complete JSON Schema with $defs for each model type.

    Args:
        output_dir: Directory where schema.json will be written.

    Returns:
        The JSON string that was written to schema.json.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    generator = _SchemaGenerator()
    schema = generator.generate()

    json_str = json.dumps(schema, indent=2, ensure_ascii=False, sort_keys=True)
    (output_dir / "schema.json").write_text(json_str, encoding="utf-8")
    return json_str


class _SchemaGenerator:
    """Internal schema generation engine.

    Walks the dataclass hierarchy starting from ParsedProject,
    collecting definitions and resolving type references.
    """

    def __init__(self) -> None:
        self._defs: dict[str, dict[str, Any]] = {}
        self._visited: set[type] = set()

    def generate(self) -> dict[str, Any]:
        """Produce the complete JSON Schema document."""
        # Process all known model classes to ensure full coverage,
        # since ParsedProject uses bare `list` and `Any` for some fields.
        for cls in _ALL_MODEL_CLASSES:
            self._process_dataclass(cls)

        schema: dict[str, Any] = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$defs": self._defs,
            "$ref": f"#/$defs/{ParsedProject.__name__}",
            "description": (
                "JSON Schema for EGP Parser output. Generated from "
                "dataclass model introspection."
            ),
            "title": "EGP Parser Output Schema",
        }
        return schema

    def _process_dataclass(self, cls: type) -> None:
        """Process a dataclass type, adding its definition to $defs."""
        if cls in self._visited:
            return
        self._visited.add(cls)

        if not dataclasses.is_dataclass(cls):
            return

        name = cls.__name__
        properties: dict[str, Any] = {}
        required: list[str] = []

        # Add _type discriminator field
        properties["_type"] = {
            "const": name,
            "description": "Type discriminator for polymorphic deserialization.",
            "type": "string",
        }
        required.append("_type")

        # Add _schema_version at the root level only
        if cls is ParsedProject:
            properties["_schema_version"] = {
                "const": _SCHEMA_VERSION,
                "description": (
                    "Schema version (semantic versioning). "
                    "Incremented on structural changes."
                ),
                "type": "string",
            }
            required.append("_schema_version")

        # Get type hints for the class (resolves forward references)
        try:
            hints = get_type_hints(cls)
        except Exception:
            hints = {f.name: f.type for f in dataclasses.fields(cls)}

        for field in dataclasses.fields(cls):
            field_name = field.name
            field_type = hints.get(field_name, field.type)

            # Skip private fields that are handled specially
            # (schema_version is handled as _schema_version above)
            if field_name == "schema_version" and cls is ParsedProject:
                continue

            prop_schema = self._type_to_schema(field_type)
            properties[field_name] = prop_schema

            # Determine if the field is required (no default value)
            has_default = (
                field.default is not dataclasses.MISSING
                or field.default_factory is not dataclasses.MISSING
            )
            if not has_default:
                required.append(field_name)

        definition: dict[str, Any] = {
            "additionalProperties": False,
            "properties": properties,
            "type": "object",
        }
        if required:
            definition["required"] = sorted(required)

        self._defs[name] = definition

    def _type_to_schema(self, tp: Any) -> dict[str, Any]:
        """Convert a Python type annotation to a JSON Schema fragment."""
        # Handle None/NoneType
        if tp is type(None):
            return {"type": "null"}

        # Handle basic primitive types
        if tp is str:
            return {"type": "string"}
        if tp is int:
            return {"type": "integer"}
        if tp is float:
            return {"type": "number"}
        if tp is bool:
            return {"type": "boolean"}

        # Handle Any type
        if tp is Any:
            return {}

        # Get origin for generic types
        origin = get_origin(tp)
        args = get_args(tp)

        # Handle Union types (including Optional which is Union[X, None])
        if origin is Union:
            non_none_args = [a for a in args if a is not type(None)]
            has_none = len(non_none_args) < len(args)

            if len(non_none_args) == 1:
                # Optional[T] = Union[T, None]
                inner_schema = self._type_to_schema(non_none_args[0])
                if has_none:
                    return {"anyOf": [inner_schema, {"type": "null"}]}
                return inner_schema
            else:
                # Union of multiple types
                schemas = [self._type_to_schema(a) for a in non_none_args]
                if has_none:
                    schemas.append({"type": "null"})
                return {"anyOf": schemas}

        # Handle list types
        if origin is list:
            if args:
                item_schema = self._type_to_schema(args[0])
                return {"items": item_schema, "type": "array"}
            return {"type": "array"}

        # Handle dict types
        if origin is dict:
            if args and len(args) == 2:
                value_schema = self._type_to_schema(args[1])
                return {
                    "additionalProperties": value_schema,
                    "type": "object",
                }
            return {"type": "object"}

        # Handle Enum types
        if isinstance(tp, type) and issubclass(tp, Enum):
            values = [member.value for member in tp]
            return {"enum": values, "type": "string"}

        # Handle dataclass types (nested models)
        if isinstance(tp, type) and dataclasses.is_dataclass(tp):
            self._process_dataclass(tp)
            return {"$ref": f"#/$defs/{tp.__name__}"}

        # Handle str | None syntax (Python 3.10+ union types)
        # get_origin returns types.UnionType for X | Y syntax
        try:
            import types as _types

            if isinstance(tp, _types.UnionType):
                args = get_args(tp)
                non_none_args = [a for a in args if a is not type(None)]
                has_none = len(non_none_args) < len(args)

                if len(non_none_args) == 1:
                    inner_schema = self._type_to_schema(non_none_args[0])
                    if has_none:
                        return {"anyOf": [inner_schema, {"type": "null"}]}
                    return inner_schema
                else:
                    schemas = [self._type_to_schema(a) for a in non_none_args]
                    if has_none:
                        schemas.append({"type": "null"})
                    return {"anyOf": schemas}
        except (ImportError, AttributeError):
            pass

        # Handle forward references (strings)
        if isinstance(tp, str):
            return {"type": "string"}

        # Fallback — treat as generic object
        return {}
