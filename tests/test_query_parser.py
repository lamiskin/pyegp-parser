"""Unit tests for the Query parser.

Tests cover:
- Full Query element parsing with SubmitableElement and QueryModel
- Missing QueryModel raises ValueError
- SubmitableElement parsing with all fields
- Empty/absent SubmitableElement returns defaults
- InputTables extraction with all attributes
- ResultItems extraction with all attributes
- Calculations with nested Expression trees
- JoinItems extraction
- WhereFilters and HavingFilters with hierarchical FilterNode trees
- OrderItems and GroupItems extraction
- QueryBuilderSettings table positions
- QueryModel scalar settings (DisplayVarsSortOrder, UseLabelsForVarNames)
- Absent collections default to empty lists
- Reusable parse_submitable_element function
"""

import xml.etree.ElementTree as ET

import pytest

from pyegp_parser.models.query import (
    QueryModel,
)
from pyegp_parser.models.tasks import SubmitableElement
from pyegp_parser.parsers.query_parser import (
    parse_query,
    parse_submitable_element,
)

# --- Fixtures: Full Query Element ---

FULL_QUERY_XML = """\
<Element Type="SAS.EG.ProjectElements.Query" Label="My Query" ID="q-001">
  <SubmitableElement>
    <UseGlobalOptions>True</UseGlobalOptions>
    <Server>SASApp</Server>
    <HASERROR>False</HASERROR>
    <HASWARNING>False</HASWARNING>
    <ExecutionTimeSpan>00:00:05</ExecutionTimeSpan>
    <ODSGraphicsEnabled>True</ODSGraphicsEnabled>
    <ODSHTMLStyle>HTMLBlue</ODSHTMLStyle>
    <Parameters>
      <Parameter Name="p1" Value="v1" />
      <Parameter Name="p2" Value="v2" />
    </Parameters>
    <ExpectedOutputDataList>
      <OutputData>output-1</OutputData>
      <OutputData>output-2</OutputData>
    </ExpectedOutputDataList>
    <JobRecipe>
      <ODSResultsList>
        <ODSResult ID="ods-1" Type="PowerPoint" />
      </ODSResultsList>
    </JobRecipe>
  </SubmitableElement>
  <QueryModel>
    <UseExplicitAndExecute>True</UseExplicitAndExecute>
    <KeepResultsInDatabaseIfPossible>False</KeepResultsInDatabaseIfPossible>
    <InObs>100</InObs>
    <OutObs>50</OutObs>
    <OutputLibrary>WORK</OutputLibrary>
    <OutputMember>RESULT</OutputMember>
    <OutputType>DATA</OutputType>
    <Server>SASApp</Server>
    <AllowDuplicates>True</AllowDuplicates>
    <OutputLabel>My Output</OutputLabel>
    <OutputOptions>REPLACE</OutputOptions>
    <Title>Query Title</Title>
    <Footnote>Query Footnote</Footnote>
    <GroupingStyle>Standard</GroupingStyle>
    <PassthroughEnabled>False</PassthroughEnabled>
    <PassthroughServer>PTServer</PassthroughServer>
    <PassthroughLibrary>PTLib</PassthroughLibrary>
    <PassthroughMember>PTMember</PassthroughMember>
    <DisplayVarsSortOrder>Alphabetical</DisplayVarsSortOrder>
    <UseLabelsForVarNames>True</UseLabelsForVarNames>
    <InputTables>
      <InputTable ID="it-1" InputTableName="TABLE1" Alias="t1" DataID="d-1"
                  IncludeSchema="True" Schema="WORK" Options="keep=col1"
                  Expanded="True" OriginalServer="SASApp"
                  OriginalLibrary="WORK" OriginalMember="TABLE1"
                  OriginalEngine="V9" />
      <InputTable ID="it-2" InputTableName="TABLE2" Alias="t2" DataID="d-2" />
    </InputTables>
    <ResultItems>
      <ResultItem ResultID="r-1" Alias="col1" TableID="it-1" Format="$20."
                  Length="20" Label="Column One" LabelModified="True"
                  BaseColumnName="COL1" />
      <ResultItem ResultID="r-2" Alias="col2" TableID="it-2"
                  BaseColumnName="COL2" CalcID="c-1" />
    </ResultItems>
    <Calculations>
      <Calculation ID="c-1" Alias="calc1" Format="BEST12." Label="Sum Amount"
                   Length="8" IsAggregate="True" IsReplacement="False"
                   ColumnName="total_amount">
        <Expression ExpressionType="Function" ExpressionText="SUM">
          <SubExpression ExpressionType="Column" ExpressionText="t1.amount" />
          <SubExpression ExpressionType="Literal" ExpressionText="0" />
        </Expression>
      </Calculation>
    </Calculations>
    <JoinItems>
      <JoinItem LeftTableID="it-1" LeftColumnName="id"
                RightTableID="it-2" RightColumnName="t1_id"
                JoinOperator="=" JoinType="INNER" JoinFilter="active=1" />
    </JoinItems>
    <WhereFilters>
      <FilterNode FilterType="AND">
        <FilterNode FilterType="Condition" TableID="it-1"
                    ColumnName="status" Operator="=" Value="active" />
        <FilterNode FilterType="Condition" TableID="it-1"
                    ColumnName="age" Operator=">" Value="18" />
      </FilterNode>
    </WhereFilters>
    <HavingFilters>
      <FilterNode FilterType="Condition" TableID="it-1"
                  ColumnName="total" Operator=">" Value="100" />
    </HavingFilters>
    <OrderItems>
      <OrderItem TableID="it-1" ColumnName="date" SortDirection="DESC" />
      <OrderItem TableID="it-2" ColumnName="name" SortDirection="ASC" />
    </OrderItems>
    <GroupItems>
      <GroupItem TableID="it-1" ColumnName="category" />
      <GroupItem TableID="it-1" ColumnName="region" />
    </GroupItems>
    <QueryBuilderSettings>
      <TablePosition TableID="it-1" X="10" Y="20" Width="200" Height="150" />
      <TablePosition TableID="it-2" X="300" Y="20" Width="200" Height="150" />
    </QueryBuilderSettings>
  </QueryModel>
</Element>
"""

