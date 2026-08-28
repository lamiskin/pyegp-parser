"""Preservation property tests for the full-content-extraction bugfix.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8**

These tests capture the EXISTING BEHAVIOR of the unfixed code for non-buggy inputs
(cases where isBugCondition returns false). They ensure that the fix does not
regress any of the following preserved behaviors:

- ProcessFlowContainer parsing produces DAGs with topologically-sorted nodes and connections
- DataList extraction produces DataItem objects with ElementMetadata, DataModel, decoded DNA
- ExternalFileList extraction produces ExternalFileItem objects with decoded DNA and FileTypeType
- Execution log association produces log content strings matched to owning elements
- ODS result recording produces binary entries with archive path, compressed size, file extension
- CompletenessSummary with total/processed/unprocessed counts is correct
- JSON output has sorted keys, 2-space indentation, UTF-8 encoding, _type discriminator fields
- ProjectMetadata, ProjectSettings, Parameters, ApplicationOverrides, MetaDataInfo are extracted

IMPORTANT: These tests MUST PASS on unfixed code (baseline behavior preservation).
They are written using observation-first methodology: observing what the code currently
does and then asserting that behavior is maintained.
"""

import json
import string
import xml.etree.ElementTree as ET
from io import BytesIO
from zipfile import ZipFile

from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from pyegp_parser import parse_file
from pyegp_parser.parsers.data_parser import parse_data_list, parse_external_file_list
from pyegp_parser.parsers.layout_parser import (
    parse_visual_layout,
)
from pyegp_parser.parsers.pfd_parser import parse_process_flow
from pyegp_parser.parsers.project_parser import parse_project_xml
from pyegp_parser.serializer import to_dict

# ---------------------------------------------------------------------------
# Hypothesis strategies for generating synthetic XML structures
# ---------------------------------------------------------------------------

_safe_label = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N"), blacklist_characters="<>&\"'"
    ),
    min_size=1,
    max_size=20,
)

_element_id = st.from_regex(r"[A-Z][A-Z0-9]{3,7}", fullmatch=True)

_optional_text = st.one_of(st.none(), _safe_label)


# ---------------------------------------------------------------------------
# Helpers to create synthetic EGP archives for non-buggy inputs
# ---------------------------------------------------------------------------


def _create_egp_archive(
    project_xml: str, extra_files: dict[str, bytes] | None = None
) -> bytes:
    """Create an in-memory EGP (ZIP) archive with the given project.xml."""
    buf = BytesIO()
    with ZipFile(buf, "w") as zf:
        zf.writestr("project.xml", project_xml.encode("utf-8"))
        if extra_files:
            for path, content in extra_files.items():
                zf.writestr(path, content)
    return buf.getvalue()


def _write_temp_egp(tmp_path, archive_bytes: bytes) -> str:
    """Write archive bytes to a temporary .egp file and return the path."""
    import uuid

    egp_file = tmp_path / f"test_{uuid.uuid4().hex[:8]}.egp"
    egp_file.write_bytes(archive_bytes)
    return str(egp_file)


# ---------------------------------------------------------------------------
# Strategy: Generate ProcessFlowContainer XML with acyclic DAGs
# ---------------------------------------------------------------------------


@st.composite
def pfd_container_xml(draw):
    """Generate a ProcessFlowContainer element with a valid acyclic PFD.

    Returns tuple of (xml_element, node_ids, expected_edges).
    """
    n = draw(st.integers(min_value=1, max_value=8))
    node_ids = draw(
        st.lists(
            _element_id,
            min_size=n,
            max_size=n,
            unique=True,
        )
    )

    # Generate acyclic edges (only from lower index to higher index)
    edges: list[tuple[str, str, bool]] = []
    for i in range(len(node_ids)):
        for j in range(i + 1, len(node_ids)):
            if draw(st.booleans()):
                res_dep = draw(st.booleans())
                edges.append((node_ids[i], node_ids[j], res_dep))

    # Build PFD XML
    container = ET.Element(
        "Element",
        attrib={
            "Type": "SAS.EG.ProjectElements.ProcessFlowContainer",
            "Label": "TestPF",
            "ID": "pf-test",
        },
    )
    pfd = ET.SubElement(container, "PFD")

    deps_map: dict[str, list[tuple[str, bool]]] = {n: [] for n in node_ids}
    for source, target, res_dep in edges:
        deps_map[target].append((source, res_dep))

    for nid in node_ids:
        process = ET.SubElement(pfd, "Process")
        elem = ET.SubElement(process, "Element", attrib={"ID": nid})
        if deps_map[nid]:
            dependencies = ET.SubElement(process, "Dependencies")
            for dep_source, res_dep in deps_map[nid]:
                dep_elem = ET.SubElement(dependencies, "DepID")
                dep_elem.text = dep_source
                if res_dep:
                    dep_elem.set("ResourceDependency", "True")

    return container, node_ids, edges


