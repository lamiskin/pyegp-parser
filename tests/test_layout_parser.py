"""Tests for the visual layout parser.

Validates Requirements 14.1 through 14.7.
"""

import xml.etree.ElementTree as ET

from pyegp_parser.models.visual_layout import (
    VisualLayout,
)
from pyegp_parser.parsers.layout_parser import (
    parse_open_project_view,
    parse_visual_layout,
)


class TestParseVisualLayout:
    """Tests for parse_visual_layout function."""

    def test_extracts_process_flow_control_states(self):
        """Requirement 14.1: Extract all ProcessFlowControlState entries."""
        xml = """
        <ProjectCollection>
            <ProcessFlowControlManager>
                <ProcessFlowControlState ContainerID="pfc-001" Zoom="100"
                    ShowGrid="True" ShowMargins="False" Align="None" />
                <ProcessFlowControlState ContainerID="pfc-002" Zoom="75"
                    ShowGrid="False" ShowMargins="True" Align="Center" />
            </ProcessFlowControlManager>
        </ProjectCollection>
        """
        root = ET.fromstring(xml)
        result = parse_visual_layout(root)

        assert isinstance(result, VisualLayout)
        assert len(result.process_flow_states) == 2
        assert result.process_flow_states[0].container_id == "pfc-001"
        assert result.process_flow_states[1].container_id == "pfc-002"

    def test_empty_collection_when_manager_absent(self):
        """Requirement 14.2: Empty collection if ProcessFlowControlManager absent."""
        xml = """
        <ProjectCollection>
            <SomeOtherSection />
        </ProjectCollection>
        """
        root = ET.fromstring(xml)
        result = parse_visual_layout(root)

        assert isinstance(result, VisualLayout)
        assert result.process_flow_states == []
        assert result.warnings == []

    def test_extracts_container_settings(self):
        """Requirement 14.3: Extract ContainerID, Zoom, ShowGrid, ShowMargins, Align."""
        xml = """
        <ProjectCollection>
            <ProcessFlowControlManager>
                <ProcessFlowControlState ContainerID="container-abc"
                    Zoom="150" ShowGrid="True" ShowMargins="True" Align="SnapToGrid" />
            </ProcessFlowControlManager>
        </ProjectCollection>
        """
        root = ET.fromstring(xml)
        result = parse_visual_layout(root)

        state = result.process_flow_states[0]
        assert state.container_id == "container-abc"
        assert state.zoom == "150"
        assert state.show_grid == "True"
        assert state.show_margins == "True"
        assert state.align == "SnapToGrid"

    def test_extracts_task_graphic_entries(self):
        """Requirement 14.4: Extract all TaskGraphic entries with all attributes."""
        xml = """
        <ProjectCollection>
            <ProcessFlowControlManager>
                <ProcessFlowControlState ContainerID="pfc-001" Zoom="100"
                    ShowGrid="True" ShowMargins="False" Align="None">
                    <TaskGraphic Type="Node" Id="tg-001" LineWidth="1"
                        Fill="#FFFFFF" PosX="100" PosY="200" Width="120"
                        Height="60" Rotation="0" Visible="True" Border="#000000"
                        AutoSize="False" Removable="True" Child="child-001"
                        Selected="False" Label="My Task" Element="elem-001" />
                    <TaskGraphic Type="Connector" Id="tg-002" LineWidth="2"
                        Fill="transparent" PosX="220" PosY="230" Width="50"
                        Height="1" Element="elem-002" />
                </ProcessFlowControlState>
            </ProcessFlowControlManager>
        </ProjectCollection>
        """
        root = ET.fromstring(xml)
        result = parse_visual_layout(root, element_ids={"elem-001", "elem-002"})

        state = result.process_flow_states[0]
        assert len(state.task_graphics) == 2

        tg1 = state.task_graphics[0]
        assert tg1.type == "Node"
        assert tg1.id == "tg-001"
        assert tg1.line_width == "1"
        assert tg1.fill == "#FFFFFF"
        assert tg1.pos_x == "100"
        assert tg1.pos_y == "200"
        assert tg1.width == "120"
        assert tg1.height == "60"
        assert tg1.rotation == "0"
        assert tg1.visible == "True"
        assert tg1.border == "#000000"
        assert tg1.auto_size == "False"
        assert tg1.removable == "True"
        assert tg1.child == "child-001"
        assert tg1.selected == "False"
        assert tg1.label == "My Task"
        assert tg1.element == "elem-001"

        tg2 = state.task_graphics[1]
        assert tg2.type == "Connector"
        assert tg2.id == "tg-002"
        assert tg2.line_width == "2"
        assert tg2.fill == "transparent"
        assert tg2.pos_x == "220"
        assert tg2.pos_y == "230"
        assert tg2.width == "50"
        assert tg2.height == "1"
        assert tg2.element == "elem-002"

    def test_task_graphic_association_with_parent_state(self):
        """Requirement 14.4: TaskGraphics associated with correct parent state."""
        xml = """
        <ProjectCollection>
            <ProcessFlowControlManager>
                <ProcessFlowControlState ContainerID="pfc-A">
                    <TaskGraphic Id="tg-A1" Element="e1" />
                    <TaskGraphic Id="tg-A2" Element="e2" />
                </ProcessFlowControlState>
                <ProcessFlowControlState ContainerID="pfc-B">
                    <TaskGraphic Id="tg-B1" Element="e3" />
                </ProcessFlowControlState>
            </ProcessFlowControlManager>
        </ProjectCollection>
        """
        root = ET.fromstring(xml)
        result = parse_visual_layout(root, element_ids={"e1", "e2", "e3"})

        assert len(result.process_flow_states) == 2
        assert len(result.process_flow_states[0].task_graphics) == 2
        assert result.process_flow_states[0].task_graphics[0].id == "tg-A1"
        assert result.process_flow_states[0].task_graphics[1].id == "tg-A2"
        assert len(result.process_flow_states[1].task_graphics) == 1
        assert result.process_flow_states[1].task_graphics[0].id == "tg-B1"

    def test_warns_for_unresolved_element_reference(self):
        """Requirement 14.5: Warn for unresolved TaskGraphic Element references."""
        xml = """
        <ProjectCollection>
            <ProcessFlowControlManager>
                <ProcessFlowControlState ContainerID="pfc-001">
                    <TaskGraphic Id="tg-001" Element="unknown-ref" />
                    <TaskGraphic Id="tg-002" Element="known-ref" />
                </ProcessFlowControlState>
            </ProcessFlowControlManager>
        </ProjectCollection>
        """
        root = ET.fromstring(xml)
        result = parse_visual_layout(root, element_ids={"known-ref"})

        # The unresolved reference should be preserved as-is
        assert result.process_flow_states[0].task_graphics[0].element == "unknown-ref"
        # A warning should be generated
        assert len(result.warnings) == 1
        assert "unknown-ref" in result.warnings[0]

    def test_no_warning_when_element_ids_not_provided(self):
        """No warning when element_ids is None (validation skipped)."""
        xml = """
        <ProjectCollection>
            <ProcessFlowControlManager>
                <ProcessFlowControlState ContainerID="pfc-001">
                    <TaskGraphic Id="tg-001" Element="any-ref" />
                </ProcessFlowControlState>
            </ProcessFlowControlManager>
        </ProjectCollection>
        """
        root = ET.fromstring(xml)
        result = parse_visual_layout(root, element_ids=None)

        assert result.warnings == []
        assert result.process_flow_states[0].task_graphics[0].element == "any-ref"

    def test_no_warning_when_element_has_no_reference(self):
        """No warning when TaskGraphic has no Element attribute."""
        xml = """
        <ProjectCollection>
            <ProcessFlowControlManager>
                <ProcessFlowControlState ContainerID="pfc-001">
                    <TaskGraphic Id="tg-001" />
                </ProcessFlowControlState>
            </ProcessFlowControlManager>
        </ProjectCollection>
        """
        root = ET.fromstring(xml)
        result = parse_visual_layout(root, element_ids=set())

        assert result.warnings == []
        assert result.process_flow_states[0].task_graphics[0].element is None

    def test_state_with_missing_attributes_returns_none(self):
        """Missing optional attributes default to None."""
        xml = """
        <ProjectCollection>
            <ProcessFlowControlManager>
                <ProcessFlowControlState ContainerID="pfc-minimal" />
            </ProcessFlowControlManager>
        </ProjectCollection>
        """
        root = ET.fromstring(xml)
        result = parse_visual_layout(root)

        state = result.process_flow_states[0]
        assert state.container_id == "pfc-minimal"
        assert state.zoom is None
        assert state.show_grid is None
        assert state.show_margins is None
        assert state.align is None
        assert state.task_graphics == []

    def test_task_graphic_with_partial_attributes(self):
        """TaskGraphic with only some attributes; missing ones are None."""
        xml = """
        <ProjectCollection>
            <ProcessFlowControlManager>
                <ProcessFlowControlState ContainerID="pfc-001">
                    <TaskGraphic Type="Node" Id="tg-partial" PosX="50" PosY="75" />
                </ProcessFlowControlState>
            </ProcessFlowControlManager>
        </ProjectCollection>
        """
        root = ET.fromstring(xml)
        result = parse_visual_layout(root)

        tg = result.process_flow_states[0].task_graphics[0]
        assert tg.type == "Node"
        assert tg.id == "tg-partial"
        assert tg.pos_x == "50"
        assert tg.pos_y == "75"
        assert tg.line_width is None
        assert tg.fill is None
        assert tg.width is None
        assert tg.height is None
        assert tg.rotation is None
        assert tg.visible is None
        assert tg.border is None
        assert tg.auto_size is None
        assert tg.removable is None
        assert tg.child is None
        assert tg.selected is None
        assert tg.label is None
        assert tg.element is None

    def test_multiple_unresolved_references_multiple_warnings(self):
        """Multiple unresolved references generate multiple warnings."""
        xml = """
        <ProjectCollection>
            <ProcessFlowControlManager>
                <ProcessFlowControlState ContainerID="pfc-001">
                    <TaskGraphic Id="tg-001" Element="bad-ref-1" />
                    <TaskGraphic Id="tg-002" Element="bad-ref-2" />
                    <TaskGraphic Id="tg-003" Element="good-ref" />
                </ProcessFlowControlState>
            </ProcessFlowControlManager>
        </ProjectCollection>
        """
        root = ET.fromstring(xml)
        result = parse_visual_layout(root, element_ids={"good-ref"})

        assert len(result.warnings) == 2
        assert "bad-ref-1" in result.warnings[0]
        assert "bad-ref-2" in result.warnings[1]


