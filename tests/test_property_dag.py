"""Property-based tests for DAG construction and cycle detection.

**Validates: Requirements 6.3, 6.4, 6.5, 6.6, 6.7**

Uses Hypothesis to verify:
- Property 5: DAG Construction and Topological Ordering (task 6.3)
- Property 6: Cycle Detection — cyclic PFD XML raises ValueError with cycle node IDs (task 6.4)
"""

import string
import xml.etree.ElementTree as ET

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pyegp_parser.parsers.pfd_parser import parse_process_flow

# ---------------------------------------------------------------------------
# Strategies for generating node IDs
# ---------------------------------------------------------------------------

_node_id = st.text(
    alphabet=string.ascii_letters + string.digits + "-_",
    min_size=1,
    max_size=20,
).filter(lambda s: s.strip() != "")


# ---------------------------------------------------------------------------
# Strategy: Generate a random acyclic graph
# ---------------------------------------------------------------------------


@st.composite
def acyclic_graph(draw):
    """Generate a random acyclic graph specification.

    Returns a tuple of (node_ids, edges) where:
    - node_ids: list of unique node ID strings
    - edges: list of (source_id, target_id, resource_dependency) tuples

    Edges only go from lower-indexed to higher-indexed nodes, guaranteeing
    no cycles.
    """
    # Generate between 1 and 15 unique node IDs
    n = draw(st.integers(min_value=1, max_value=15))
    node_ids = draw(
        st.lists(
            _node_id,
            min_size=n,
            max_size=n,
            unique=True,
        )
    )

    # For each pair (i, j) where i < j, randomly decide whether to add an edge
    edges = []
    for i in range(len(node_ids)):
        for j in range(i + 1, len(node_ids)):
            add_edge = draw(st.booleans())
            if add_edge:
                resource_dep = draw(st.booleans())
                edges.append((node_ids[i], node_ids[j], resource_dep))

    return node_ids, edges


# ---------------------------------------------------------------------------
# Helper: Build PFD XML Element from a graph (nodes + edges)
# ---------------------------------------------------------------------------


def _build_pfd_xml(
    nodes: list[str],
    edges: list[tuple[str, str, bool]],
) -> ET.Element:
    """Build a ProcessFlowContainer XML element from nodes and edges.

    Args:
        nodes: List of node IDs.
        edges: List of (source, target, resource_dependency) tuples.
            Edge means source must run before target, so target depends on source.

    Returns:
        An ET.Element representing the ProcessFlowContainer with PFD section.
    """
    root = ET.Element(
        "Element",
        attrib={
            "Type": "SAS.EG.ProjectElements.ProcessFlowContainer",
            "Label": "TestPF",
            "ID": "pf-test",
        },
    )
    pfd = ET.SubElement(root, "PFD")

    # Build adjacency: target -> list of (source, resource_dep)
    deps_map: dict[str, list[tuple[str, bool]]] = {n: [] for n in nodes}
    for source, target, res_dep in edges:
        if target in deps_map:
            deps_map[target].append((source, res_dep))

    for node_id in nodes:
        process = ET.SubElement(pfd, "Process")
        elem = ET.SubElement(process, "Element", attrib={"ID": node_id})
        node_deps = deps_map.get(node_id, [])
        if node_deps:
            dependencies = ET.SubElement(process, "Dependencies")
            for dep_source, res_dep in node_deps:
                dep_elem = ET.SubElement(dependencies, "DepID")
                dep_elem.text = dep_source
                if res_dep:
                    dep_elem.set("ResourceDependency", "True")

    return root


# ---------------------------------------------------------------------------
# Property 5: DAG Construction and Topological Ordering
# ---------------------------------------------------------------------------


class TestDAGConstructionAndTopologicalOrdering:
    """**Validates: Requirements 6.3, 6.4, 6.5, 6.6**

    Property 5: Generate random acyclic graphs as PFD XML; verify N nodes,
    E edges, and valid topological ordering.
    """

    @given(data=acyclic_graph())
    @settings(max_examples=300)
    def test_p1_node_count_matches_process_entries(self, data):
        """P1: Number of nodes in result matches number of Process entries.

        Every Process entry in the PFD should appear as a node in the DAGModel.
        """
        node_ids, edges = data
        container_xml = _build_pfd_xml(node_ids, edges)
        result = parse_process_flow(container_xml)

        assert len(result.nodes) == len(node_ids), (
            f"Expected {len(node_ids)} nodes, got {len(result.nodes)}. "
            f"Missing: {set(node_ids) - set(result.nodes)}"
        )
        # All node IDs should be present in the result
        assert set(result.nodes) == set(node_ids)

    @given(data=acyclic_graph())
    @settings(max_examples=300)
    def test_p2_connection_count_matches_edge_count(self, data):
        """P2: Number of connections matches number of edges in the graph.

        Every edge in the generated acyclic graph should produce exactly one
        Connection in the result.
        """
        node_ids, edges = data
        container_xml = _build_pfd_xml(node_ids, edges)
        result = parse_process_flow(container_xml)

        assert len(result.connections) == len(edges), (
            f"Expected {len(edges)} connections, got {len(result.connections)}"
        )

    @given(data=acyclic_graph())
    @settings(max_examples=300)
    def test_p3_topological_order_valid(self, data):
        """P3: Topological order is valid.

        For every connection, the source must appear before the target in
        the nodes list (which is in topological order).
        """
        node_ids, edges = data
        container_xml = _build_pfd_xml(node_ids, edges)
        result = parse_process_flow(container_xml)

        # Build position index for quick lookup
        position = {node_id: idx for idx, node_id in enumerate(result.nodes)}

        for conn in result.connections:
            source_pos = position[conn.source_id]
            target_pos = position[conn.target_id]
            assert source_pos < target_pos, (
                f"Invalid topological order: source '{conn.source_id}' at "
                f"position {source_pos} should appear before target "
                f"'{conn.target_id}' at position {target_pos}"
            )

    @given(data=acyclic_graph())
    @settings(max_examples=300)
    def test_p4_resource_dependency_flags_preserved(self, data):
        """P4: ResourceDependency flags are correctly preserved.

        Each connection's resource_dependency flag should match the
        corresponding edge's flag from the generated graph.
        """
        node_ids, edges = data
        container_xml = _build_pfd_xml(node_ids, edges)
        result = parse_process_flow(container_xml)

        # Build a set of expected edges as (source, target, resource_dep) tuples
        expected_edges = {
            (source_id, target_id, resource_dep)
            for source_id, target_id, resource_dep in edges
        }

        # Build actual edges from connections
        actual_edges = {
            (conn.source_id, conn.target_id, conn.resource_dependency)
            for conn in result.connections
        }

        assert actual_edges == expected_edges, (
            f"Edge mismatch.\n"
            f"Missing from actual: {expected_edges - actual_edges}\n"
            f"Extra in actual: {actual_edges - expected_edges}"
        )