MISSING_QUERY_MODEL_XML = """\
<Element Type="SAS.EG.ProjectElements.Query" Label="Bad Query" ID="q-bad">
  <SubmitableElement>
    <UseGlobalOptions>True</UseGlobalOptions>
    <Server>SASApp</Server>
  </SubmitableElement>
</Element>
"""

MINIMAL_QUERY_XML = """\
<Element Type="SAS.EG.ProjectElements.Query" Label="Minimal" ID="q-min">
  <QueryModel>
    <OutputLibrary>WORK</OutputLibrary>
    <OutputMember>MINIMAL</OutputMember>
  </QueryModel>
</Element>
"""

EMPTY_COLLECTIONS_XML = """\
<Element Type="SAS.EG.ProjectElements.Query" Label="Empty" ID="q-empty">
  <QueryModel>
    <InputTables />
    <ResultItems />
    <Calculations />
    <JoinItems />
    <WhereFilters />
    <HavingFilters />
    <OrderItems />
    <GroupItems />
    <QueryBuilderSettings />
  </QueryModel>
</Element>
"""

NESTED_EXPRESSION_XML = """\
<Element Type="SAS.EG.ProjectElements.Query" Label="Nested" ID="q-nested">
  <QueryModel>
    <Calculations>
      <Calculation ID="c-deep" Alias="deep_calc">
        <Expression ExpressionType="Function" ExpressionText="CASE">
          <SubExpression ExpressionType="Condition" ExpressionText="WHEN">
            <SubExpression ExpressionType="Column" ExpressionText="t1.flag" />
            <SubExpression ExpressionType="Literal" ExpressionText="1" />
          </SubExpression>
          <SubExpression ExpressionType="Literal" ExpressionText="DEFAULT" />
        </Expression>
      </Calculation>
    </Calculations>
  </QueryModel>
</Element>
"""

DEEP_FILTER_TREE_XML = """\
<Element Type="SAS.EG.ProjectElements.Query" Label="DeepFilter" ID="q-deep">
  <QueryModel>
    <WhereFilters>
      <FilterNode FilterType="OR">
        <FilterNode FilterType="AND">
          <FilterNode FilterType="Condition" TableID="t1"
                      ColumnName="x" Operator="=" Value="1" />
          <FilterNode FilterType="Condition" TableID="t1"
                      ColumnName="y" Operator="=" Value="2" />
        </FilterNode>
        <FilterNode FilterType="Condition" TableID="t2"
                    ColumnName="z" Operator=">" Value="3" />
      </FilterNode>
    </WhereFilters>
  </QueryModel>
</Element>
"""

