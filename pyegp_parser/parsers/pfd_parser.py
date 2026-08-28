"""Process Flow Definition (PFD) parser.

Parses ProcessFlowContainer elements' PFD sections into DAGModel
representations, handling dependencies, ResourceDependency flags,
dangling references (with warnings), and cycle detection.
"""

import xml.etree.ElementTree as ET

from ..dag import DAG
from ..models.process_flow import Connection, DAGModel


def parse_process_flow(element_node: ET.Element) -> DAGModel:
    """Parse a ProcessFlowContainer element's PFD section into a DAGModel.

    Args:
        element_node: The XML Element node for a ProcessFlowContainer.

    Returns:
        DAGModel with nodes in topological order, connections, and warnings.

    Raises:
        ValueError: If PFD section is missing or cycle detected.
    """
    # Step 1: Find <PFD> child element
    pfd = element_node.find("PFD")
    if pfd is None:
        element_id = _get_element_id(element_node)
        raise ValueError(
            f"ProcessFlowContainer '{element_id}' is missing its process flow "
            f"definition (PFD section)"
        )

    dag = DAG()
    warnings: list[str] = []

    # Step 2: For each <Process> child in PFD, extract Element ID and add node
    for process in pfd.findall("Process"):
        node_id = _get_process_element_id(process)
        if node_id is None:
            continue
        dag.add_node(node_id)

    # Step 3: For each <Process>, extract Dependencies/DepID entries
    for process in pfd.findall("Process"):
        node_id = _get_process_element_id(process)
        if node_id is None:
            continue

        dependencies = process.find("Dependencies")
        if dependencies is None:
            continue

        for dep_id_elem in dependencies.findall("DepID"):
            # Read the text content (referenced element ID)
            referenced_id = dep_id_elem.text
            if referenced_id is None:
                continue
            referenced_id = referenced_id.strip()
            if not referenced_id:
                continue

            # Read ResourceDependency attribute (default "False")
            resource_dep_str = dep_id_elem.get("ResourceDependency", "False")
            resource_dependency = resource_dep_str.lower() == "true"

            # Check if referenced ID exists as a node in the PFD
            if referenced_id in dag.nodes:
                # Edge goes from dependency (source) to dependent (target)
                dag.add_edge(referenced_id, node_id, resource_dependency)
            else:
                # Dangling reference: warn and skip
                warnings.append(
                    f"DepID '{referenced_id}' referenced by process '{node_id}' "
                    f"does not exist in the process flow; skipping connection"
                )

    # Step 4: Build topological order (raises ValueError if cycle detected)
    sorted_nodes = dag.topological_sort()

    # Convert edges to Connection list
    connections = [
        Connection(
            source_id=edge.source,
            target_id=edge.target,
            resource_dependency=edge.resource_dependency,
        )
        for edge in dag.edges
    ]

    return DAGModel(
        nodes=sorted_nodes,
        connections=connections,
        warnings=warnings,
    )


def _get_process_element_id(process: ET.Element) -> str | None:
    """Extract the element ID from a Process node.

    Handles two layouts:
    1. EGP 8.x: ID stored as child text element of <Element>
       (e.g. <Process><Element><ID>...</ID></Element></Process>)
    2. Legacy: ID stored as attribute on <Element>
       (e.g. <Process><Element ID="..."/></Process>)

    Args:
        process: A <Process> XML element within a PFD.

    Returns:
        The element ID string, or None if not found.
    """
    elem = process.find("Element")
    if elem is None:
        return None

    # Try attribute first (legacy)
    node_id = elem.get("ID")
    if node_id:
        return node_id

    # EGP 8.x: ID as child text element
    id_child = elem.find("ID")
    if id_child is not None and id_child.text and id_child.text.strip():
        return id_child.text.strip()

    return None


def _get_element_id(element_node: ET.Element) -> str:
    """Get the ID of an element node, checking both attribute and child layouts.

    Args:
        element_node: An Element XML node.

    Returns:
        The element ID or "unknown" if not found.
    """
    # Try attribute
    eid = element_node.get("ID")
    if eid:
        return eid

    # Try inner Element child with ID child text
    inner = element_node.find("Element")
    if inner is not None:
        id_child = inner.find("ID")
        if id_child is not None and id_child.text and id_child.text.strip():
            return id_child.text.strip()

    return "unknown"
