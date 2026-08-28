"""Tests for the Process Flow Definition (PFD) parser."""

import xml.etree.ElementTree as ET

import pytest

from pyegp_parser.models.process_flow import Connection, DAGModel
from pyegp_parser.parsers.pfd_parser import parse_process_flow


class TestPFDSectionMissing:
    """Requirement 6.2: ValueError if PFD section is missing."""

    def test_raises_value_error_when_pfd_missing(self):
        xml_str = '<Element Type="SAS.EG.ProjectElements.ProcessFlowContainer" Label="PF" ID="pf-001" />'
        elem = ET.fromstring(xml_str)
        with pytest.raises(ValueError, match="missing its process flow definition"):
            parse_process_flow(elem)

    def test_error_includes_element_id(self):
        xml_str = '<Element Type="SAS.EG.ProjectElements.ProcessFlowContainer" Label="PF" ID="pf-999" />'
        elem = ET.fromstring(xml_str)
        with pytest.raises(ValueError, match="pf-999"):
            parse_process_flow(elem)


class TestEmptyPFD:
    """Empty PFD section returns empty DAGModel."""

    def test_empty_pfd_returns_empty_dag(self):
        xml_str = """
        <Element Type="SAS.EG.ProjectElements.ProcessFlowContainer" Label="PF" ID="pf-001">
            <PFD />
        </Element>
        """
        elem = ET.fromstring(xml_str)
        result = parse_process_flow(elem)
        assert isinstance(result, DAGModel)
        assert result.nodes == []
        assert result.connections == []
        assert result.warnings == []


class TestSingleNodeNoDependencies:
    """Single process entry with no dependencies."""

    def test_single_node_extracted(self):
        xml_str = """
        <Element Type="SAS.EG.ProjectElements.ProcessFlowContainer" Label="PF" ID="pf-001">
            <PFD>
                <Process>
                    <Element ID="task-A" />
                    <Dependencies />
                </Process>
            </PFD>
        </Element>
        """
        elem = ET.fromstring(xml_str)
        result = parse_process_flow(elem)
        assert result.nodes == ["task-A"]
        assert result.connections == []
        assert result.warnings == []


class TestLinearDependencies:
    """Requirement 6.3, 6.4, 6.5: Linear chain A -> B -> C."""

    def setup_method(self):
        xml_str = """
        <Element Type="SAS.EG.ProjectElements.ProcessFlowContainer" Label="PF" ID="pf-001">
            <PFD>
                <Process>
                    <Element ID="task-A" />
                    <Dependencies />
                </Process>
                <Process>
                    <Element ID="task-B" />
                    <Dependencies>
                        <DepID ResourceDependency="False">task-A</DepID>
                    </Dependencies>
                </Process>
                <Process>
                    <Element ID="task-C" />
                    <Dependencies>
                        <DepID>task-B</DepID>
                    </Dependencies>
                </Process>
            </PFD>
        </Element>
        """
        elem = ET.fromstring(xml_str)
        self.result = parse_process_flow(elem)

    def test_all_nodes_present(self):
        assert set(self.result.nodes) == {"task-A", "task-B", "task-C"}

    def test_topological_order_respected(self):
        nodes = self.result.nodes
        assert nodes.index("task-A") < nodes.index("task-B")
        assert nodes.index("task-B") < nodes.index("task-C")

    def test_connections_count(self):
        assert len(self.result.connections) == 2

    def test_connection_a_to_b(self):
        conn = Connection(
            source_id="task-A", target_id="task-B", resource_dependency=False
        )
        assert conn in self.result.connections

    def test_connection_b_to_c(self):
        conn = Connection(
            source_id="task-B", target_id="task-C", resource_dependency=False
        )
        assert conn in self.result.connections

    def test_no_warnings(self):
        assert self.result.warnings == []