SUBMITABLE_ONLY_XML = """\
<Element Type="SAS.EG.ProjectElements.CodeTask" Label="Code" ID="ct-1">
  <SubmitableElement>
    <UseGlobalOptions>False</UseGlobalOptions>
    <Server>GridServer</Server>
    <HASERROR>True</HASERROR>
    <HASWARNING>True</HASWARNING>
    <ExecutionTimeSpan>00:01:30</ExecutionTimeSpan>
    <ODSPDFEnabled>True</ODSPDFEnabled>
    <ODSPDFStyle>Printer</ODSPDFStyle>
    <Parameters>
      <Parameter Name="macro_var" Value="test_value" />
    </Parameters>
    <ExpectedOutputDataList>
      <OutputData>data-out-1</OutputData>
    </ExpectedOutputDataList>
  </SubmitableElement>
</Element>
"""

NO_SUBMITABLE_XML = """\
<Element Type="SAS.EG.ProjectElements.Query" Label="NoSub" ID="q-nosub">
  <QueryModel>
    <OutputLibrary>WORK</OutputLibrary>
  </QueryModel>
</Element>
"""


# --- Tests ---


class TestParseQueryFullExtraction:
    """Test full extraction of a complete Query element."""

    def setup_method(self):
        self.root = ET.fromstring(FULL_QUERY_XML)
        self.submitable, self.query_model = parse_query(self.root)

    def test_returns_tuple(self):
        assert isinstance(self.submitable, SubmitableElement)
        assert isinstance(self.query_model, QueryModel)

    def test_submitable_fields(self):
        assert self.submitable.use_global_options is True
        assert self.submitable.server == "SASApp"
        assert self.submitable.has_error is False
        assert self.submitable.has_warning is False
        assert self.submitable.execution_time_span == "00:00:05"

    def test_submitable_ods_overrides(self):
        assert self.submitable.ods_style_overrides is not None
        assert self.submitable.ods_style_overrides["ODSGraphicsEnabled"] == "True"
        assert self.submitable.ods_style_overrides["ODSHTMLStyle"] == "HTMLBlue"

    def test_submitable_parameters(self):
        assert len(self.submitable.parameters) == 2
        assert self.submitable.parameters[0] == {"Name": "p1", "Value": "v1"}
        assert self.submitable.parameters[1] == {"Name": "p2", "Value": "v2"}

    def test_submitable_expected_output_data_list(self):
        assert self.submitable.expected_output_data_list == [
            "output-1",
            "output-2",
        ]

    def test_submitable_job_recipe(self):
        assert self.submitable.job_recipe is not None
        assert "ODSResultsList" in self.submitable.job_recipe
        assert len(self.submitable.job_recipe["ODSResultsList"]) == 1
        assert self.submitable.job_recipe["ODSResultsList"][0]["ID"] == "ods-1"

    def test_query_model_scalar_settings(self):
        qm = self.query_model
        assert qm.use_explicit_and_execute is True
        assert qm.keep_results_in_database_if_possible is False
        assert qm.in_obs == 100
        assert qm.out_obs == 50
        assert qm.output_library == "WORK"
        assert qm.output_member == "RESULT"
        assert qm.output_type == "DATA"
        assert qm.server == "SASApp"
        assert qm.allow_duplicates is True
        assert qm.output_label == "My Output"
        assert qm.output_options == "REPLACE"
        assert qm.title == "Query Title"
        assert qm.footnote == "Query Footnote"
        assert qm.grouping_style == "Standard"
        assert qm.passthrough_enabled is False
        assert qm.passthrough_server == "PTServer"
        assert qm.passthrough_library == "PTLib"
        assert qm.passthrough_member == "PTMember"
        assert qm.display_vars_sort_order == "Alphabetical"
        assert qm.use_labels_for_var_names is True

    def test_input_tables(self):
        tables = self.query_model.input_tables
        assert len(tables) == 2

        t1 = tables[0]
        assert t1.id == "it-1"
        assert t1.input_table_name == "TABLE1"
        assert t1.alias == "t1"
        assert t1.data_id == "d-1"
        assert t1.include_schema is True
        assert t1.schema == "WORK"
        assert t1.options == "keep=col1"
        assert t1.expanded is True
        assert t1.original_server == "SASApp"
        assert t1.original_library == "WORK"
        assert t1.original_member == "TABLE1"
        assert t1.original_engine == "V9"

        t2 = tables[1]
        assert t2.id == "it-2"
        assert t2.input_table_name == "TABLE2"
        assert t2.alias == "t2"
        assert t2.include_schema is None
        assert t2.schema is None

    def test_result_items(self):
        items = self.query_model.result_items
        assert len(items) == 2

        r1 = items[0]
        assert r1.result_id == "r-1"
        assert r1.alias == "col1"
        assert r1.table_id == "it-1"
        assert r1.format == "$20."
        assert r1.length == 20
        assert r1.label == "Column One"
        assert r1.label_modified is True
        assert r1.base_column_name == "COL1"
        assert r1.calc_id is None

        r2 = items[1]
        assert r2.result_id == "r-2"
        assert r2.calc_id == "c-1"

    def test_calculations(self):
        calcs = self.query_model.calculations
        assert len(calcs) == 1

        c = calcs[0]
        assert c.id == "c-1"
        assert c.alias == "calc1"
        assert c.format == "BEST12."
        assert c.label == "Sum Amount"
        assert c.length == 8
        assert c.is_aggregate is True
        assert c.is_replacement is False
        assert c.column_name == "total_amount"

    def test_calculation_expression(self):
        expr = self.query_model.calculations[0].expression
        assert expr is not None
        assert expr.expression_type == "Function"
        assert expr.expression_text == "SUM"
        assert len(expr.sub_expressions) == 2
        assert expr.sub_expressions[0].expression_type == "Column"
        assert expr.sub_expressions[0].expression_text == "t1.amount"
        assert expr.sub_expressions[1].expression_type == "Literal"
        assert expr.sub_expressions[1].expression_text == "0"

    def test_join_items(self):
        joins = self.query_model.join_items
        assert len(joins) == 1

        j = joins[0]
        assert j.left_table_id == "it-1"
        assert j.left_column_name == "id"
        assert j.right_table_id == "it-2"
        assert j.right_column_name == "t1_id"
        assert j.join_operator == "="
        assert j.join_type == "INNER"
        assert j.join_filter == "active=1"

    def test_where_filters(self):
        filters = self.query_model.where_filters
        assert len(filters) == 1

        root_filter = filters[0]
        assert root_filter.filter_type == "AND"
        assert len(root_filter.children) == 2

        child1 = root_filter.children[0]
        assert child1.filter_type == "Condition"
        assert child1.table_id == "it-1"
        assert child1.column_name == "status"
        assert child1.operator == "="
        assert child1.value == "active"
        assert child1.children == []

        child2 = root_filter.children[1]
        assert child2.column_name == "age"
        assert child2.operator == ">"
        assert child2.value == "18"

    def test_having_filters(self):
        filters = self.query_model.having_filters
        assert len(filters) == 1

        f = filters[0]
        assert f.filter_type == "Condition"
        assert f.table_id == "it-1"
        assert f.column_name == "total"
        assert f.operator == ">"
        assert f.value == "100"
        assert f.children == []

    def test_order_items(self):
        items = self.query_model.order_items
        assert len(items) == 2
        assert items[0].table_id == "it-1"
        assert items[0].column_name == "date"
        assert items[0].sort_direction == "DESC"
        assert items[1].table_id == "it-2"
        assert items[1].column_name == "name"
        assert items[1].sort_direction == "ASC"

    def test_group_items(self):
        items = self.query_model.group_items
        assert len(items) == 2
        assert items[0].table_id == "it-1"
        assert items[0].column_name == "category"
        assert items[1].table_id == "it-1"
        assert items[1].column_name == "region"

    def test_query_builder_settings(self):
        settings = self.query_model.query_builder_settings
        assert len(settings) == 2

        s1 = settings[0]
        assert s1.table_id == "it-1"
        assert s1.x == 10
        assert s1.y == 20
        assert s1.width == 200
        assert s1.height == 150

        s2 = settings[1]
        assert s2.table_id == "it-2"
        assert s2.x == 300


