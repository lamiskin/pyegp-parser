"""Bug condition exploration property tests for full-content-extraction bugfix.

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8**

These tests encode the EXPECTED BEHAVIOR. They are designed to FAIL on unfixed code,
confirming the bug exists. After the fix is implemented, they should PASS.

The bug condition: parse_file() discards typed content, ignores External_Objects,
uses attribute-access for child-text layout fields, and silently swallows errors.
"""

import json
import xml.etree.ElementTree as ET
from io import BytesIO
from zipfile import ZipFile

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from pyegp_parser import parse_file
from pyegp_parser.models.base import ElementMetadata
from pyegp_parser.parsers.layout_parser import parse_visual_layout
from pyegp_parser.parsers.shortcut_parser import parse_shortcut
from pyegp_parser.serializer import to_dict

# --- Helpers to create synthetic EGP archives ---


def _make_project_xml_with_query(
    query_label: str = "Test Query",
    query_id: str = "Q001",
    table_name: str = "WORK.INPUT",
) -> str:
    """Create a minimal project.xml containing a Query element with QueryModel."""
    return f"""<?xml version="1.0" encoding="utf-8"?>
<ProjectCollection EGVersion="8.1" Type="SAS.EG.ProjectElements.ProjectCollection">
    <Project>
        <Element>
            <Label>Test Project</Label>
            <ID>PROJ001</ID>
            <Type>SAS.EG.ProjectElements.Project</Type>
        </Element>
    </Project>
    <Elements>
        <Element Type="SAS.EG.ProjectElements.Query" Label="{query_label}" ID="{query_id}">
            <Element>
                <Label>{query_label}</Label>
                <ID>{query_id}</ID>
                <Type>SAS.EG.ProjectElements.Query</Type>
            </Element>
            <SubmitableElement>
                <Server>SASApp</Server>
                <UseGlobalOptions>True</UseGlobalOptions>
            </SubmitableElement>
            <QueryModel>
                <InputTables>
                    <InputTable ID="T1" InputTableName="{table_name}" />
                </InputTables>
                <ResultItems>
                    <ResultItem ResultID="R1" Alias="col1" TableID="T1" />
                </ResultItems>
                <JoinItems>
                    <JoinItem LeftTableID="T1" RightTableID="T2" JoinType="Inner" />
                </JoinItems>
            </QueryModel>
        </Element>
        <Element Type="SAS.EG.ProjectElements.ProjectLog" Label="Project Log" ID="PL001">
            <Enabled>True</Enabled>
            <WrittenTo>False</WrittenTo>
        </Element>
    </Elements>
</ProjectCollection>"""


def _make_project_xml_with_code_task(
    task_label: str = "Test Code Task",
    task_id: str = "CT001",
) -> str:
    """Create a minimal project.xml containing a CodeTask element."""
    return f"""<?xml version="1.0" encoding="utf-8"?>
<ProjectCollection EGVersion="8.1" Type="SAS.EG.ProjectElements.ProjectCollection">
    <Project>
        <Element>
            <Label>Test Project</Label>
            <ID>PROJ001</ID>
            <Type>SAS.EG.ProjectElements.Project</Type>
        </Element>
    </Project>
    <Elements>
        <Element Type="SAS.EG.ProjectElements.CodeTask" Label="{task_label}" ID="{task_id}">
            <Element>
                <Label>{task_label}</Label>
                <ID>{task_id}</ID>
                <Type>SAS.EG.ProjectElements.CodeTask</Type>
            </Element>
            <SubmitableElement>
                <Server>SASApp</Server>
                <UseGlobalOptions>True</UseGlobalOptions>
                <HASERROR>False</HASERROR>
            </SubmitableElement>
        </Element>
        <Element Type="SAS.EG.ProjectElements.ProjectLog" Label="Project Log" ID="PL001">
            <Enabled>True</Enabled>
            <WrittenTo>False</WrittenTo>
        </Element>
    </Elements>
</ProjectCollection>"""


