"""Tests for Log and Code element parsers.

Validates Requirements 11.1 through 11.6.
"""

import xml.etree.ElementTree as ET

import pytest

from pyegp_parser.models.base import ElementMetadata
from pyegp_parser.models.log_code import CodeElement, LogElement
from pyegp_parser.parsers.log_code_parser import parse_code_element, parse_log_element


class TestParseLogElement:
    """Tests for parse_log_element function."""

    def _make_metadata(self, element_id: str = "log-001") -> ElementMetadata:
        return ElementMetadata(
            label="Test Log",
            type="SAS.EG.ProjectElements.Log",
            id=element_id,
        )

    def test_full_log_section(self):
        """Requirement 11.1: Extract all Log section fields."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.Log" Label="Log" ID="log-001">
            <Log>
                <Parent>task-abc</Parent>
                <LineSize>132</LineSize>
                <PageSize>60</PageSize>
                <Portrait>true</Portrait>
                <ConditionParent>cond-xyz</ConditionParent>
            </Log>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = self._make_metadata()

        result = parse_log_element(node, metadata)

        assert isinstance(result, LogElement)
        assert result.metadata == metadata
        assert result.parent_id == "task-abc"
        assert result.line_size == 132
        assert result.page_size == 60
        assert result.portrait is True
        assert result.condition_parent == "cond-xyz"

    def test_log_section_partial_fields(self):
        """Requirement 11.1: Absent optional fields are None."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.Log" Label="Log" ID="log-002">
            <Log>
                <Parent>task-def</Parent>
                <LineSize>80</LineSize>
            </Log>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = self._make_metadata("log-002")

        result = parse_log_element(node, metadata)

        assert result.parent_id == "task-def"
        assert result.line_size == 80
        assert result.page_size is None
        assert result.portrait is None
        assert result.condition_parent is None

    def test_log_section_portrait_false(self):
        """Portrait flag set to false."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.Log" Label="Log" ID="log-003">
            <Log>
                <Parent>task-ghi</Parent>
                <Portrait>false</Portrait>
            </Log>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = self._make_metadata("log-003")

        result = parse_log_element(node, metadata)

        assert result.portrait is False

    def test_missing_log_section_raises_value_error(self):
        """Requirement 11.2: Raise ValueError if Log section absent."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.Log" Label="Log" ID="log-004">
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = self._make_metadata("log-004")

        with pytest.raises(ValueError, match="log-004.*missing required Log section"):
            parse_log_element(node, metadata)

    def test_empty_log_section_all_none(self):
        """Log section present but all children absent returns all None fields."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.Log" Label="Log" ID="log-005">
            <Log>
            </Log>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = self._make_metadata("log-005")

        result = parse_log_element(node, metadata)

        assert result.parent_id is None
        assert result.line_size is None
        assert result.page_size is None
        assert result.portrait is None
        assert result.condition_parent is None


class TestParseCodeElement:
    """Tests for parse_code_element function."""

    def _make_metadata(self, element_id: str = "code-001") -> ElementMetadata:
        return ElementMetadata(
            label="Test Code",
            type="SAS.EG.ProjectElements.Code",
            id=element_id,
        )

    def test_text_element_and_code_section(self):
        """Requirement 11.3, 11.4: Extract both TextElement and Code section."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.Code" Label="Code" ID="code-001">
            <TextElement>
                <Text>proc print data=work.test; run;</Text>
                <ReadOnly>false</ReadOnly>
                <DefExt>.sas</DefExt>
            </TextElement>
            <Code>
                <Parent>task-abc</Parent>
                <Libref_Code>libname mylib '/path';</Libref_Code>
                <BeginAppCode>/* begin app */</BeginAppCode>
                <BeginUserCode>/* begin user */</BeginUserCode>
                <TaskCode>proc print; run;</TaskCode>
                <EndUserCode>/* end user */</EndUserCode>
                <EndAppCode>/* end app */</EndAppCode>
                <LibrefCl_Code>libname mylib clear;</LibrefCl_Code>
                <MacroAssign_Code>%let x=1;</MacroAssign_Code>
                <MacroUnassign_Code>%symdel x;</MacroUnassign_Code>
            </Code>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = self._make_metadata()

        result = parse_code_element(node, metadata)

        assert isinstance(result, CodeElement)
        assert result.metadata == metadata
        # TextElement fields
        assert result.text == "proc print data=work.test; run;"
        assert result.read_only is False
        assert result.def_ext == ".sas"
        # Code section fields
        assert result.parent_id == "task-abc"
        assert result.libref_code == "libname mylib '/path';"
        assert result.begin_app_code == "/* begin app */"
        assert result.begin_user_code == "/* begin user */"
        assert result.task_code == "proc print; run;"
        assert result.end_user_code == "/* end user */"
        assert result.end_app_code == "/* end app */"
        assert result.libref_cl_code == "libname mylib clear;"
        assert result.macro_assign_code == "%let x=1;"
        assert result.macro_unassign_code == "%symdel x;"

    def test_text_element_only_no_code_section(self):
        """Requirement 11.5: TextElement present but no Code section; code fields None."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.Code" Label="Code" ID="code-002">
            <TextElement>
                <Text>data work.hello; x=1; run;</Text>
                <ReadOnly>true</ReadOnly>
                <DefExt>.sas</DefExt>
            </TextElement>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = self._make_metadata("code-002")

        result = parse_code_element(node, metadata)

        assert result.text == "data work.hello; x=1; run;"
        assert result.read_only is True
        assert result.def_ext == ".sas"
        # Code section fields should all be None
        assert result.parent_id is None
        assert result.libref_code is None
        assert result.begin_app_code is None
        assert result.begin_user_code is None
        assert result.task_code is None
        assert result.end_user_code is None
        assert result.end_app_code is None
        assert result.libref_cl_code is None
        assert result.macro_assign_code is None
        assert result.macro_unassign_code is None

    def test_code_section_only_no_text_element(self):
        """Code section present but no TextElement; text fields None."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.Code" Label="Code" ID="code-003">
            <Code>
                <Parent>task-xyz</Parent>
                <TaskCode>proc means; run;</TaskCode>
            </Code>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = self._make_metadata("code-003")

        result = parse_code_element(node, metadata)

        # TextElement fields should be None
        assert result.text is None
        assert result.read_only is None
        assert result.def_ext is None
        # Code section fields
        assert result.parent_id == "task-xyz"
        assert result.task_code == "proc means; run;"

    def test_neither_text_nor_code_section_raises_value_error(self):
        """Requirement 11.6: Raise ValueError if neither section present."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.Code" Label="Code" ID="code-004">
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = self._make_metadata("code-004")

        with pytest.raises(ValueError, match="code-004.*no code content"):
            parse_code_element(node, metadata)

    def test_text_element_with_empty_text(self):
        """TextElement present with empty text still counts as having TextElement."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.Code" Label="Code" ID="code-005">
            <TextElement>
                <ReadOnly>false</ReadOnly>
            </TextElement>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = self._make_metadata("code-005")

        result = parse_code_element(node, metadata)

        assert result.text is None
        assert result.read_only is False
        assert result.def_ext is None
        # No Code section
        assert result.parent_id is None

    def test_code_section_partial_fields(self):
        """Code section with only some children; absent ones are None."""
        xml = """
        <Element Type="SAS.EG.ProjectElements.Code" Label="Code" ID="code-006">
            <TextElement>
                <Text>some code</Text>
            </TextElement>
            <Code>
                <Parent>parent-id</Parent>
                <BeginUserCode>/* user start */</BeginUserCode>
                <EndUserCode>/* user end */</EndUserCode>
            </Code>
        </Element>
        """
        node = ET.fromstring(xml)
        metadata = self._make_metadata("code-006")

        result = parse_code_element(node, metadata)

        assert result.text == "some code"
        assert result.parent_id == "parent-id"
        assert result.begin_user_code == "/* user start */"
        assert result.end_user_code == "/* user end */"
        assert result.libref_code is None
        assert result.begin_app_code is None
        assert result.task_code is None
        assert result.end_app_code is None
        assert result.libref_cl_code is None
        assert result.macro_assign_code is None
        assert result.macro_unassign_code is None
