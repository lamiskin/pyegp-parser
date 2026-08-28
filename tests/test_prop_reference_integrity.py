"""Property-based test for reference integrity in serialized EGP project JSON.

**Validates: Requirements 17.4**

Uses Hypothesis to verify that:
- Property 11: Reference Integrity — every internal ID reference in the serialized
  JSON document (parent_id fields, input_list entries, connection source_id/target_id,
  shortcut_list entries) resolves to a defined entity within the same document.

Strategy:
- Generate a set of element IDs first
- Generate data items with IDs from that set
- Generate shortcuts that reference IDs from data items
- Generate process flow connections that reference element IDs
- This ensures reference integrity by construction, then validates
  the property holds after serialization via to_dict()
"""

import string

from hypothesis import given, settings
from hypothesis import strategies as st

from pyegp_parser.models.base import ElementMetadata
from pyegp_parser.models.data import DataItem, DataModel
from pyegp_parser.models.external_file import ExternalFileItem
from pyegp_parser.models.process_flow import Connection, DAGModel, ProcessFlowContainer
from pyegp_parser.models.project import ParsedProject, SourceInfo
from pyegp_parser.models.shortcut import ShortCutToData, ShortCutToFile
from pyegp_parser.models.tasks import (
    CodeTaskElement,
    SubmitableElement,
)
from pyegp_parser.serializer import to_dict

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Strategy for generating alphanumeric IDs
_id_chars = string.ascii_letters + string.digits
_element_id = st.text(alphabet=_id_chars, min_size=4, max_size=12)


