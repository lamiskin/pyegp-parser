"""Tests for pyegp_parser.models element type modules.

Verifies that all element models can be constructed correctly with
default values and with explicit values, and that element type
classification works as expected.
"""

from pyegp_parser.models.base import ElementMetadata
from pyegp_parser.models.elements import ElementCategory, classify_element_type
from pyegp_parser.models.log_code import CodeElement, LogElement
from pyegp_parser.models.process_flow import Connection, DAGModel, ProcessFlowContainer
from pyegp_parser.models.query import (
    Calculation,
    Expression,
    FilterNode,
    GroupItem,
    InputTable,
    JoinItem,
    OrderItem,
    QueryBuilderTablePosition,
    QueryModel,
    ResultItem,
)
from pyegp_parser.models.tasks import (
    AppendTaskElement,
    CodeTaskElement,
    EGTaskElement,
    ExportTaskElement,
    ImportTaskElement,
    SubmitableElement,
)

# ========== Element Classification Tests ==========


class TestElementCategoryEnum:
    """Verify the ElementCategory enum contains all expected members."""

    def test_all_categories_present(self):
        expected = {
            "PROCESS_FLOW_CONTAINER",
            "SHORTCUT_TO_FILE",
            "SHORTCUT_TO_DATA",
            "QUERY",
            "IMPORT_TASK",
            "EXPORT_TASK",
            "CODE_TASK",
            "EG_TASK",
            "APPEND_TASK",
            "LOG",
            "CODE",
            "PROJECT_LOG",
            "UNKNOWN",
        }
        actual = {member.name for member in ElementCategory}
        assert actual == expected

    def test_enum_values_match_type_segments(self):
        """Each enum value is the final segment of the type string."""
        assert ElementCategory.PROCESS_FLOW_CONTAINER.value == "ProcessFlowContainer"
        assert ElementCategory.QUERY.value == "Query"
        assert ElementCategory.CODE_TASK.value == "CodeTask"
        assert ElementCategory.UNKNOWN.value == "Unknown"


class TestClassifyElementType:
    """Verify classify_element_type dispatches correctly."""

    def test_fully_qualified_type_returns_correct_category(self):
        result = classify_element_type("SAS.EG.ProjectElements.ProcessFlowContainer")
        assert result == ElementCategory.PROCESS_FLOW_CONTAINER

    def test_query_type(self):
        result = classify_element_type("SAS.EG.ProjectElements.Query")
        assert result == ElementCategory.QUERY

    def test_import_task_type(self):
        result = classify_element_type("SAS.EG.ProjectElements.ImportTask")
        assert result == ElementCategory.IMPORT_TASK

    def test_code_task_type(self):
        result = classify_element_type("SAS.EG.ProjectElements.CodeTask")
        assert result == ElementCategory.CODE_TASK

    def test_eg_task_type(self):
        result = classify_element_type("SAS.EG.ProjectElements.EGTask")
        assert result == ElementCategory.EG_TASK

    def test_export_task_type(self):
        result = classify_element_type("SAS.EG.ProjectElements.ExportTask")
        assert result == ElementCategory.EXPORT_TASK

    def test_append_task_type(self):
        result = classify_element_type("SAS.EG.ProjectElements.AppendTask")
        assert result == ElementCategory.APPEND_TASK

    def test_log_type(self):
        result = classify_element_type("SAS.EG.ProjectElements.Log")
        assert result == ElementCategory.LOG

    def test_code_type(self):
        result = classify_element_type("SAS.EG.ProjectElements.Code")
        assert result == ElementCategory.CODE

    def test_shortcut_to_data_type(self):
        result = classify_element_type("SAS.EG.ProjectElements.ShortCutToData")
        assert result == ElementCategory.SHORTCUT_TO_DATA

    def test_shortcut_to_file_type(self):
        result = classify_element_type("SAS.EG.ProjectElements.ShortCutToFile")
        assert result == ElementCategory.SHORTCUT_TO_FILE

    def test_project_log_type(self):
        result = classify_element_type("SAS.EG.ProjectElements.ProjectLog")
        assert result == ElementCategory.PROJECT_LOG

    def test_unknown_type_returns_unknown(self):
        result = classify_element_type("SAS.EG.ProjectElements.SomethingElse")
        assert result == ElementCategory.UNKNOWN

    def test_empty_string_returns_unknown(self):
        result = classify_element_type("")
        assert result == ElementCategory.UNKNOWN

    def test_single_segment_known_type(self):
        """A type string with no dots still classifies by the whole string."""
        result = classify_element_type("Query")
        assert result == ElementCategory.QUERY

    def test_single_segment_unknown_type(self):
        result = classify_element_type("Foobar")
        assert result == ElementCategory.UNKNOWN