# ---------------------------------------------------------------------------
# Strategy: Generate a graph that CONTAINS at least one cycle
# ---------------------------------------------------------------------------


@st.composite
def cyclic_graph(draw):
    """Generate a graph with at least one guaranteed cycle.

    Strategy:
    1. Generate N >= 2 unique node IDs
    2. Pick a subset of at least 2 nodes and create a cycle among them
    3. Optionally add extra random edges

    Returns:
        Tuple of (nodes, edges, cycle_node_ids) where edges is list of
        (source, target, resource_dep) tuples and cycle_node_ids is the set
        of IDs participating in the guaranteed cycle.
    """
    # Generate between 2 and 10 unique node IDs
    n = draw(st.integers(min_value=2, max_value=10))
    node_ids = draw(
        st.lists(
            _node_id,
            min_size=n,
            max_size=n,
            unique=True,
        )
    )

    # Pick a subset of at least 2 nodes for the cycle
    cycle_size = draw(st.integers(min_value=2, max_value=len(node_ids)))
    # Use a permutation of the first cycle_size elements
    cycle_indices = draw(st.permutations(list(range(len(node_ids)))))
    cycle_node_indices = cycle_indices[:cycle_size]
    cycle_nodes = [node_ids[i] for i in cycle_node_indices]

    # Create directed cycle: node[0] -> node[1] -> ... -> node[k-1] -> node[0]
    edges: list[tuple[str, str, bool]] = []
    for i in range(len(cycle_nodes)):
        source = cycle_nodes[i]
        target = cycle_nodes[(i + 1) % len(cycle_nodes)]
        res_dep = draw(st.booleans())
        edges.append((source, target, res_dep))

    # Optionally add extra random edges (may or may not create additional cycles)
    num_extra = draw(st.integers(min_value=0, max_value=5))
    for _ in range(num_extra):
        src = draw(st.sampled_from(node_ids))
        tgt = draw(st.sampled_from(node_ids))
        if src != tgt:
            res_dep = draw(st.booleans())
            edges.append((src, tgt, res_dep))

    return node_ids, edges, set(cycle_nodes)


# ---------------------------------------------------------------------------
# Property 6: Cycle Detection
# ---------------------------------------------------------------------------


class TestCycleDetection:
    """**Validates: Requirements 6.7**

    Property 6: Generate PFD XML containing at least one cycle; verify
    ValueError raised with cycle node IDs.
    """

    @given(data=cyclic_graph())
    @settings(max_examples=200)
    def test_cyclic_graph_raises_value_error(self, data):
        """Cyclic PFD XML must raise ValueError with 'circular dependency' message."""
        node_ids, edges, cycle_nodes = data

        # Build PFD XML with the cyclic graph
        pfd_elem = _build_pfd_xml(node_ids, edges)

        # parse_process_flow must raise ValueError
        with pytest.raises(ValueError, match="circular dependency"):
            parse_process_flow(pfd_elem)

    @given(data=cyclic_graph())
    @settings(max_examples=200)
    def test_cycle_error_mentions_participating_node_ids(self, data):
        """The ValueError message must mention at least some cycle participant IDs."""
        node_ids, edges, cycle_nodes = data

        # Build PFD XML with the cyclic graph
        pfd_elem = _build_pfd_xml(node_ids, edges)

        with pytest.raises(ValueError) as exc_info:
            parse_process_flow(pfd_elem)

        error_message = str(exc_info.value)

        # At least one of the cycle participant node IDs must appear in the error
        found_any = any(node_id in error_message for node_id in cycle_nodes)
        assert found_any, (
            f"ValueError message does not mention any cycle node IDs.\n"
            f"Cycle nodes: {cycle_nodes}\n"
            f"Error message: {error_message}"
        )