@st.composite
def parsed_project_with_consistent_ids(draw):
    """Generate a ParsedProject where all ID references are consistent.

    Constructs a project with:
    - A pool of element IDs used across all components
    - Data items whose IDs come from a defined set
    - External file items whose IDs come from a defined set
    - Shortcuts that reference valid data/external file item IDs
    - Process flow connections that reference valid element IDs
    - Tasks with parent_id referencing valid shortcut/data IDs
    """
    # Generate a pool of unique element IDs
    num_elements = draw(st.integers(min_value=2, max_value=8))
    element_ids = draw(
        st.lists(
            _element_id,
            min_size=num_elements,
            max_size=num_elements,
            unique=True,
        )
    )

    # Generate data item IDs (subset or separate)
    num_data_items = draw(st.integers(min_value=1, max_value=4))
    data_item_ids = draw(
        st.lists(
            _element_id.filter(lambda x: x not in element_ids),
            min_size=num_data_items,
            max_size=num_data_items,
            unique=True,
        )
    )

    # Generate external file IDs
    num_ext_files = draw(st.integers(min_value=0, max_value=3))
    ext_file_ids = draw(
        st.lists(
            _element_id.filter(
                lambda x: x not in element_ids and x not in data_item_ids
            ),
            min_size=num_ext_files,
            max_size=num_ext_files,
            unique=True,
        )
    )

    # All defined IDs in the project
    all_defined_ids = set(element_ids) | set(data_item_ids) | set(ext_file_ids)

    # --- Build Data Items ---
    # Each data item has shortcut_list entries that reference element_ids
    # (shortcuts are elements that point back to data items)
    data_items = []
    for di_id in data_item_ids:
        # shortcut_list contains IDs of ShortCutToData elements that reference this data item
        num_shortcuts = draw(
            st.integers(min_value=0, max_value=min(2, len(element_ids)))
        )
        shortcut_ids = draw(
            st.lists(
                st.sampled_from(element_ids),
                min_size=num_shortcuts,
                max_size=num_shortcuts,
                unique=True,
            )
        )
        data_items.append(
            DataItem(
                element=ElementMetadata(id=di_id, label=f"Data_{di_id}"),
                data_model=DataModel(display_name=f"Table_{di_id}"),
                shortcut_list=shortcut_ids,
            )
        )

    # --- Build External File Items ---
    ext_files = []
    for ef_id in ext_file_ids:
        num_shortcuts = draw(
            st.integers(min_value=0, max_value=min(2, len(element_ids)))
        )
        shortcut_ids = draw(
            st.lists(
                st.sampled_from(element_ids),
                min_size=num_shortcuts,
                max_size=num_shortcuts,
                unique=True,
            )
        )
        ext_files.append(
            ExternalFileItem(
                element=ElementMetadata(id=ef_id, label=f"File_{ef_id}"),
                shortcut_list=shortcut_ids,
                file_type_type="CSV",
            )
        )

    # --- Build Elements (shortcuts, tasks, code tasks) ---
    elements = []

    # Create some ShortCutToData elements referencing data items
    num_shortcut_data = draw(
        st.integers(min_value=1, max_value=min(3, len(element_ids)))
    )
    shortcut_data_indices = draw(
        st.lists(
            st.integers(min_value=0, max_value=len(element_ids) - 1),
            min_size=num_shortcut_data,
            max_size=num_shortcut_data,
            unique=True,
        )
    )
    for idx in shortcut_data_indices:
        eid = element_ids[idx]
        # parent_id references a data item
        parent = draw(st.sampled_from(data_item_ids))
        # input_list references other element IDs
        num_inputs = draw(st.integers(min_value=0, max_value=min(2, len(element_ids))))
        input_ids = draw(
            st.lists(
                st.sampled_from(element_ids),
                min_size=num_inputs,
                max_size=num_inputs,
                unique=True,
            )
        )
        elements.append(
            ShortCutToData(
                metadata=ElementMetadata(id=eid, label=f"SC_{eid}"),
                parent_id=parent,
                input_list=input_ids,
            )
        )

    # Create some ShortCutToFile elements if external files exist
    if ext_file_ids:
        remaining_ids = [
            eid
            for eid in element_ids
            if eid not in [e.metadata.id for e in elements if e.metadata]
        ]
        if remaining_ids:
            num_shortcut_file = draw(
                st.integers(min_value=0, max_value=min(2, len(remaining_ids)))
            )
            shortcut_file_ids_to_use = draw(
                st.lists(
                    st.sampled_from(remaining_ids),
                    min_size=num_shortcut_file,
                    max_size=num_shortcut_file,
                    unique=True,
                )
            )
            for eid in shortcut_file_ids_to_use:
                parent = draw(st.sampled_from(ext_file_ids))
                elements.append(
                    ShortCutToFile(
                        metadata=ElementMetadata(id=eid, label=f"SCF_{eid}"),
                        parent_id=parent,
                        input_list=[],
                    )
                )

    # Create some task elements with parent_id references
    used_ids = {e.metadata.id for e in elements if e.metadata}
    remaining_ids = [eid for eid in element_ids if eid not in used_ids]
    for eid in remaining_ids:
        # Tasks can have parent_id referencing data items or shortcuts
        valid_parents = data_item_ids + [e.metadata.id for e in elements if e.metadata]
        parent = draw(st.sampled_from(valid_parents)) if valid_parents else None
        elements.append(
            CodeTaskElement(
                metadata=ElementMetadata(id=eid, label=f"Code_{eid}"),
                submitable=SubmitableElement(),
                code_content="/* generated */",
            )
        )

    # --- Build Process Flow Container with connections ---
    # Connections reference element IDs (both source and target must be in element_ids)
    num_connections = draw(
        st.integers(min_value=0, max_value=min(4, len(element_ids) - 1))
    )
    connections = []
    for _ in range(num_connections):
        source = draw(st.sampled_from(element_ids))
        target = draw(st.sampled_from(element_ids).filter(lambda t, s=source: t != s))
        resource_dep = draw(st.booleans())
        connections.append(
            Connection(
                source_id=source, target_id=target, resource_dependency=resource_dep
            )
        )

    container = ProcessFlowContainer(
        metadata=ElementMetadata(
            id=draw(_element_id.filter(lambda x: x not in all_defined_ids)),
            label="Process Flow 1",
        ),
        dag=DAGModel(
            nodes=element_ids[:],
            connections=connections,
        ),
    )

    # Add the container ID to our defined set
    all_defined_ids.add(container.metadata.id)

    # --- Assemble ParsedProject ---
    project = ParsedProject(
        source=SourceInfo(
            file_path="/test/project.egp",
            file_name="project.egp",
            file_size_bytes=1024,
            parsed_at="2024-01-01T00:00:00",
            total_zip_entries=10,
        ),
        data_list=data_items,
        external_files=ext_files,
        elements=elements,
        containers=[container],
    )

    return project, all_defined_ids


# ---------------------------------------------------------------------------
# Helper functions for walking JSON dict tree
# ---------------------------------------------------------------------------