def _make_project_xml_with_shortcut(
    shortcut_label: str = "Test Shortcut",
    shortcut_id: str = "SC001",
    parent_id: str = "DATA001",
) -> str:
    """Create a minimal project.xml containing a ShortCutToData element."""
    return f"""<?xml version="1.0" encoding="utf-8"?>
<ProjectCollection EGVersion="8.1" Type="SAS.EG.ProjectElements.ProjectCollection">
    <Project>
        <Element>
            <Label>Test Project</Label>
            <ID>PROJ001</ID>
            <Type>SAS.EG.ProjectElements.Project</Type>
        </Element>
    </Project>
    <Elements>
        <Element Type="SAS.EG.ProjectElements.ShortCutToData" Label="{shortcut_label}" ID="{shortcut_id}">
            <Element>
                <Label>{shortcut_label}</Label>
                <ID>{shortcut_id}</ID>
                <Type>SAS.EG.ProjectElements.ShortCutToData</Type>
            </Element>
            <SHORTCUT>
                <Parent>{parent_id}</Parent>
                <INPUTLIST>
                    <INPUTID>INPUT001</INPUTID>
                    <INPUTID>INPUT002</INPUTID>
                </INPUTLIST>
                <UserHasExplicitlySetLabel>True</UserHasExplicitlySetLabel>
            </SHORTCUT>
        </Element>
        <Element Type="SAS.EG.ProjectElements.ProjectLog" Label="Project Log" ID="PL001">
            <Enabled>True</Enabled>
            <WrittenTo>False</WrittenTo>
        </Element>
    </Elements>
</ProjectCollection>"""


def _make_project_xml_with_external_objects() -> str:
    """Create a minimal project.xml containing an External_Objects section."""
    return """<?xml version="1.0" encoding="utf-8"?>
<ProjectCollection EGVersion="8.1" Type="SAS.EG.ProjectElements.ProjectCollection">
    <Project>
        <Element>
            <Label>Test Project</Label>
            <ID>PROJ001</ID>
            <Type>SAS.EG.ProjectElements.Project</Type>
        </Element>
    </Project>
    <Elements>
        <Element Type="SAS.EG.ProjectElements.ProjectLog" Label="Project Log" ID="PL001">
            <Enabled>True</Enabled>
            <WrittenTo>False</WrittenTo>
        </Element>
    </Elements>
    <External_Objects>
        <ExternalObject Name="ExtObj1" Type="SAS.Dataset" Path="/data/input.sas7bdat">
            <Description>External input dataset</Description>
        </ExternalObject>
        <ExternalObject Name="ExtObj2" Type="SAS.Program" Path="/code/transform.sas">
            <Description>External SAS program</Description>
        </ExternalObject>
    </External_Objects>
</ProjectCollection>"""


def _make_project_xml_with_task_graphic_child_text() -> str:
    """Create a project.xml with TaskGraphic using child text elements for positions."""
    return """<?xml version="1.0" encoding="utf-8"?>
<ProjectCollection EGVersion="8.1" Type="SAS.EG.ProjectElements.ProjectCollection">
    <Project>
        <Element>
            <Label>Test Project</Label>
            <ID>PROJ001</ID>
            <Type>SAS.EG.ProjectElements.Project</Type>
        </Element>
    </Project>
    <Elements>
        <Element Type="SAS.EG.ProjectElements.ProjectLog" Label="Project Log" ID="PL001">
            <Enabled>True</Enabled>
            <WrittenTo>False</WrittenTo>
        </Element>
    </Elements>
    <ProcessFlowControlManager>
        <ProcessFlowControlState ContainerID="pfc-001">
            <TaskGraphic Type="Node" Id="tg-001" Element="elem-001">
                <PosX>24</PosX>
                <PosY>100</PosY>
                <Width>120</Width>
                <Height>60</Height>
            </TaskGraphic>
            <TaskGraphic Type="Node" Id="tg-002" Element="elem-002">
                <PosX>200</PosX>
                <PosY>300</PosY>
                <Width>150</Width>
                <Height>80</Height>
            </TaskGraphic>
        </ProcessFlowControlState>
    </ProcessFlowControlManager>
</ProjectCollection>"""


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