# ========== Query Model Tests ==========


class TestQueryModelDefaults:
    """Verify QueryModel and sub-models construct with proper defaults."""

    def test_query_model_default_construction(self):
        qm = QueryModel()
        assert qm.use_explicit_and_execute is None
        assert qm.input_tables == []
        assert qm.result_items == []
        assert qm.calculations == []
        assert qm.join_items == []
        assert qm.where_filters == []
        assert qm.having_filters == []
        assert qm.order_items == []
        assert qm.group_items == []
        assert qm.query_builder_settings == []
        assert qm.output_library is None

    def test_input_table_default(self):
        t = InputTable()
        assert t.id is None
        assert t.input_table_name is None
        assert t.include_schema is None

    def test_result_item_default(self):
        r = ResultItem()
        assert r.result_id is None
        assert r.alias is None

    def test_expression_recursive(self):
        """Expression supports nested sub_expressions."""
        inner = Expression(expression_type="literal", expression_text="42")
        outer = Expression(
            expression_type="function",
            expression_text="SUM",
            sub_expressions=[inner],
        )
        assert outer.sub_expressions[0].expression_text == "42"

    def test_calculation_with_expression(self):
        expr = Expression(expression_type="column", expression_text="col1")
        calc = Calculation(id="calc-1", alias="total", expression=expr)
        assert calc.expression.expression_type == "column"

    def test_filter_node_hierarchical(self):
        """FilterNode supports nested children for AND/OR groups."""
        child1 = FilterNode(
            filter_type="condition", column_name="age", operator=">", value="18"
        )
        child2 = FilterNode(
            filter_type="condition", column_name="name", operator="=", value="A"
        )
        parent = FilterNode(filter_type="and", children=[child1, child2])
        assert len(parent.children) == 2
        assert parent.children[0].column_name == "age"

    def test_join_item_construction(self):
        j = JoinItem(
            left_table_id="t1",
            left_column_name="id",
            right_table_id="t2",
            right_column_name="t1_id",
            join_type="INNER",
        )
        assert j.left_table_id == "t1"
        assert j.join_type == "INNER"

    def test_order_item_construction(self):
        o = OrderItem(table_id="t1", column_name="date", sort_direction="DESC")
        assert o.sort_direction == "DESC"

    def test_group_item_construction(self):
        g = GroupItem(table_id="t1", column_name="category")
        assert g.column_name == "category"

    def test_query_builder_table_position(self):
        pos = QueryBuilderTablePosition(
            table_id="t1", x=100, y=200, width=300, height=150
        )
        assert pos.x == 100
        assert pos.height == 150

    def test_query_model_list_independence(self):
        """Each QueryModel instance has independent lists."""
        q1 = QueryModel()
        q2 = QueryModel()
        q1.input_tables.append(InputTable(id="t1"))
        assert q2.input_tables == []


# ========== Task Model Tests ==========


class TestSubmitableElement:
    """Verify SubmitableElement construction."""

    def test_default_construction(self):
        s = SubmitableElement()
        assert s.use_global_options is None
        assert s.server is None
        assert s.has_error is None
        assert s.has_warning is None
        assert s.ods_style_overrides is None
        assert s.expected_output_data_list == []
        assert s.parameters == []
        assert s.execution_time_span is None
        assert s.job_recipe is None

    def test_list_independence(self):
        s1 = SubmitableElement()
        s2 = SubmitableElement()
        s1.expected_output_data_list.append("data1")
        assert s2.expected_output_data_list == []


class TestImportTaskElement:
    """Verify ImportTaskElement construction."""

    def test_default_construction(self):
        task = ImportTaskElement()
        assert task.metadata is None
        assert task.submitable is None
        assert task.eg_task_clsid is None
        assert task.input_data_list == []
        assert task.log_content is None

    def test_with_metadata_and_submitable(self):
        meta = ElementMetadata(label="Import Data", id="imp-1")
        sub = SubmitableElement(server="SASApp")
        task = ImportTaskElement(metadata=meta, submitable=sub, parent_id="pf-1")
        assert task.metadata.label == "Import Data"
        assert task.submitable.server == "SASApp"
        assert task.parent_id == "pf-1"


class TestCodeTaskElement:
    """Verify CodeTaskElement construction."""

    def test_default_construction(self):
        task = CodeTaskElement()
        assert task.metadata is None
        assert task.submitable is None
        assert task.code_content is None
        assert task.log_content is None

    def test_with_code_content(self):
        task = CodeTaskElement(
            metadata=ElementMetadata(label="My Code"),
            code_content="proc print data=work.mydata; run;",
        )
        assert task.code_content == "proc print data=work.mydata; run;"


