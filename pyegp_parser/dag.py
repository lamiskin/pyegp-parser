"""DAG data structure with topological sort using Kahn's algorithm."""

from collections import deque
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Edge:
    """A directed edge in the process flow DAG.

    Attributes:
        source: Dependency element ID (runs first).
        target: Dependent element ID (runs after).
        resource_dependency: Whether this is a resource dependency (vs execution).
    """

    source: str  # dependency element ID (runs first)
    target: str  # dependent element ID (runs after)
    resource_dependency: bool


@dataclass
class DAG:
    """Directed Acyclic Graph for process flow execution ordering.

    Supports adding nodes and edges, topological sorting via Kahn's algorithm,
    and querying incoming edges for a given node.
    """

    nodes: set[str] = field(default_factory=set)
    edges: list[Edge] = field(default_factory=list)
    _adjacency: dict[str, list[str]] = field(default_factory=dict, repr=False)
    _in_degree: dict[str, int] = field(default_factory=dict, repr=False)

    def add_node(self, node_id: str) -> None:
        """Add a node to the graph."""
        self.nodes.add(node_id)
        if node_id not in self._adjacency:
            self._adjacency[node_id] = []
        if node_id not in self._in_degree:
            self._in_degree[node_id] = 0

    def add_edge(
        self, source: str, target: str, resource_dependency: bool = False
    ) -> None:
        """Add a directed edge (source -> target means source runs before target).

        Args:
            source: The dependency element ID (runs first).
            target: The dependent element ID (runs after).
            resource_dependency: Whether this is a resource dependency.
        """
        # Ensure both nodes exist
        self.add_node(source)
        self.add_node(target)
        edge = Edge(
            source=source, target=target, resource_dependency=resource_dependency
        )
        self.edges.append(edge)
        self._adjacency[source].append(target)
        self._in_degree[target] += 1

    def topological_sort(self) -> list[str]:
        """Return nodes in a valid execution order using Kahn's algorithm.

        Returns:
            List of node IDs in a valid topological order.

        Raises:
            ValueError: If the graph contains a cycle (includes cycle node IDs).
        """
        sorted_nodes: list[str] = []
        in_degree = dict(self._in_degree)
        queue = deque(n for n, d in in_degree.items() if d == 0)

        while queue:
            node = queue.popleft()
            sorted_nodes.append(node)
            for neighbor in self._adjacency.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(sorted_nodes) != len(self.nodes):
            cycle_nodes = [n for n in self.nodes if n not in sorted_nodes]
            raise ValueError(
                f"Process flow contains circular dependency involving: {cycle_nodes}"
            )
        return sorted_nodes

    def get_edges_for_node(self, node_id: str) -> list[Edge]:
        """Get all incoming edges (dependencies) for a node.

        Args:
            node_id: The element ID to query incoming edges for.

        Returns:
            List of Edge objects where this node is the target.
        """
        return [e for e in self.edges if e.target == node_id]