class TestParseQueryMissingQueryModel:
    """Test that missing QueryModel raises ValueError."""

    def test_raises_value_error(self):
        root = ET.fromstring(MISSING_QUERY_MODEL_XML)
        with pytest.raises(ValueError, match="missing required QueryModel"):
            parse_query(root)

    def test_error_includes_element_id(self):
        root = ET.fromstring(MISSING_QUERY_MODEL_XML)
        with pytest.raises(ValueError, match="q-bad"):
            parse_query(root)


class TestParseQueryMinimal:
    """Test parsing a minimal Query with only a few QueryModel fields."""

    def test_minimal_query_parses(self):
        root = ET.fromstring(MINIMAL_QUERY_XML)
        submitable, query_model = parse_query(root)

        assert query_model.output_library == "WORK"
        assert query_model.output_member == "MINIMAL"
        assert query_model.server is None
        assert query_model.in_obs is None
        assert query_model.use_explicit_and_execute is None

    def test_minimal_query_collections_empty(self):
        root = ET.fromstring(MINIMAL_QUERY_XML)
        _, query_model = parse_query(root)

        assert query_model.input_tables == []
        assert query_model.result_items == []
        assert query_model.calculations == []
        assert query_model.join_items == []
        assert query_model.where_filters == []
        assert query_model.having_filters == []
        assert query_model.order_items == []
        assert query_model.group_items == []
        assert query_model.query_builder_settings == []

    def test_minimal_submitable_defaults(self):
        root = ET.fromstring(MINIMAL_QUERY_XML)
        submitable, _ = parse_query(root)

        assert submitable.use_global_options is None
        assert submitable.server is None
        assert submitable.has_error is None
        assert submitable.has_warning is None
        assert submitable.execution_time_span is None
        assert submitable.ods_style_overrides is None
        assert submitable.expected_output_data_list == []
        assert submitable.parameters == []
        assert submitable.job_recipe is None