# --- Bug Condition Exploration Tests ---


class TestBugConditionQueryContentNotExtracted:
    """Bug Condition: Query elements produce only ElementMetadata, QueryModel absent.

    **Validates: Requirements 1.1, 1.4**

    Expected behavior (post-fix): parse_file() on an EGP containing a Query element
    includes QueryModel fields (InputTables, ResultItems, JoinItems) in the output.
    """

    def test_query_model_included_in_output(self, tmp_path):
        """parse_file() should include QueryModel data for Query elements.

        Scoped PBT: tests multiple Query configurations to surface
        the bug condition that QueryModel content is discarded.
        """
        test_cases = [
            ("TestQuery", "Q001", "WORK.INPUT"),
            ("MyQuery", "QRY0042", "WORK.CUSTOMERS"),
            ("AggregateQ", "QAGG1", "WORK.SALES_DATA"),
        ]
        for query_label, query_id, table_name in test_cases:
            xml = _make_project_xml_with_query(query_label, query_id, table_name)
            archive_bytes = _create_egp_archive(xml)
            egp_path = _write_temp_egp(tmp_path, archive_bytes)

            project = parse_file(egp_path)
            output_dict = to_dict(project)
            output_json = json.dumps(output_dict, indent=2)

            # The serialized output should contain QueryModel typed content fields.
            # These field names only appear if the query parser was invoked and
            # its output was included in the serialized ParsedProject.
            assert "input_tables" in output_json, (
                f"QueryModel.input_tables not found in output for Query element '{query_id}'. "
                f"Bug confirmed: only ElementMetadata is serialized, typed content is discarded."
            )


class TestBugConditionCodeTaskContentNotExtracted:
    """Bug Condition: Task elements have no SubmitableElement or code content in output.

    **Validates: Requirements 1.1, 1.5**

    Expected behavior (post-fix): parse_file() on an EGP containing a CodeTask
    includes SubmitableElement and code content in the serialized output.
    """

    def test_code_task_content_included_in_output(self, tmp_path):
        """parse_file() should include SubmitableElement for CodeTask elements.

        Scoped PBT: tests multiple CodeTask configurations.
        """
        test_cases = [
            ("Proc Print Task", "CT001"),
            ("Data Transform", "CODE42"),
            ("SAS Macro", "CTASK7"),
        ]
        for task_label, task_id in test_cases:
            xml = _make_project_xml_with_code_task(task_label, task_id)
            code_content = b"proc print data=work.test; run;"
            extra_files = {f"CodeTask-{task_id}/code.sas": code_content}
            archive_bytes = _create_egp_archive(xml, extra_files)
            egp_path = _write_temp_egp(tmp_path, archive_bytes)

            project = parse_file(egp_path)
            output_dict = to_dict(project)
            output_json = json.dumps(output_dict, indent=2)

            # The output should contain SubmitableElement or CodeTaskElement typed content
            has_submitable = (
                "SubmitableElement" in output_json or "submitable" in output_json
            )
            has_code_content = (
                "code_content" in output_json or "proc print" in output_json
            )
            assert has_submitable or has_code_content, (
                f"CodeTask typed content not found in output for element '{task_id}'. "
                f"Bug confirmed: only ElementMetadata is serialized, SubmitableElement/code discarded."
            )