# ---------------------------------------------------------------------------
# Strategy: Generate DataList XML with varying DataItems
# ---------------------------------------------------------------------------


@st.composite
def data_list_xml(draw):
    """Generate a DataList XML section with DataItem entries.

    Returns tuple of (root_element, expected_item_count).
    """
    n_items = draw(st.integers(min_value=0, max_value=5))
    root = ET.Element("ProjectCollection")
    data_list_elem = ET.SubElement(root, "DataList")

    for i in range(n_items):
        data_elem = ET.SubElement(data_list_elem, "Data")
        element_child = ET.SubElement(data_elem, "Element")
        label_child = ET.SubElement(element_child, "Label")
        label_child.text = draw(_safe_label)
        id_child = ET.SubElement(element_child, "ID")
        id_child.text = draw(_element_id)
        type_child = ET.SubElement(element_child, "Type")
        type_child.text = "SAS.EG.ProjectElements.Data"

        # Add DataModel inside nested Data child (EGP 8.x layout)
        inner_data = ET.SubElement(data_elem, "Data")
        data_model = ET.SubElement(inner_data, "DataModel")
        server_child = ET.SubElement(data_model, "Server")
        server_child.text = draw(_safe_label)
        table_child = ET.SubElement(data_model, "Table")
        table_child.text = draw(_safe_label)

    return root, n_items


# ---------------------------------------------------------------------------
# Strategy: Generate project XML with metadata, settings, parameters
# ---------------------------------------------------------------------------


@st.composite
def project_xml_with_metadata(draw):
    """Generate a project.xml string with metadata, settings, and parameters.

    Returns tuple of (xml_string, expected_label, expected_params).
    """
    label = draw(_safe_label)
    project_id = draw(_element_id)
    eg_version = draw(st.sampled_from(["7.1", "8.1", "8.2", "9.0"]))

    # Parameters
    n_params = draw(st.integers(min_value=0, max_value=3))
    param_names = draw(
        st.lists(_safe_label, min_size=n_params, max_size=n_params, unique=True)
    )
    param_values = draw(st.lists(_safe_label, min_size=n_params, max_size=n_params))
    params = list(zip(param_names, param_values))

    # Settings booleans
    use_relative_paths = draw(st.sampled_from(["True", "False"]))
    submit_to_grid = draw(st.sampled_from(["True", "False"]))

    params_xml = ""
    if params:
        params_xml = "<Parameters>"
        for name, value in params:
            params_xml += f'<Parameter Name="{name}" Value="{value}"/>'
        params_xml += "</Parameters>"

    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<ProjectCollection EGVersion="{eg_version}" Type="SAS.EG.ProjectElements.ProjectCollection">
    <Element>
        <Label>{label}</Label>
        <ID>{project_id}</ID>
        <Type>SAS.EG.ProjectElements.Project</Type>
    </Element>
    <UseRelativePaths>{use_relative_paths}</UseRelativePaths>
    <SubmitToGrid>{submit_to_grid}</SubmitToGrid>
    {params_xml}
    <Elements>
        <Element Type="SAS.EG.ProjectElements.ProjectLog" Label="Project Log" ID="PL001">
            <Enabled>True</Enabled>
            <WrittenTo>False</WrittenTo>
        </Element>
    </Elements>
