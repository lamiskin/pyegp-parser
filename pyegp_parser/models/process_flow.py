"""Process flow models for EGP project DAG structures."""

from dataclasses import dataclass, field

from .base import ElementMetadata


@dataclass
class Connection:
    """A directed edge in the process flow DAG.

    Represents a dependency relationship where source_id must
    complete before target_id can execute.
    """

    source_id: str
    target_id: str
    resource_dependency: bool


@dataclass
class DAGModel:
    """Serializable representation of the process flow DAG.

    Contains the topologically sorted node list, all connections,
    and any warnings generated during DAG construction (e.g.
    dangling references).
    """

    nodes: list[str] = field(default_factory=list)  # Element IDs in topological order
    connections: list[Connection] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class ProcessFlowContainer:
    """A process flow container element with its dependency graph.

    Represents a top-level grouping of tasks in an EGP project
    with their execution ordering defined by the DAG.
    """

    metadata: ElementMetadata | None = None
    dag: DAGModel | None = None