class TestBugConditionShortcutContentNotExtracted:
    """Bug Condition: ShortCutToData elements lack parent_id and input_list in output.

    **Validates: Requirements 1.1, 1.6**

    Expected behavior (post-fix): parse_file() on an EGP containing a ShortCutToData
    includes parent_id and input_list in the serialized output.
    """

    def test_shortcut_content_included_in_output(self, tmp_path):
        """parse_file() should include parent_id and input_list for ShortCutToData elements.

        Scoped PBT: tests multiple ShortCut configurations.
        """
        test_cases = [
            ("InputData Shortcut", "SC001", "DATA001"),
            ("Ref Shortcut", "SCREF5", "PARENT99"),
            ("Link SC", "SCLNK", "DI00042"),
        ]
        for shortcut_label, shortcut_id, parent_id in test_cases:
            xml = _make_project_xml_with_shortcut(
                shortcut_label, shortcut_id, parent_id
            )
            archive_bytes = _create_egp_archive(xml)
            egp_path = _write_temp_egp(tmp_path, archive_bytes)

            project = parse_file(egp_path)
            output_dict = to_dict(project)
            output_json = json.dumps(output_dict, indent=2)

            # The output should contain ShortCutToData typed content
            has_parent_id = "parent_id" in output_json and parent_id in output_json
            has_input_list = "input_list" in output_json or "INPUT001" in output_json
            assert has_parent_id or has_input_list, (
                f"ShortCutToData typed content not found in output for element '{shortcut_id}'. "
                f"Bug confirmed: shortcut_parser.parse_shortcut() is never called in the pipeline."
            )


class TestBugConditionExternalObjectsNotParsed:
    """Bug Condition: External_Objects section produces zero output entries.

    **Validates: Requirements 1.2**

    Expected behavior (post-fix): parse_file() on an EGP containing External_Objects
    includes parsed external object entries in the output.
    """

    def test_external_objects_included_in_output(self, tmp_path):
        """parse_file() should include External_Objects entries in output."""
        xml = _make_project_xml_with_external_objects()
        archive_bytes = _create_egp_archive(xml)
        egp_path = _write_temp_egp(tmp_path, archive_bytes)

        project = parse_file(egp_path)
        output_dict = to_dict(project)
        output_json = json.dumps(output_dict, indent=2)

        # The output should contain External_Objects/ExternalObject data
        has_external_objects = (
            "external_objects" in output_json and "ExtObj1" in output_json
        )
        # Check if the ParsedProject has external_objects field populated
        has_ext_obj_field = hasattr(project, "external_objects") and getattr(
            project, "external_objects", None
        )
        assert has_external_objects or has_ext_obj_field, (
            "External_Objects section content not found in output. "
            "Bug confirmed: no parser handles External_Objects, section is silently ignored."
        )