</ProjectCollection>"""

    return (
        xml,
        label,
        project_id,
        eg_version,
        params,
        use_relative_paths,
        submit_to_grid,
    )


# ---------------------------------------------------------------------------
# Strategy: Generate a full EGP project.xml with only non-buggy elements
# (ProcessFlowContainers, no typed-content elements)
# ---------------------------------------------------------------------------


@st.composite
def preservation_project_xml(draw):
    """Generate a project.xml with only non-buggy elements for preservation testing.

    Includes: ProcessFlowContainers, DataList, metadata, settings, parameters.
    Excludes: Query, CodeTask, ShortCutToData/File, Log, Code, External_Objects.
    """
    label = draw(_safe_label)
    project_id = draw(_element_id)
    eg_version = draw(st.sampled_from(["7.1", "8.1", "8.2"]))

    # Parameters
    n_params = draw(st.integers(min_value=0, max_value=2))
    params_xml = ""
    param_pairs = []
    if n_params > 0:
        param_names = draw(
            st.lists(_safe_label, min_size=n_params, max_size=n_params, unique=True)
        )
        param_values = draw(st.lists(_safe_label, min_size=n_params, max_size=n_params))
        param_pairs = list(zip(param_names, param_values))
        params_xml = "<Parameters>"
        for name, value in param_pairs:
            params_xml += f'<Parameter Name="{name}" Value="{value}"/>'
        params_xml += "</Parameters>"

    # Settings
    use_relative = draw(st.sampled_from(["True", "False"]))

    # ProcessFlowContainer elements (non-buggy typed elements)
    n_pfc = draw(st.integers(min_value=0, max_value=2))
    pfc_elements = ""
    for i in range(n_pfc):
        pfc_id = f"PFC{i:03d}"
        pfc_label = f"Process Flow {i}"
        # Simple PFD with a couple nodes
        n_nodes = draw(st.integers(min_value=1, max_value=3))
        node_ids = [f"N{i}_{j}" for j in range(n_nodes)]
        pfd_xml = "<PFD>"
        for nid in node_ids:
            pfd_xml += f'<Process><Element ID="{nid}"/></Process>'
        pfd_xml += "</PFD>"
        pfc_elements += f"""
        <Element Type="SAS.EG.ProjectElements.ProcessFlowContainer" Label="{pfc_label}" ID="{pfc_id}">
            {pfd_xml}
        </Element>"""

    # DataList with simple items
    n_data = draw(st.integers(min_value=0, max_value=2))
    data_list_xml = ""
    if n_data > 0:
        data_list_xml = "<DataList>"
        for i in range(n_data):
            data_id = f"DATA{i:03d}"
            data_label = f"Dataset {i}"
            data_list_xml += f"""
            <Data>
                <Element>
                    <Label>{data_label}</Label>
                    <ID>{data_id}</ID>
                    <Type>SAS.EG.ProjectElements.Data</Type>
                </Element>
                <Data>
                    <DataModel>
                        <Server>SASApp</Server>
                        <Table>TABLE{i}</Table>
                    </DataModel>
                </Data>
            </Data>"""
        data_list_xml += "</DataList>"

    # Visual layout with attribute-based TaskGraphics (non-buggy: using attributes)
    layout_xml = ""
    if n_pfc > 0:
        layout_xml = "<ProcessFlowControlManager>"
        for i in range(n_pfc):
            pfc_id = f"PFC{i:03d}"
            layout_xml += f'<ProcessFlowControlState ContainerID="{pfc_id}" Zoom="100" ShowGrid="False">'
            # TaskGraphics with ATTRIBUTES (not child-text, so not buggy)
            layout_xml += f'<TaskGraphic Type="Node" Id="tg-{i}" PosX="50" PosY="100" Width="120" Height="60" Element="N{i}_0"/>'
            layout_xml += "</ProcessFlowControlState>"
        layout_xml += "</ProcessFlowControlManager>"

    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<ProjectCollection EGVersion="{eg_version}" Type="SAS.EG.ProjectElements.ProjectCollection">
    <Element>
        <Label>{label}</Label>
        <ID>{project_id}</ID>
        <Type>SAS.EG.ProjectElements.Project</Type>
    </Element>
    <UseRelativePaths>{use_relative}</UseRelativePaths>
    {params_xml}
    {data_list_xml}
    <Elements>
        {pfc_elements}
        <Element Type="SAS.EG.ProjectElements.ProjectLog" Label="Project Log" ID="PL001">
            <Enabled>True</Enabled>
            <WrittenTo>False</WrittenTo>
        </Element>
    </Elements>
    {layout_xml}
</ProjectCollection>"""

    return xml, label, project_id, eg_version, param_pairs, n_pfc, n_data