class TestResourceDependencyFlag:
    """Requirement 6.4: ResourceDependency flag extraction."""

    def test_resource_dependency_true(self):
        xml_str = """
        <Element Type="SAS.EG.ProjectElements.ProcessFlowContainer" Label="PF" ID="pf-001">
            <PFD>
                <Process>
                    <Element ID="task-A" />
                    <Dependencies />
                </Process>
                <Process>
                    <Element ID="task-B" />
                    <Dependencies>
                        <DepID ResourceDependency="True">task-A</DepID>
                    </Dependencies>
                </Process>
            </PFD>
        </Element>
        """
        elem = ET.fromstring(xml_str)
        result = parse_process_flow(elem)
        assert len(result.connections) == 1
        assert result.connections[0].resource_dependency is True

    def test_resource_dependency_default_false(self):
        xml_str = """
        <Element Type="SAS.EG.ProjectElements.ProcessFlowContainer" Label="PF" ID="pf-001">
            <PFD>
                <Process>
                    <Element ID="task-A" />
                    <Dependencies />
                </Process>
                <Process>
                    <Element ID="task-B" />
                    <Dependencies>
                        <DepID>task-A</DepID>
                    </Dependencies>
                </Process>
            </PFD>
        </Element>
        """
        elem = ET.fromstring(xml_str)
        result = parse_process_flow(elem)
        assert len(result.connections) == 1
        assert result.connections[0].resource_dependency is False

    def test_mixed_dependencies(self):
        xml_str = """
        <Element Type="SAS.EG.ProjectElements.ProcessFlowContainer" Label="PF" ID="pf-001">
            <PFD>
                <Process>
                    <Element ID="task-A" />
                    <Dependencies />
                </Process>
                <Process>
                    <Element ID="task-B" />
                    <Dependencies />
                </Process>
                <Process>
                    <Element ID="task-C" />
                    <Dependencies>
                        <DepID ResourceDependency="True">task-A</DepID>
                        <DepID ResourceDependency="False">task-B</DepID>
                    </Dependencies>
                </Process>
            </PFD>
        </Element>
        """
        elem = ET.fromstring(xml_str)
        result = parse_process_flow(elem)
        assert len(result.connections) == 2
        resource_conns = [c for c in result.connections if c.resource_dependency]
        exec_conns = [c for c in result.connections if not c.resource_dependency]
        assert len(resource_conns) == 1
        assert resource_conns[0].source_id == "task-A"
        assert len(exec_conns) == 1
        assert exec_conns[0].source_id == "task-B"


class TestDanglingDepIDReferences:
    """Requirement 6.8: Warn and skip dangling DepID references."""

    def test_dangling_reference_skipped_with_warning(self):
        xml_str = """
        <Element Type="SAS.EG.ProjectElements.ProcessFlowContainer" Label="PF" ID="pf-001">
            <PFD>
                <Process>
                    <Element ID="task-A" />
                    <Dependencies>
                        <DepID>nonexistent-id</DepID>
                    </Dependencies>
                </Process>
            </PFD>
        </Element>
        """
        elem = ET.fromstring(xml_str)
        result = parse_process_flow(elem)
        assert result.nodes == ["task-A"]
        assert result.connections == []
        assert len(result.warnings) == 1
        assert "nonexistent-id" in result.warnings[0]
        assert "task-A" in result.warnings[0]

    def test_multiple_dangling_references(self):
        xml_str = """
        <Element Type="SAS.EG.ProjectElements.ProcessFlowContainer" Label="PF" ID="pf-001">
            <PFD>
                <Process>
                    <Element ID="task-A" />
                    <Dependencies>
                        <DepID>ghost-1</DepID>
                        <DepID>ghost-2</DepID>
                    </Dependencies>
                </Process>
            </PFD>
        </Element>
        """
        elem = ET.fromstring(xml_str)
        result = parse_process_flow(elem)
        assert len(result.warnings) == 2
        assert "ghost-1" in result.warnings[0]
        assert "ghost-2" in result.warnings[1]

    def test_mix_of_valid_and_dangling(self):
        xml_str = """
        <Element Type="SAS.EG.ProjectElements.ProcessFlowContainer" Label="PF" ID="pf-001">
            <PFD>
                <Process>
                    <Element ID="task-A" />
                    <Dependencies />
                </Process>
                <Process>
                    <Element ID="task-B" />
                    <Dependencies>
                        <DepID>task-A</DepID>
                        <DepID>nonexistent</DepID>
                    </Dependencies>
                </Process>
            </PFD>
        </Element>
        """
        elem = ET.fromstring(xml_str)
        result = parse_process_flow(elem)
        assert len(result.connections) == 1
        assert result.connections[0].source_id == "task-A"
        assert result.connections[0].target_id == "task-B"
        assert len(result.warnings) == 1
        assert "nonexistent" in result.warnings[0]