class TestBugConditionTaskGraphicChildTextReturnsNone:
    """Bug Condition: TaskGraphic pos_x, pos_y are all None despite valid child-text XML.

    **Validates: Requirements 1.3**

    Expected behavior (post-fix): parse_file() with TaskGraphic child-text elements
    returns non-None values for position fields.
    """

    @given(
        pos_x=st.integers(min_value=0, max_value=2000),
        pos_y=st.integers(min_value=0, max_value=2000),
        width=st.integers(min_value=10, max_value=500),
        height=st.integers(min_value=10, max_value=500),
    )
    @settings(
        max_examples=5, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_task_graphic_child_text_position_not_none(
        self, pos_x, pos_y, width, height
    ):
        """Layout parser should read child text elements, not attributes, for position."""
        xml = f"""
        <ProjectCollection>
            <ProcessFlowControlManager>
                <ProcessFlowControlState ContainerID="pfc-001">
                    <TaskGraphic Type="Node" Id="tg-001" Element="elem-001">
                        <PosX>{pos_x}</PosX>
                        <PosY>{pos_y}</PosY>
                        <Width>{width}</Width>
                        <Height>{height}</Height>
                    </TaskGraphic>
                </ProcessFlowControlState>
            </ProcessFlowControlManager>
        </ProjectCollection>
        """
        root = ET.fromstring(xml)
        result = parse_visual_layout(root)

        tg = result.process_flow_states[0].task_graphics[0]
        # When values are stored as child text elements, the parser should
        # read them using child-text access, not attribute access
        assert tg.pos_x is not None, (
            f"pos_x is None despite <PosX>{pos_x}</PosX> being present as child text. "
            f"Bug confirmed: parser uses graphic_elem.get('PosX') (attribute access) "
            f"instead of reading child text elements."
        )
        assert tg.pos_y is not None, (
            f"pos_y is None despite <PosY>{pos_y}</PosY> being present as child text. "
            f"Bug confirmed: attribute-access pattern returns None for child-text elements."
        )
        assert tg.width is not None, (
            f"width is None despite <Width>{width}</Width> being present as child text."
        )
        assert tg.height is not None, (
            f"height is None despite <Height>{height}</Height> being present as child text."
        )


class TestBugConditionSilentErrorSwallowing:
    """Bug Condition: Missing required sections are silently swallowed (no ValueError raised).

    **Validates: Requirements 1.8**

    Expected behavior (post-fix): A typed parser encountering a missing required section
    raises ValueError instead of returning None.
    """

    @given(
        element_id=st.from_regex(r"[A-Z][A-Z0-9]{3,7}", fullmatch=True),
    )
    @settings(max_examples=5)
    def test_shortcut_missing_section_raises_valueerror(self, element_id):
        """parse_shortcut() with missing SHORTCUT section should raise ValueError."""
        # This test verifies the parser itself raises ValueError.
        # The bug is that parse_file() swallows this error silently.
        xml = f"""
        <Element Type="SAS.EG.ProjectElements.ShortCutToData" Label="Bad Shortcut" ID="{element_id}">
            <Element>
                <Label>Bad Shortcut</Label>
                <ID>{element_id}</ID>
                <Type>SAS.EG.ProjectElements.ShortCutToData</Type>
            </Element>
            <!-- Missing SHORTCUT section entirely -->
        </Element>
        """
        element_node = ET.fromstring(xml)
        metadata = ElementMetadata(
            label="Bad Shortcut",
            id=element_id,
            type="SAS.EG.ProjectElements.ShortCutToData",
        )

        # The parser itself should raise ValueError (this part works)
        with pytest.raises(ValueError, match="missing the SHORTCUT section"):
            parse_shortcut(element_node, metadata, is_data=True)

    def test_parse_file_propagates_error_for_missing_section(self, tmp_path):
        """parse_file() should propagate ValueError when typed parser fails, not swallow it.

        Bug condition: parse_file() wraps typed parser calls in try/except ValueError
        and logs a warning instead of propagating the error.

        Scoped PBT: tests multiple element IDs that have missing required sections.
        """
        test_ids = ["SC001", "BADSC", "MISS99"]
        for element_id in test_ids:
            # Create a ShortCutToData element WITHOUT the required SHORTCUT section
            xml = f"""<?xml version="1.0" encoding="utf-8"?>
<ProjectCollection EGVersion="8.1" Type="SAS.EG.ProjectElements.ProjectCollection">
    <Project>
        <Element>
            <Label>Test Project</Label>
            <ID>PROJ001</ID>
            <Type>SAS.EG.ProjectElements.Project</Type>
        </Element>
    </Project>
    <Elements>
        <Element Type="SAS.EG.ProjectElements.ShortCutToData" Label="Bad Shortcut" ID="{element_id}">
            <Element>
                <Label>Bad Shortcut</Label>
                <ID>{element_id}</ID>
                <Type>SAS.EG.ProjectElements.ShortCutToData</Type>
            </Element>
            <!-- SHORTCUT section intentionally missing to trigger error -->
        </Element>
        <Element Type="SAS.EG.ProjectElements.ProjectLog" Label="Project Log" ID="PL001">
            <Enabled>True</Enabled>
            <WrittenTo>False</WrittenTo>
        </Element>
    </Elements>
</ProjectCollection>"""
            archive_bytes = _create_egp_archive(xml)
            egp_path = _write_temp_egp(tmp_path, archive_bytes)

            # Expected behavior: parse_file() should raise ValueError (error propagation)
            # Bug behavior: parse_file() silently swallows the error and continues
            with pytest.raises(ValueError):
                parse_file(egp_path)