class TestParseQueryEmptyCollections:
    """Test that empty collection elements produce empty lists (Req 8.12)."""

    def test_empty_input_tables(self):
        root = ET.fromstring(EMPTY_COLLECTIONS_XML)
        _, qm = parse_query(root)
        assert qm.input_tables == []

    def test_empty_result_items(self):
        root = ET.fromstring(EMPTY_COLLECTIONS_XML)
        _, qm = parse_query(root)
        assert qm.result_items == []

    def test_empty_calculations(self):
        root = ET.fromstring(EMPTY_COLLECTIONS_XML)
        _, qm = parse_query(root)
        assert qm.calculations == []

    def test_empty_join_items(self):
        root = ET.fromstring(EMPTY_COLLECTIONS_XML)
        _, qm = parse_query(root)
        assert qm.join_items == []

    def test_empty_where_filters(self):
        root = ET.fromstring(EMPTY_COLLECTIONS_XML)
        _, qm = parse_query(root)
        assert qm.where_filters == []

    def test_empty_having_filters(self):
        root = ET.fromstring(EMPTY_COLLECTIONS_XML)
        _, qm = parse_query(root)
        assert qm.having_filters == []

    def test_empty_order_items(self):
        root = ET.fromstring(EMPTY_COLLECTIONS_XML)
        _, qm = parse_query(root)
        assert qm.order_items == []

    def test_empty_group_items(self):
        root = ET.fromstring(EMPTY_COLLECTIONS_XML)
        _, qm = parse_query(root)
        assert qm.group_items == []

    def test_empty_query_builder_settings(self):
        root = ET.fromstring(EMPTY_COLLECTIONS_XML)
        _, qm = parse_query(root)
        assert qm.query_builder_settings == []


class TestNestedExpressions:
    """Test deeply nested Expression trees in Calculations."""

    def test_deep_nested_expressions(self):
        root = ET.fromstring(NESTED_EXPRESSION_XML)
        _, qm = parse_query(root)

        calc = qm.calculations[0]
        assert calc.id == "c-deep"
        assert calc.alias == "deep_calc"

        expr = calc.expression
        assert expr.expression_type == "Function"
        assert expr.expression_text == "CASE"
        assert len(expr.sub_expressions) == 2

        # First sub-expression has its own nested sub-expressions
        when_expr = expr.sub_expressions[0]
        assert when_expr.expression_type == "Condition"
        assert when_expr.expression_text == "WHEN"
        assert len(when_expr.sub_expressions) == 2
        assert when_expr.sub_expressions[0].expression_type == "Column"
        assert when_expr.sub_expressions[0].expression_text == "t1.flag"
        assert when_expr.sub_expressions[1].expression_type == "Literal"
        assert when_expr.sub_expressions[1].expression_text == "1"

        # Second sub-expression is a leaf
        default_expr = expr.sub_expressions[1]
        assert default_expr.expression_type == "Literal"
        assert default_expr.expression_text == "DEFAULT"
        assert default_expr.sub_expressions == []

    def test_calculation_without_expression(self):
        xml = """\
<Element ID="q-noexpr">
  <QueryModel>
    <Calculations>
      <Calculation ID="c-noexpr" Alias="plain" />
    </Calculations>
  </QueryModel>
</Element>
"""
        root = ET.fromstring(xml)
        _, qm = parse_query(root)

        assert qm.calculations[0].expression is None