class TestParseOpenProjectView:
    """Tests for parse_open_project_view function."""

    def test_extracts_tree_items(self):
        """Requirement 14.6: Extract TreeItem entries with ID and IsExpanded."""
        xml = """
        <ProjectCollection>
            <OpenProjectView>
                <TreeItem ID="item-001" IsExpanded="True" />
                <TreeItem ID="item-002" IsExpanded="False" />
                <TreeItem ID="item-003" IsExpanded="True" />
            </OpenProjectView>
        </ProjectCollection>
        """
        root = ET.fromstring(xml)
        result = parse_open_project_view(root)

        assert len(result) == 3
        assert result[0].id == "item-001"
        assert result[0].is_expanded is True
        assert result[1].id == "item-002"
        assert result[1].is_expanded is False
        assert result[2].id == "item-003"
        assert result[2].is_expanded is True

    def test_empty_list_when_section_absent(self):
        """Requirement 14.7: Empty collection if OpenProjectView absent."""
        xml = """
        <ProjectCollection>
            <SomeOtherSection />
        </ProjectCollection>
        """
        root = ET.fromstring(xml)
        result = parse_open_project_view(root)

        assert result == []

    def test_tree_item_without_is_expanded(self):
        """TreeItem with missing IsExpanded attribute returns None for that field."""
        xml = """
        <ProjectCollection>
            <OpenProjectView>
                <TreeItem ID="item-only-id" />
            </OpenProjectView>
        </ProjectCollection>
        """
        root = ET.fromstring(xml)
        result = parse_open_project_view(root)

        assert len(result) == 1
        assert result[0].id == "item-only-id"
        assert result[0].is_expanded is None

    def test_tree_item_without_id(self):
        """TreeItem with missing ID attribute returns None for id."""
        xml = """
        <ProjectCollection>
            <OpenProjectView>
                <TreeItem IsExpanded="False" />
            </OpenProjectView>
        </ProjectCollection>
        """
        root = ET.fromstring(xml)
        result = parse_open_project_view(root)

        assert len(result) == 1
        assert result[0].id is None
        assert result[0].is_expanded is False

    def test_empty_open_project_view(self):
        """OpenProjectView present but with no TreeItem children."""
        xml = """
        <ProjectCollection>
            <OpenProjectView />
        </ProjectCollection>
        """
        root = ET.fromstring(xml)
        result = parse_open_project_view(root)

        assert result == []

    def test_is_expanded_case_insensitive(self):
        """IsExpanded parsing handles various case variations."""
        xml = """
        <ProjectCollection>
            <OpenProjectView>
                <TreeItem ID="item-1" IsExpanded="true" />
                <TreeItem ID="item-2" IsExpanded="True" />
                <TreeItem ID="item-3" IsExpanded="FALSE" />
                <TreeItem ID="item-4" IsExpanded="false" />
            </OpenProjectView>
        </ProjectCollection>
        """
        root = ET.fromstring(xml)
        result = parse_open_project_view(root)

        assert result[0].is_expanded is True
        assert result[1].is_expanded is True
        assert result[2].is_expanded is False
        assert result[3].is_expanded is False