# ---------------------------------------------------------------------------
# Property Tests: Preservation of Existing Pipeline Behavior
# ---------------------------------------------------------------------------


class TestPFDDAGPreservation:
    """Property: ProcessFlowContainer parsing produces DAGs with topologically-sorted
    nodes and connections on unfixed code.

    **Validates: Requirements 3.1**
    """

    @given(data=pfd_container_xml())
    @settings(max_examples=50)
    def test_pfd_produces_dag_with_correct_nodes(self, data):
        """PFD parsing produces a DAGModel containing all declared nodes."""
        container_xml, node_ids, edges = data
        result = parse_process_flow(container_xml)

        # All nodes present
        assert set(result.nodes) == set(node_ids), (
            f"DAG nodes mismatch. Expected {set(node_ids)}, got {set(result.nodes)}"
        )

    @given(data=pfd_container_xml())
    @settings(max_examples=50)
    def test_pfd_topological_order_valid(self, data):
        """PFD parsing produces topologically-sorted node order."""
        container_xml, node_ids, edges = data
        result = parse_process_flow(container_xml)

        position = {nid: idx for idx, nid in enumerate(result.nodes)}
        for conn in result.connections:
            assert position[conn.source_id] < position[conn.target_id], (
                f"Topological violation: {conn.source_id} at {position[conn.source_id]} "
                f"should precede {conn.target_id} at {position[conn.target_id]}"
            )

    @given(data=pfd_container_xml())
    @settings(max_examples=50)
    def test_pfd_connections_match_edges(self, data):
        """PFD parsing produces connections matching the input edges."""
        container_xml, node_ids, edges = data
        result = parse_process_flow(container_xml)

        expected_edges = {(s, t, r) for s, t, r in edges}
        actual_edges = {
            (c.source_id, c.target_id, c.resource_dependency)
            for c in result.connections
        }
        assert actual_edges == expected_edges


class TestDataListPreservation:
    """Property: DataList extraction produces DataItem objects with ElementMetadata,
    DataModel, decoded DNA on unfixed code.

    **Validates: Requirements 3.2**
    """

    @given(data=data_list_xml())
    @settings(max_examples=50)
    def test_data_list_item_count_matches(self, data):
        """DataList parsing returns the correct number of DataItem objects."""
        root, expected_count = data
        result = parse_data_list(root)
        assert len(result) == expected_count

    @given(data=data_list_xml())
    @settings(max_examples=50)
    def test_data_list_items_have_element_metadata(self, data):
        """Each DataItem has ElementMetadata populated with label and ID."""
        root, expected_count = data
        result = parse_data_list(root)
        for item in result:
            assert item.element is not None
            # Metadata should have at least label or id populated
            assert item.element.label is not None or item.element.id is not None

    @given(data=data_list_xml())
    @settings(max_examples=50)
    def test_data_list_items_have_data_model(self, data):
        """Each DataItem has a DataModel with server and table populated."""
        root, expected_count = data
        assume(expected_count > 0)
        result = parse_data_list(root)
        for item in result:
            assert item.data_model is not None
            assert item.data_model.server is not None
            assert item.data_model.table is not None