class TestEGTaskElement:
    """Verify EGTaskElement construction."""

    def test_default_construction(self):
        task = EGTaskElement()
        assert task.metadata is None
        assert task.eg_task_clsid is None
        assert task.generates_code_flag is None
        assert task.task_config is None

    def test_with_clsid(self):
        task = EGTaskElement(eg_task_clsid="{ABC-123}", generates_code_flag=True)
        assert task.eg_task_clsid == "{ABC-123}"
        assert task.generates_code_flag is True


class TestExportTaskElement:
    """Verify ExportTaskElement construction."""

    def test_default_construction(self):
        task = ExportTaskElement()
        assert task.metadata is None
        assert task.parent_id is None
        assert task.task_config is None


class TestAppendTaskElement:
    """Verify AppendTaskElement construction."""

    def test_default_construction(self):
        task = AppendTaskElement()
        assert task.metadata is None
        assert task.input_data_refs == []
        assert task.parent_id is None

    def test_list_independence(self):
        t1 = AppendTaskElement()
        t2 = AppendTaskElement()
        t1.input_data_refs.append("ref-1")
        assert t2.input_data_refs == []


# ========== Log/Code Model Tests ==========


class TestLogElement:
    """Verify LogElement construction."""

    def test_default_construction(self):
        log = LogElement()
        assert log.metadata is None
        assert log.parent_id is None
        assert log.line_size is None
        assert log.page_size is None
        assert log.portrait is None
        assert log.condition_parent is None

    def test_with_values(self):
        log = LogElement(
            metadata=ElementMetadata(label="Log Output"),
            parent_id="task-1",
            line_size=132,
            page_size=60,
            portrait=True,
        )
        assert log.line_size == 132
        assert log.portrait is True


class TestCodeElement:
    """Verify CodeElement construction."""

    def test_default_construction(self):
        code = CodeElement()
        assert code.metadata is None
        assert code.text is None
        assert code.read_only is None
        assert code.def_ext is None
        assert code.parent_id is None
        assert code.libref_code is None
        assert code.begin_app_code is None
        assert code.begin_user_code is None
        assert code.task_code is None
        assert code.end_user_code is None
        assert code.end_app_code is None
        assert code.libref_cl_code is None
        assert code.macro_assign_code is None
        assert code.macro_unassign_code is None

    def test_with_code_sections(self):
        code = CodeElement(
            text="proc print; run;",
            read_only=False,
            def_ext=".sas",
            task_code="proc means; run;",
            begin_user_code="/* user code */",
        )
        assert code.text == "proc print; run;"
        assert code.read_only is False
        assert code.task_code == "proc means; run;"


# ========== Process Flow Model Tests ==========


class TestConnection:
    """Verify Connection construction."""

    def test_construction(self):
        conn = Connection(source_id="a", target_id="b", resource_dependency=False)
        assert conn.source_id == "a"
        assert conn.target_id == "b"
        assert conn.resource_dependency is False

    def test_resource_dependency_true(self):
        conn = Connection(source_id="x", target_id="y", resource_dependency=True)
        assert conn.resource_dependency is True


class TestDAGModel:
    """Verify DAGModel construction."""

    def test_default_construction(self):
        dag = DAGModel()
        assert dag.nodes == []
        assert dag.connections == []
        assert dag.warnings == []

    def test_with_nodes_and_connections(self):
        conn = Connection(source_id="a", target_id="b", resource_dependency=False)
        dag = DAGModel(nodes=["a", "b"], connections=[conn])
        assert len(dag.nodes) == 2
        assert len(dag.connections) == 1
        assert dag.connections[0].source_id == "a"

    def test_list_independence(self):
        d1 = DAGModel()
        d2 = DAGModel()
        d1.nodes.append("node-1")
        assert d2.nodes == []


class TestProcessFlowContainer:
    """Verify ProcessFlowContainer construction."""

    def test_default_construction(self):
        pfc = ProcessFlowContainer()
        assert pfc.metadata is None
        assert pfc.dag is None

    def test_with_metadata_and_dag(self):
        meta = ElementMetadata(label="Process Flow 1", id="pf-1")
        dag = DAGModel(nodes=["a", "b", "c"])
        pfc = ProcessFlowContainer(metadata=meta, dag=dag)
        assert pfc.metadata.label == "Process Flow 1"
        assert len(pfc.dag.nodes) == 3