class TestCycleDetection:
    """Requirement 6.7: Raise ValueError if cycle detected."""

    def test_simple_cycle_raises_value_error(self):
        xml_str = """
        <Element Type="SAS.EG.ProjectElements.ProcessFlowContainer" Label="PF" ID="pf-001">
            <PFD>
                <Process>
                    <Element ID="task-A" />
                    <Dependencies>
                        <DepID>task-B</DepID>
                    </Dependencies>
                </Process>
                <Process>
                    <Element ID="task-B" />
                    <Dependencies>
                        <DepID>task-A</DepID>
                    </Dependencies>
                </Process>
            </PFD>
        </Element>
        """
        elem = ET.fromstring(xml_str)
        with pytest.raises(ValueError, match="circular dependency"):
            parse_process_flow(elem)

    def test_three_node_cycle_raises_value_error(self):
        xml_str = """
        <Element Type="SAS.EG.ProjectElements.ProcessFlowContainer" Label="PF" ID="pf-001">
            <PFD>
                <Process>
                    <Element ID="task-A" />
                    <Dependencies>
                        <DepID>task-C</DepID>
                    </Dependencies>
                </Process>
                <Process>
                    <Element ID="task-B" />
                    <Dependencies>
                        <DepID>task-A</DepID>
                    </Dependencies>
                </Process>
                <Process>
                    <Element ID="task-C" />
                    <Dependencies>
                        <DepID>task-B</DepID>
                    </Dependencies>
                </Process>
            </PFD>
        </Element>
        """
        elem = ET.fromstring(xml_str)
        with pytest.raises(ValueError, match="circular dependency"):
            parse_process_flow(elem)


class TestDiamondDAG:
    """Diamond pattern: A -> B, A -> C, B -> D, C -> D."""

    def setup_method(self):
        xml_str = """
        <Element Type="SAS.EG.ProjectElements.ProcessFlowContainer" Label="PF" ID="pf-001">
            <PFD>
                <Process>
                    <Element ID="A" />
                    <Dependencies />
                </Process>
                <Process>
                    <Element ID="B" />
                    <Dependencies>
                        <DepID>A</DepID>
                    </Dependencies>
                </Process>
                <Process>
                    <Element ID="C" />
                    <Dependencies>
                        <DepID>A</DepID>
                    </Dependencies>
                </Process>
                <Process>
                    <Element ID="D" />
                    <Dependencies>
                        <DepID>B</DepID>
                        <DepID>C</DepID>
                    </Dependencies>
                </Process>
            </PFD>
        </Element>
        """
        elem = ET.fromstring(xml_str)
        self.result = parse_process_flow(elem)

    def test_all_nodes_present(self):
        assert set(self.result.nodes) == {"A", "B", "C", "D"}

    def test_a_before_b_and_c(self):
        nodes = self.result.nodes
        assert nodes.index("A") < nodes.index("B")
        assert nodes.index("A") < nodes.index("C")

    def test_b_and_c_before_d(self):
        nodes = self.result.nodes
        assert nodes.index("B") < nodes.index("D")
        assert nodes.index("C") < nodes.index("D")

    def test_four_connections(self):
        assert len(self.result.connections) == 4