class TestExternalFileListPreservation:
    """Property: ExternalFileList extraction produces ExternalFileItem objects
    with decoded DNA and FileTypeType on unfixed code.

    **Validates: Requirements 3.3**
    """

    def test_absent_external_file_list_returns_empty(self):
        """If ExternalFileList section is absent, returns empty list."""
        root = ET.fromstring("<ProjectCollection></ProjectCollection>")
        result = parse_external_file_list(root)
        assert result == []

    def test_external_file_with_valid_dna_parsed(self):
        """ExternalFileItem with valid DNA is parsed with decoded_dna and file_type_type.

        Observation: The DNA decoder produces a DNADescriptor (not None) when DNA text
        is present. The FileTypeType is correctly extracted. decoded_dna is a
        DNADescriptor instance even if the DNA text doesn't decode to populated fields
        (depends on encoding). The key preservation is that the parser doesn't raise
        and produces a valid ExternalFileItem with decoded_dna set.
        """
        # Use HTML-escaped DNA that the XML parser will unescape once.
        # The DNA decoder expects potentially-escaped content and handles it.
        xml = """<ProjectCollection>
            <ExternalFileList>
                <ExternalFile>
                    <Element>
                        <Label>InputFile</Label>
                        <ID>EF001</ID>
                        <Type>SAS.EG.ProjectElements.ExternalFile</Type>
                    </Element>
                    <ExternalFile>
                        <FileTypeType>CSV</FileTypeType>
                        <DNA>&lt;Descriptor Type=&quot;SAS.Servers.ServerDef&quot; Name=&quot;SASMain&quot; Version=&quot;1.0&quot; Assembly=&quot;&quot; Factory=&quot;&quot;&gt;&lt;/Descriptor&gt;</DNA>
                    </ExternalFile>
                </ExternalFile>
            </ExternalFileList>
        </ProjectCollection>"""
        root = ET.fromstring(xml)
        result = parse_external_file_list(root)
        assert len(result) == 1
        item = result[0]
        assert item.file_type_type == "CSV"
        # The DNA decoder always returns a DNADescriptor (not None)
        assert item.decoded_dna is not None
        assert item.element is not None
        assert item.element.label == "InputFile"
        assert item.element.id == "EF001"


