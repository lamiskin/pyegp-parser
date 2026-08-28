"""Data models for parsed EGP project structures."""

from .base import ElementMetadata
from .data import DataItem, DataModel
from .elements import ElementCategory, classify_element_type
from .external_file import ExternalFileItem
from .external_objects import ExternalObject
from .log_code import CodeElement, LogElement
from .process_flow import Connection, DAGModel, ProcessFlowContainer
from .project import (
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
from .query import (
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
from .shortcut import ShortCutToData, ShortCutToFile
from .tasks import (
    AppendTaskElement,
    CodeTaskElement,
    EGTaskElement,
    ExportTaskElement,
    ImportTaskElement,
    SubmitableElement,
)
from .visual_layout import (
    ProcessFlowControlState,
    TaskGraphic,
    TreeItem,
    VisualLayout,
)

__all__ = [
    # Tasks
    "AppendTaskElement",
    # Project
    "BinaryEntry",
    # Query
    "Calculation",
    # Log and Code
    "CodeElement",
    "CodeTaskElement",
    "CompletenessSummary",
    # Process flow
    "Connection",
    "DAGModel",
    # Data
    "DataItem",
    "DataModel",
    "EGTaskElement",
    # Elements classification
    "ElementCategory",
    # Base
    "ElementMetadata",
    "ExportTaskElement",
    "Expression",
    # External files
    "ExternalFileItem",
    # External objects
    "ExternalObject",
    "FilterNode",
    "GroupItem",
    "ImportTaskElement",
    "InputTable",
    "JoinItem",
    "LogElement",
    "OrderItem",
    "Parameter",
    "ParsedProject",
    "ProcessFlowContainer",
    # Visual layout
    "ProcessFlowControlState",
    "ProjectLogInfo",
    "ProjectMetadata",
    "ProjectSettings",
    "QueryBuilderTablePosition",
    "QueryModel",
    "ResultItem",
    # Shortcuts
    "ShortCutToData",
    "ShortCutToFile",
    "SourceInfo",
    "SubmitableElement",
    "TaskGraphic",
    "TreeItem",
    "UnprocessedEntry",
    "VisualLayout",
    "classify_element_type",
]