class TestDeepFilterTree:
    """Test hierarchical FilterNode trees in Where/Having filters."""

    def test_nested_filter_tree(self):
        root = ET.fromstring(DEEP_FILTER_TREE_XML)
        _, qm = parse_query(root)

        filters = qm.where_filters
        assert len(filters) == 1

        # Top level: OR
        or_node = filters[0]
        assert or_node.filter_type == "OR"
        assert len(or_node.children) == 2

        # First child: AND with two conditions
        and_node = or_node.children[0]
        assert and_node.filter_type == "AND"
        assert len(and_node.children) == 2
        assert and_node.children[0].column_name == "x"
        assert and_node.children[0].value == "1"
        assert and_node.children[1].column_name == "y"
        assert and_node.children[1].value == "2"

        # Second child: single condition
        cond_node = or_node.children[1]
        assert cond_node.filter_type == "Condition"
        assert cond_node.table_id == "t2"
        assert cond_node.column_name == "z"
        assert cond_node.operator == ">"
        assert cond_node.value == "3"
        assert cond_node.children == []


class TestParseSubmitableElement:
    """Test the reusable parse_submitable_element function."""

    def test_full_submitable_extraction(self):
        root = ET.fromstring(SUBMITABLE_ONLY_XML)
        submitable = parse_submitable_element(root)

        assert submitable.use_global_options is False
        assert submitable.server == "GridServer"
        assert submitable.has_error is True
        assert submitable.has_warning is True
        assert submitable.execution_time_span == "00:01:30"

    def test_submitable_ods_overrides(self):
        root = ET.fromstring(SUBMITABLE_ONLY_XML)
        submitable = parse_submitable_element(root)

        assert submitable.ods_style_overrides is not None
        assert submitable.ods_style_overrides["ODSPDFEnabled"] == "True"
        assert submitable.ods_style_overrides["ODSPDFStyle"] == "Printer"

    def test_submitable_parameters(self):
        root = ET.fromstring(SUBMITABLE_ONLY_XML)
        submitable = parse_submitable_element(root)

        assert len(submitable.parameters) == 1
        assert submitable.parameters[0] == {
            "Name": "macro_var",
            "Value": "test_value",
        }

    def test_submitable_expected_output(self):
        root = ET.fromstring(SUBMITABLE_ONLY_XML)
        submitable = parse_submitable_element(root)

        assert submitable.expected_output_data_list == ["data-out-1"]

    def test_absent_submitable_returns_defaults(self):
        root = ET.fromstring(NO_SUBMITABLE_XML)
        submitable = parse_submitable_element(root)

        assert submitable.use_global_options is None
        assert submitable.server is None
        assert submitable.has_error is None
        assert submitable.has_warning is None
        assert submitable.execution_time_span is None
        assert submitable.ods_style_overrides is None
        assert submitable.expected_output_data_list == []
        assert submitable.parameters == []
        assert submitable.job_recipe is None


class TestParseQueryDisplaySettings:
    """Test DisplayVarsSortOrder and UseLabelsForVarNames extraction."""

    def test_display_vars_sort_order(self):
        root = ET.fromstring(FULL_QUERY_XML)
        _, qm = parse_query(root)
        assert qm.display_vars_sort_order == "Alphabetical"

    def test_use_labels_for_var_names(self):
        root = ET.fromstring(FULL_QUERY_XML)
        _, qm = parse_query(root)
        assert qm.use_labels_for_var_names is True

    def test_absent_display_settings(self):
        root = ET.fromstring(MINIMAL_QUERY_XML)
        _, qm = parse_query(root)
        assert qm.display_vars_sort_order is None
        assert qm.use_labels_for_var_names is None
