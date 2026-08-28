"""Tests for pyegp_parser.dag module."""

import pytest

from pyegp_parser.dag import DAG, Edge

# ---------------------------------------------------------------------------
# Edge dataclass tests
# ---------------------------------------------------------------------------


class TestEdge:
    """Tests for the Edge frozen dataclass."""

    def test_edge_creation(self):
        edge = Edge(source="A", target="B", resource_dependency=False)
        assert edge.source == "A"
        assert edge.target == "B"
        assert edge.resource_dependency is False

    def test_edge_is_frozen(self):
        edge = Edge(source="A", target="B", resource_dependency=True)
        with pytest.raises(Exception):  # FrozenInstanceError
            edge.source = "C"  # type: ignore

    def test_edge_equality(self):
        e1 = Edge(source="A", target="B", resource_dependency=False)
        e2 = Edge(source="A", target="B", resource_dependency=False)
        assert e1 == e2

    def test_edge_inequality_resource_flag(self):
        e1 = Edge(source="A", target="B", resource_dependency=False)
        e2 = Edge(source="A", target="B", resource_dependency=True)
        assert e1 != e2


# ---------------------------------------------------------------------------
# Empty DAG tests
# ---------------------------------------------------------------------------


class TestEmptyDAG:
    """Tests for an empty DAG."""

    def test_empty_dag_has_no_nodes(self):
        dag = DAG()
        assert dag.nodes == set()

    def test_empty_dag_has_no_edges(self):
        dag = DAG()
        assert dag.edges == []

    def test_empty_dag_topological_sort_returns_empty(self):
        dag = DAG()
        assert dag.topological_sort() == []

    def test_empty_dag_get_edges_for_node_returns_empty(self):
        dag = DAG()
        assert dag.get_edges_for_node("nonexistent") == []


# ---------------------------------------------------------------------------
# Single node, no edges
# ---------------------------------------------------------------------------


class TestSingleNode:
    """Tests for a DAG with a single node and no edges."""

    def test_single_node_added(self):
        dag = DAG()
        dag.add_node("A")
        assert "A" in dag.nodes
        assert len(dag.nodes) == 1

    def test_single_node_no_edges(self):
        dag = DAG()
        dag.add_node("A")
        assert dag.edges == []

    def test_single_node_topological_sort(self):
        dag = DAG()
        dag.add_node("A")
        assert dag.topological_sort() == ["A"]

    def test_single_node_get_edges_returns_empty(self):
        dag = DAG()
        dag.add_node("A")
        assert dag.get_edges_for_node("A") == []

    def test_add_node_idempotent(self):
        dag = DAG()
        dag.add_node("A")
        dag.add_node("A")
        assert len(dag.nodes) == 1


# ---------------------------------------------------------------------------
# Linear chain (A -> B -> C)
# ---------------------------------------------------------------------------


class TestLinearChain:
    """Tests for a linear chain DAG: A -> B -> C."""

    def setup_method(self):
        self.dag = DAG()
        self.dag.add_edge("A", "B")
        self.dag.add_edge("B", "C")

    def test_nodes_present(self):
        assert self.dag.nodes == {"A", "B", "C"}

    def test_edge_count(self):
        assert len(self.dag.edges) == 2

    def test_topological_sort_order(self):
        order = self.dag.topological_sort()
        assert order.index("A") < order.index("B")
        assert order.index("B") < order.index("C")

    def test_topological_sort_contains_all_nodes(self):
        order = self.dag.topological_sort()
        assert set(order) == {"A", "B", "C"}

    def test_get_edges_for_b(self):
        edges = self.dag.get_edges_for_node("B")
        assert len(edges) == 1
        assert edges[0].source == "A"
        assert edges[0].target == "B"

    def test_get_edges_for_a_is_empty(self):
        assert self.dag.get_edges_for_node("A") == []

    def test_get_edges_for_c(self):
        edges = self.dag.get_edges_for_node("C")
        assert len(edges) == 1
        assert edges[0].source == "B"
        assert edges[0].target == "C"


# ---------------------------------------------------------------------------
# Diamond pattern (A -> B, A -> C, B -> D, C -> D)
# ---------------------------------------------------------------------------