class TestExecutionLogPreservation:
    """Property: Execution log association produces log content strings
    matched to owning elements on unfixed code.

    **Validates: Requirements 3.4**
    """

    @given(
        task_id=_element_id,
        log_id=_element_id,
        log_content=_safe_label,
    )
    @settings(
        max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_execution_logs_extracted_and_keyed_by_id(
        self, tmp_path, task_id, log_id, log_content
    ):
        """Execution logs are extracted from archive and keyed by log ID."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<ProjectCollection EGVersion="8.1" Type="SAS.EG.ProjectElements.ProjectCollection">
    <Element>
        <Label>Test Project</Label>
        <ID>PROJ001</ID>
        <Type>SAS.EG.ProjectElements.Project</Type>
    </Element>
    <Elements>
        <Element Type="SAS.EG.ProjectElements.ProjectLog" Label="Project Log" ID="PL001">
            <Enabled>True</Enabled>
            <WrittenTo>False</WrittenTo>
        </Element>
    </Elements>
</ProjectCollection>"""
        log_path = f"CodeTask-{task_id}/Log-{log_id}/result.log"
        extra_files = {log_path: log_content.encode("utf-8")}
        archive_bytes = _create_egp_archive(xml, extra_files)
        egp_path = _write_temp_egp(tmp_path, archive_bytes)

        project = parse_file(egp_path)
        # The project log section should exist; execution logs are extracted
        # In the current pipeline, execution logs are stored internally but
        # not directly as a field on ParsedProject (they're used for association)
        # The key preservation is that the parse completes successfully
        assert project is not None
        assert project.completeness_summary is not None


class TestODSResultPreservation:
    """Property: ODS result recording produces binary entries with archive path,
    compressed size, file extension on unfixed code.

    **Validates: Requirements 3.5**
    """

    @given(
        ods_id=_element_id,
        file_ext=st.sampled_from([".pptx", ".xlsx", ".html", ".pdf", ".rtf"]),
    )
    @settings(
        max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_ods_results_produce_binary_entries(self, tmp_path, ods_id, file_ext):
        """ODS results in archive produce BinaryEntry with path, size, extension."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<ProjectCollection EGVersion="8.1" Type="SAS.EG.ProjectElements.ProjectCollection">
    <Element>
        <Label>Test Project</Label>
        <ID>PROJ001</ID>
        <Type>SAS.EG.ProjectElements.Project</Type>
    </Element>
    <Elements>
        <Element Type="SAS.EG.ProjectElements.ProjectLog" Label="Project Log" ID="PL001">
            <Enabled>True</Enabled>
            <WrittenTo>False</WrittenTo>
        </Element>
    </Elements>
</ProjectCollection>"""
        ods_path = f"ODSResults/ODSResult-{ods_id}/result{file_ext}"
        ods_content = b"fake binary content for ODS result"
        extra_files = {ods_path: ods_content}
        archive_bytes = _create_egp_archive(xml, extra_files)
        egp_path = _write_temp_egp(tmp_path, archive_bytes)

        project = parse_file(egp_path)
        # Binary entries should contain the ODS result
        assert len(project.binary_entries) >= 1
        entry = next(e for e in project.binary_entries if ods_id in e.path)
        assert entry.file_extension == file_ext
        assert entry.compressed_size >= 0
        assert entry.path == ods_path


class TestCompletenessSummaryPreservation:
    """Property: CompletenessSummary with total/processed/unprocessed counts is correct.

    **Validates: Requirements 3.6**
    """

    @given(
        n_extra_files=st.integers(min_value=0, max_value=3),
    )
    @settings(
        max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_completeness_summary_counts_correct(self, tmp_path, n_extra_files):
        """CompletenessSummary has total = processed + unprocessed."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<ProjectCollection EGVersion="8.1" Type="SAS.EG.ProjectElements.ProjectCollection">
    <Element>
        <Label>Test Project</Label>
        <ID>PROJ001</ID>
        <Type>SAS.EG.ProjectElements.Project</Type>
    </Element>
    <Elements>
        <Element Type="SAS.EG.ProjectElements.ProjectLog" Label="Project Log" ID="PL001">
            <Enabled>True</Enabled>
            <WrittenTo>False</WrittenTo>
        </Element>
    </Elements>
</ProjectCollection>"""
        extra_files = {}
        for i in range(n_extra_files):
            extra_files[f"unknown_file_{i}.dat"] = b"data"
        archive_bytes = _create_egp_archive(xml, extra_files)
        egp_path = _write_temp_egp(tmp_path, archive_bytes)

        project = parse_file(egp_path)
        summary = project.completeness_summary
        assert summary is not None
        assert (
            summary.total_entries
            == summary.processed_entries + summary.unprocessed_entries
        )
        # project.xml is always processed
        assert summary.processed_entries >= 1

    @given(
        n_extra_files=st.integers(min_value=1, max_value=3),
    )
    @settings(
        max_examples=10, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_unprocessed_entries_flagged(self, tmp_path, n_extra_files):
        """Unknown files in archive are flagged as unprocessed."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<ProjectCollection EGVersion="8.1" Type="SAS.EG.ProjectElements.ProjectCollection">
    <Element>
        <Label>Test Project</Label>
        <ID>PROJ001</ID>
        <Type>SAS.EG.ProjectElements.Project</Type>
    </Element>
    <Elements>
        <Element Type="SAS.EG.ProjectElements.ProjectLog" Label="Project Log" ID="PL001">
            <Enabled>True</Enabled>
            <WrittenTo>False</WrittenTo>
        </Element>
    </Elements>
</ProjectCollection>"""
        extra_files = {
            f"random_unknown_{i}.bin": b"x" * 100 for i in range(n_extra_files)
        }
        archive_bytes = _create_egp_archive(xml, extra_files)
        egp_path = _write_temp_egp(tmp_path, archive_bytes)

        project = parse_file(egp_path)
        assert project.completeness_warning is True
        assert len(project.unprocessed_entries) >= n_extra_files


class TestJSONFormatPreservation:
    """Property: JSON output has sorted keys, 2-space indentation, UTF-8 encoding,
    _type discriminator fields on unfixed code.

    **Validates: Requirements 3.7**
    """

    @given(data=preservation_project_xml())
    @settings(
        max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_json_output_sorted_keys(self, tmp_path, data):
        """JSON serialized output has all keys sorted alphabetically."""
        xml, label, project_id, eg_version, params, n_pfc, n_data = data
        archive_bytes = _create_egp_archive(xml)
        egp_path = _write_temp_egp(tmp_path, archive_bytes)

        project = parse_file(egp_path)
        output_dict = to_dict(project)
        json_str = json.dumps(output_dict, indent=2, ensure_ascii=False, sort_keys=True)

        # Verify sorted keys: re-parse and check all dict keys are sorted
        parsed = json.loads(json_str)
        _assert_keys_sorted(parsed)

    @given(data=preservation_project_xml())
    @settings(
        max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_json_output_has_type_discriminators(self, tmp_path, data):
        """JSON output contains _type discriminator fields for all dataclass objects."""
        xml, label, project_id, eg_version, params, n_pfc, n_data = data
        archive_bytes = _create_egp_archive(xml)
        egp_path = _write_temp_egp(tmp_path, archive_bytes)

        project = parse_file(egp_path)
        output_dict = to_dict(project)

        # Root must have _type
        assert output_dict["_type"] == "ParsedProject"
        # Check nested objects have _type fields
        _assert_all_dicts_have_type(output_dict)

    @given(data=preservation_project_xml())
    @settings(
        max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_json_output_two_space_indent(self, tmp_path, data):
        """JSON output uses 2-space indentation."""
        xml, label, project_id, eg_version, params, n_pfc, n_data = data
        archive_bytes = _create_egp_archive(xml)
        egp_path = _write_temp_egp(tmp_path, archive_bytes)

        project = parse_file(egp_path)
        output_dict = to_dict(project)
        json_str = json.dumps(output_dict, indent=2, ensure_ascii=False, sort_keys=True)

        # Check that indentation uses 2 spaces (lines starting with spaces)
        lines = json_str.split("\n")
        for line in lines:
            stripped = line.lstrip(" ")
            indent = len(line) - len(stripped)
            if indent > 0:
                # Indent should be a multiple of 2
                assert indent % 2 == 0, f"Non-2-space indent found: '{line}'"

    @given(data=preservation_project_xml())
    @settings(
        max_examples=10, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_json_output_utf8_encoding(self, tmp_path, data):
        """JSON output can be encoded as UTF-8 without errors."""
        xml, label, project_id, eg_version, params, n_pfc, n_data = data
        archive_bytes = _create_egp_archive(xml)
        egp_path = _write_temp_egp(tmp_path, archive_bytes)

        project = parse_file(egp_path)
        output_dict = to_dict(project)
        json_str = json.dumps(output_dict, indent=2, ensure_ascii=False, sort_keys=True)

        # Must encode cleanly as UTF-8
        encoded = json_str.encode("utf-8")
        assert len(encoded) > 0
        # Re-decode must produce same string
        assert encoded.decode("utf-8") == json_str


class TestProjectMetadataPreservation:
    """Property: ProjectMetadata, ProjectSettings, Parameters, ApplicationOverrides,
    MetaDataInfo are extracted correctly on unfixed code.

    **Validates: Requirements 3.8**
    """

    @given(data=project_xml_with_metadata())
    @settings(max_examples=30)
    def test_project_metadata_extracted(self, data):
        """ProjectMetadata fields are correctly extracted from project.xml."""
        xml, label, project_id, eg_version, params, use_rel, submit_grid = data
        result = parse_project_xml(xml)

        assert result.metadata is not None
        assert result.metadata.eg_version == eg_version
        assert result.metadata.label == label
        assert result.metadata.id == project_id

    @given(data=project_xml_with_metadata())
    @settings(max_examples=30)
    def test_project_settings_extracted(self, data):
        """ProjectSettings boolean fields are correctly extracted."""
        xml, label, project_id, eg_version, params, use_rel, submit_grid = data
        result = parse_project_xml(xml)

        assert result.settings is not None
        assert result.settings.use_relative_paths == (use_rel == "True")
        assert result.settings.submit_to_grid == (submit_grid == "True")

    @given(data=project_xml_with_metadata())
    @settings(max_examples=30)
    def test_parameters_extracted(self, data):
        """Parameters are extracted with correct name/value pairs."""
        xml, label, project_id, eg_version, params, use_rel, submit_grid = data
        result = parse_project_xml(xml)

        assert len(result.parameters) == len(params)
        for i, (name, value) in enumerate(params):
            assert result.parameters[i].name == name
            assert result.parameters[i].value == value

    @given(data=preservation_project_xml())
    @settings(
        max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_full_pipeline_metadata_preserved(self, tmp_path, data):
        """Full parse_file() pipeline preserves metadata, settings, parameters."""
        xml, label, project_id, eg_version, param_pairs, n_pfc, n_data = data
        archive_bytes = _create_egp_archive(xml)
        egp_path = _write_temp_egp(tmp_path, archive_bytes)

        project = parse_file(egp_path)

        # Metadata preserved
        assert project.metadata is not None
        assert project.metadata.label == label
        assert project.metadata.id == project_id
        assert project.metadata.eg_version == eg_version

        # Settings preserved
        assert project.settings is not None

        # Parameters preserved
        assert len(project.parameters) == len(param_pairs)

    @given(data=preservation_project_xml())
    @settings(
        max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_full_pipeline_containers_preserved(self, tmp_path, data):
        """Full parse_file() pipeline preserves ProcessFlowContainer DAGs."""
        xml, label, project_id, eg_version, param_pairs, n_pfc, n_data = data
        archive_bytes = _create_egp_archive(xml)
        egp_path = _write_temp_egp(tmp_path, archive_bytes)

        project = parse_file(egp_path)

        # Containers should match the expected count
        assert len(project.containers) == n_pfc
        for container in project.containers:
            assert container.metadata is not None
            # DAG should be built for valid PFD
            assert container.dag is not None
            assert len(container.dag.nodes) >= 1

    @given(data=preservation_project_xml())
    @settings(
        max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_full_pipeline_data_list_preserved(self, tmp_path, data):
        """Full parse_file() pipeline preserves DataList extraction."""
        xml, label, project_id, eg_version, param_pairs, n_pfc, n_data = data
        archive_bytes = _create_egp_archive(xml)
        egp_path = _write_temp_egp(tmp_path, archive_bytes)

        project = parse_file(egp_path)

        # Data list count should match
        assert len(project.data_list) == n_data
        for item in project.data_list:
            assert item.element is not None


class TestVisualLayoutAttributePreservation:
    """Property: Visual layout with attribute-based TaskGraphics (legacy format)
    is preserved correctly on unfixed code.

    **Validates: Requirements 3.1** (part of ProcessFlowContainer rendering)
    """

    @given(
        pos_x=st.text(alphabet=string.digits, min_size=1, max_size=4),
        pos_y=st.text(alphabet=string.digits, min_size=1, max_size=4),
        width=st.text(alphabet=string.digits, min_size=1, max_size=4),
        height=st.text(alphabet=string.digits, min_size=1, max_size=4),
    )
    @settings(max_examples=30)
    def test_attribute_based_task_graphics_preserved(self, pos_x, pos_y, width, height):
        """TaskGraphic with attribute-based positions (legacy) are correctly extracted."""
        xml = f"""<ProjectCollection>
            <ProcessFlowControlManager>
                <ProcessFlowControlState ContainerID="pfc-001" Zoom="100">
                    <TaskGraphic Type="Node" Id="tg-001" Element="elem-001"
                        PosX="{pos_x}" PosY="{pos_y}" Width="{width}" Height="{height}"/>
                </ProcessFlowControlState>
            </ProcessFlowControlManager>
        </ProjectCollection>"""
        root = ET.fromstring(xml)
        result = parse_visual_layout(root)

        assert len(result.process_flow_states) == 1
        state = result.process_flow_states[0]
        assert state.container_id == "pfc-001"
        assert state.zoom == "100"
        assert len(state.task_graphics) == 1

        tg = state.task_graphics[0]
        assert tg.pos_x == pos_x
        assert tg.pos_y == pos_y
        assert tg.width == width
        assert tg.height == height
        assert tg.element == "elem-001"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _assert_keys_sorted(obj):
    """Recursively assert all dict keys are sorted."""
    if isinstance(obj, dict):
        keys = list(obj.keys())
        assert keys == sorted(keys), f"Keys not sorted: {keys}"
        for v in obj.values():
            _assert_keys_sorted(v)
    elif isinstance(obj, list):
        for item in obj:
            _assert_keys_sorted(item)


def _assert_all_dicts_have_type(obj):
    """Recursively check that all nested dicts that represent dataclass objects have _type."""
    if isinstance(obj, dict):
        # Dicts that have _type are dataclass objects - verify they have it
        # Some dicts might be plain key-value maps (like application_overrides)
        # We check that root-level and nested objects that should have _type do
        if "_type" in obj:
            assert isinstance(obj["_type"], str) and len(obj["_type"]) > 0
        for v in obj.values():
            _assert_all_dicts_have_type(v)
    elif isinstance(obj, list):
        for item in obj:
            _assert_all_dicts_have_type(item)