class TestExampleFromSpec:
    """Integration test with the exact XML structure from the task spec."""

    def setup_method(self):
        xml_str = """
        <Element Type="SAS.EG.ProjectElements.ProcessFlowContainer" Label="Process Flow" ID="pf-001">
            <PFD>
                <Process>
                    <Element ID="task-A" />
                    <Dependencies />
                </Process>
                <Process>
                    <Element ID="task-B" />
                    <Dependencies>
                        <DepID ResourceDependency="False">task-A</DepID>
                    </Dependencies>
                </Process>
                <Process>
                    <Element ID="task-C" />
                    <Dependencies>
                        <DepID ResourceDependency="True">task-A</DepID>
                        <DepID>task-B</DepID>
                    </Dependencies>
                </Process>
            </PFD>
        </Element>
        """
        elem = ET.fromstring(xml_str)
        self.result = parse_process_flow(elem)

    def test_three_nodes(self):
        assert len(self.result.nodes) == 3
        assert set(self.result.nodes) == {"task-A", "task-B", "task-C"}

    def test_topological_order(self):
        nodes = self.result.nodes
        assert nodes.index("task-A") < nodes.index("task-B")
        assert nodes.index("task-A") < nodes.index("task-C")
        assert nodes.index("task-B") < nodes.index("task-C")

    def test_three_connections(self):
        assert len(self.result.connections) == 3

    def test_resource_dependency_from_a_to_c(self):
        resource_conns = [
            c
            for c in self.result.connections
            if c.resource_dependency
            and c.source_id == "task-A"
            and c.target_id == "task-C"
        ]
        assert len(resource_conns) == 1

    def test_execution_dependency_from_a_to_b(self):
        exec_conns = [
            c
            for c in self.result.connections
            if not c.resource_dependency
            and c.source_id == "task-A"
            and c.target_id == "task-B"
        ]
        assert len(exec_conns) == 1

    def test_execution_dependency_from_b_to_c(self):
        exec_conns = [
            c
            for c in self.result.connections
            if not c.resource_dependency
            and c.source_id == "task-B"
            and c.target_id == "task-C"
        ]
        assert len(exec_conns) == 1

    def test_no_warnings(self):
        assert self.result.warnings == []


class TestEdgeCases:
    """Edge cases for robustness."""

    def test_process_without_element_child_skipped(self):
        """Process entries without an Element child are silently skipped."""
        xml_str = """
        <Element Type="SAS.EG.ProjectElements.ProcessFlowContainer" Label="PF" ID="pf-001">
            <PFD>
                <Process>
                    <Dependencies />
                </Process>
                <Process>
                    <Element ID="task-A" />
                    <Dependencies />
                </Process>
            </PFD>
        </Element>
        """
        elem = ET.fromstring(xml_str)
        result = parse_process_flow(elem)
        assert result.nodes == ["task-A"]

    def test_process_without_dependencies_child(self):
        """Process entries without a Dependencies child still have their node added."""
        xml_str = """
        <Element Type="SAS.EG.ProjectElements.ProcessFlowContainer" Label="PF" ID="pf-001">
            <PFD>
                <Process>
                    <Element ID="task-A" />
                </Process>
            </PFD>
        </Element>
        """
        elem = ET.fromstring(xml_str)
        result = parse_process_flow(elem)
        assert result.nodes == ["task-A"]
        assert result.connections == []

    def test_empty_dep_id_text_ignored(self):
        """DepID elements with empty or whitespace text are ignored."""
        xml_str = """
        <Element Type="SAS.EG.ProjectElements.ProcessFlowContainer" Label="PF" ID="pf-001">
            <PFD>
                <Process>
                    <Element ID="task-A" />
                    <Dependencies>
                        <DepID>   </DepID>
                        <DepID />
                    </Dependencies>
                </Process>
            </PFD>
        </Element>
        """
        elem = ET.fromstring(xml_str)
        result = parse_process_flow(elem)
        assert result.nodes == ["task-A"]
        assert result.connections == []
        assert result.warnings == []

    def test_element_without_id_attribute_skipped(self):
        """Element nodes without an ID attribute are skipped."""
        xml_str = """
        <Element Type="SAS.EG.ProjectElements.ProcessFlowContainer" Label="PF" ID="pf-001">
            <PFD>
                <Process>
                    <Element />
                </Process>
                <Process>
                    <Element ID="task-A" />
                    <Dependencies />
                </Process>
            </PFD>
        </Element>
        """
        elem = ET.fromstring(xml_str)
        result = parse_process_flow(elem)
        assert result.nodes == ["task-A"]