class TestDiamondPattern:
    """Tests for a diamond DAG: A -> B -> D and A -> C -> D."""

    def setup_method(self):
        self.dag = DAG()
        self.dag.add_edge("A", "B")
        self.dag.add_edge("A", "C")
        self.dag.add_edge("B", "D")
        self.dag.add_edge("C", "D")

    def test_nodes_present(self):
        assert self.dag.nodes == {"A", "B", "C", "D"}

    def test_edge_count(self):
        assert len(self.dag.edges) == 4

    def test_topological_sort_a_before_b_and_c(self):
        order = self.dag.topological_sort()
        assert order.index("A") < order.index("B")
        assert order.index("A") < order.index("C")

    def test_topological_sort_b_and_c_before_d(self):
        order = self.dag.topological_sort()
        assert order.index("B") < order.index("D")
        assert order.index("C") < order.index("D")

    def test_topological_sort_contains_all_nodes(self):
        order = self.dag.topological_sort()
        assert set(order) == {"A", "B", "C", "D"}

    def test_get_edges_for_d_has_two_incoming(self):
        edges = self.dag.get_edges_for_node("D")
        assert len(edges) == 2
        sources = {e.source for e in edges}
        assert sources == {"B", "C"}

    def test_get_edges_for_a_is_empty(self):
        assert self.dag.get_edges_for_node("A") == []


# ---------------------------------------------------------------------------
# Cycle detection (A -> B -> C -> A)
# ---------------------------------------------------------------------------


class TestCycleDetection:
    """Tests for cycle detection raising ValueError."""

    def test_simple_cycle_raises_value_error(self):
        dag = DAG()
        dag.add_edge("A", "B")
        dag.add_edge("B", "C")
        dag.add_edge("C", "A")
        with pytest.raises(ValueError, match="circular dependency"):
            dag.topological_sort()

    def test_cycle_error_includes_node_ids(self):
        dag = DAG()
        dag.add_edge("A", "B")
        dag.add_edge("B", "C")
        dag.add_edge("C", "A")
        with pytest.raises(ValueError) as exc_info:
            dag.topological_sort()
        error_msg = str(exc_info.value)
        # All cycle nodes should be mentioned
        assert "A" in error_msg
        assert "B" in error_msg
        assert "C" in error_msg

    def test_partial_cycle_includes_only_cycle_nodes(self):
        """A -> B -> C -> B (cycle), D is reachable from A but not in cycle."""
        dag = DAG()
        dag.add_edge("A", "B")
        dag.add_edge("B", "C")
        dag.add_edge("C", "B")  # Creates cycle between B and C
        dag.add_edge("A", "D")  # D is fine, no cycle
        with pytest.raises(ValueError) as exc_info:
            dag.topological_sort()
        error_msg = str(exc_info.value)
        assert "B" in error_msg
        assert "C" in error_msg


# ---------------------------------------------------------------------------
# Self-loop detection
# ---------------------------------------------------------------------------


class TestSelfLoop:
    """Tests for self-loop cycle detection."""

    def test_self_loop_raises_value_error(self):
        dag = DAG()
        dag.add_edge("A", "A")
        with pytest.raises(ValueError, match="circular dependency"):
            dag.topological_sort()

    def test_self_loop_error_includes_node_id(self):
        dag = DAG()
        dag.add_edge("X", "X")
        with pytest.raises(ValueError) as exc_info:
            dag.topological_sort()
        assert "X" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Resource vs execution dependency edges
# ---------------------------------------------------------------------------


class TestResourceDependency:
    """Tests for resource_dependency flag on edges."""

    def test_default_is_execution_dependency(self):
        dag = DAG()
        dag.add_edge("A", "B")
        assert dag.edges[0].resource_dependency is False

    def test_resource_dependency_true(self):
        dag = DAG()
        dag.add_edge("A", "B", resource_dependency=True)
        assert dag.edges[0].resource_dependency is True

    def test_mixed_dependencies(self):
        dag = DAG()
        dag.add_edge("A", "B", resource_dependency=False)
        dag.add_edge("A", "C", resource_dependency=True)
        execution_edges = [e for e in dag.edges if not e.resource_dependency]
        resource_edges = [e for e in dag.edges if e.resource_dependency]
        assert len(execution_edges) == 1
        assert len(resource_edges) == 1
        assert execution_edges[0].target == "B"
        assert resource_edges[0].target == "C"

    def test_resource_dependency_does_not_affect_sort(self):
        """Both types of edges enforce ordering."""
        dag = DAG()
        dag.add_edge("A", "B", resource_dependency=True)
        dag.add_edge("B", "C", resource_dependency=False)
        order = dag.topological_sort()
        assert order.index("A") < order.index("B")
        assert order.index("B") < order.index("C")