def collect_defined_ids(json_dict: dict) -> set[str]:
    """Walk the JSON dict tree and collect all defined entity IDs.

    Defined IDs come from:
    - elements[].metadata.id
    - data_list[].element.id
    - external_files[].element.id
    - containers[].metadata.id
    - containers[].dag.nodes[]
    """
    defined = set()

    # Data list item IDs
    for item in json_dict.get("data_list", []) or []:
        if isinstance(item, dict):
            elem = item.get("element")
            if isinstance(elem, dict) and elem.get("id"):
                defined.add(elem["id"])

    # External file item IDs
    for item in json_dict.get("external_files", []) or []:
        if isinstance(item, dict):
            elem = item.get("element")
            if isinstance(elem, dict) and elem.get("id"):
                defined.add(elem["id"])

    # Element IDs
    for item in json_dict.get("elements", []) or []:
        if isinstance(item, dict):
            meta = item.get("metadata")
            if isinstance(meta, dict) and meta.get("id"):
                defined.add(meta["id"])

    # Container IDs and DAG nodes
    for container in json_dict.get("containers", []) or []:
        if isinstance(container, dict):
            meta = container.get("metadata")
            if isinstance(meta, dict) and meta.get("id"):
                defined.add(meta["id"])
            dag = container.get("dag")
            if isinstance(dag, dict):
                for node_id in dag.get("nodes", []) or []:
                    if node_id:
                        defined.add(node_id)

    return defined


def collect_referenced_ids(json_dict: dict) -> set[str]:
    """Walk the JSON dict tree and collect all ID references.

    Referenced IDs come from:
    - elements[].parent_id (shortcuts and tasks)
    - elements[].input_list[] (shortcuts)
    - containers[].dag.connections[].source_id
    - containers[].dag.connections[].target_id
    - data_list[].shortcut_list[]
    - external_files[].shortcut_list[]
    """
    referenced = set()

    # Element references: parent_id, input_list
    for item in json_dict.get("elements", []) or []:
        if isinstance(item, dict):
            parent_id = item.get("parent_id")
            if parent_id:
                referenced.add(parent_id)
            for input_id in item.get("input_list", []) or []:
                if input_id:
                    referenced.add(input_id)

    # Container connection references
    for container in json_dict.get("containers", []) or []:
        if isinstance(container, dict):
            dag = container.get("dag")
            if isinstance(dag, dict):
                for conn in dag.get("connections", []) or []:
                    if isinstance(conn, dict):
                        source = conn.get("source_id")
                        target = conn.get("target_id")
                        if source:
                            referenced.add(source)
                        if target:
                            referenced.add(target)

    # Data item shortcut_list references
    for item in json_dict.get("data_list", []) or []:
        if isinstance(item, dict):
            for sc_id in item.get("shortcut_list", []) or []:
                if sc_id:
                    referenced.add(sc_id)

    # External file shortcut_list references
    for item in json_dict.get("external_files", []) or []:
        if isinstance(item, dict):
            for sc_id in item.get("shortcut_list", []) or []:
                if sc_id:
                    referenced.add(sc_id)

    return referenced


# ---------------------------------------------------------------------------
# Property Test
# ---------------------------------------------------------------------------


class TestReferenceIntegrity:
    """**Validates: Requirements 17.4**"""

    @given(data=parsed_project_with_consistent_ids())
    @settings(max_examples=30)
    def test_property_11_all_id_references_resolve_to_defined_entities(self, data):
        """Property 11: Reference Integrity.

        Parse valid EGP project structures; walk JSON checking all internal ID
        references resolve to defined entities.

        Every referenced ID (parent_id, input_list entries, connection
        source_id/target_id, shortcut_list entries) must exist in the set
        of defined entity IDs.
        """
        project, expected_defined_ids = data

        # Serialize to dict using to_dict()
        json_dict = to_dict(project)

        # Collect all defined IDs from the serialized structure
        defined_ids = collect_defined_ids(json_dict)

        # Collect all referenced IDs from the serialized structure
        referenced_ids = collect_referenced_ids(json_dict)

        # Assert every referenced ID exists in the defined set
        unresolved = referenced_ids - defined_ids
        assert unresolved == set(), (
            f"Found unresolved ID references: {unresolved}. "
            f"Defined IDs: {sorted(defined_ids)}. "
            f"Referenced IDs: {sorted(referenced_ids)}"
        )