# ---------------------------------------------------------------------------
# get_edges_for_node returns correct incoming edges
# ---------------------------------------------------------------------------


class TestGetEdgesForNode:
    """Tests for get_edges_for_node returning incoming edges."""

    def test_node_with_no_incoming_edges(self):
        dag = DAG()
        dag.add_edge("A", "B")
        dag.add_edge("A", "C")
        assert dag.get_edges_for_node("A") == []

    def test_node_with_single_incoming_edge(self):
        dag = DAG()
        dag.add_edge("A", "B")
        edges = dag.get_edges_for_node("B")
        assert len(edges) == 1
        assert edges[0] == Edge(source="A", target="B", resource_dependency=False)

    def test_node_with_multiple_incoming_edges(self):
        dag = DAG()
        dag.add_edge("A", "D")
        dag.add_edge("B", "D")
        dag.add_edge("C", "D")
        edges = dag.get_edges_for_node("D")
        assert len(edges) == 3
        sources = {e.source for e in edges}
        assert sources == {"A", "B", "C"}

    def test_node_with_mixed_dependency_types(self):
        dag = DAG()
        dag.add_edge("A", "B", resource_dependency=True)
        dag.add_edge("C", "B", resource_dependency=False)
        edges = dag.get_edges_for_node("B")
        assert len(edges) == 2
        resource_edges = [e for e in edges if e.resource_dependency]
        execution_edges = [e for e in edges if not e.resource_dependency]
        assert len(resource_edges) == 1
        assert resource_edges[0].source == "A"
        assert len(execution_edges) == 1
        assert execution_edges[0].source == "C"

    def test_nonexistent_node_returns_empty(self):
        dag = DAG()
        dag.add_edge("A", "B")
        assert dag.get_edges_for_node("Z") == []


# ---------------------------------------------------------------------------
# Topological order validity
# ---------------------------------------------------------------------------


class TestTopologicalOrderValidity:
    """Tests that topological order is valid (every edge goes forward)."""

    def test_all_edges_go_forward_linear(self):
        dag = DAG()
        dag.add_edge("A", "B")
        dag.add_edge("B", "C")
        dag.add_edge("C", "D")
        order = dag.topological_sort()
        for edge in dag.edges:
            assert order.index(edge.source) < order.index(edge.target)

    def test_all_edges_go_forward_diamond(self):
        dag = DAG()
        dag.add_edge("A", "B")
        dag.add_edge("A", "C")
        dag.add_edge("B", "D")
        dag.add_edge("C", "D")
        order = dag.topological_sort()
        for edge in dag.edges:
            assert order.index(edge.source) < order.index(edge.target)

    def test_all_edges_go_forward_complex(self):
        """A more complex graph with multiple paths."""
        dag = DAG()
        dag.add_edge("A", "B")
        dag.add_edge("A", "C")
        dag.add_edge("B", "D")
        dag.add_edge("C", "D")
        dag.add_edge("D", "E")
        dag.add_edge("B", "E")
        dag.add_edge("A", "E")
        order = dag.topological_sort()
        for edge in dag.edges:
            assert order.index(edge.source) < order.index(edge.target)

    def test_disconnected_components(self):
        """DAG with multiple disconnected subgraphs."""
        dag = DAG()
        dag.add_edge("A", "B")
        dag.add_edge("C", "D")
        dag.add_node("E")
        order = dag.topological_sort()
        assert set(order) == {"A", "B", "C", "D", "E"}
        assert order.index("A") < order.index("B")
        assert order.index("C") < order.index("D")

    def test_wide_graph_all_edges_forward(self):
        """Single source with many targets."""
        dag = DAG()
        targets = [f"T{i}" for i in range(10)]
        for t in targets:
            dag.add_edge("root", t)
        order = dag.topological_sort()
        for edge in dag.edges:
            assert order.index(edge.source) < order.index(edge.target)
