"""Property-based tests for query model extraction completeness.

**Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9, 8.10, 8.12**

Uses Hypothesis to verify that:
- P1: All present InputTables are extracted with correct field values
- P2: All present ResultItems are extracted with correct field values
- P3: All present Calculations (with Expression trees) are extracted correctly
- P4: All present JoinItems are extracted with correct field values
- P5: All present FilterNodes in WhereFilters/HavingFilters (with nesting) are extracted
- P6: All present OrderItems and GroupItems are extracted correctly
- P7: Absent collections are represented as empty lists
- P8: Scalar settings match input or are None when absent
- P9: Item counts match what was generated
"""

import string
import xml.etree.ElementTree as ET

from hypothesis import given, settings
from hypothesis import strategies as st

from pyegp_parser.models.query import (
    Expression,
    FilterNode,
)
from pyegp_parser.parsers.query_parser import parse_query

# ---------------------------------------------------------------------------
# Strategies for generating Query element XML
# ---------------------------------------------------------------------------

# Basic string strategies
_id_str = st.text(
    alphabet=string.ascii_letters + string.digits,
    min_size=1,
    max_size=15,
)

# Strategy for optional strings - must not be whitespace-only since the parser
# treats whitespace-only text as None via .strip() == ""
_optional_str = st.one_of(
    st.none(),
    st.text(
        alphabet=string.ascii_letters + string.digits + "_-",
        min_size=1,
        max_size=30,
    ).filter(lambda s: s.strip() != ""),
)

_optional_int = st.one_of(st.none(), st.integers(min_value=0, max_value=10000))

_optional_bool = st.one_of(st.none(), st.booleans())

_sort_direction = st.one_of(st.none(), st.sampled_from(["Ascending", "Descending"]))

_join_operator = st.one_of(
    st.none(), st.sampled_from(["=", "<>", "<", ">", "<=", ">="])
)

_join_type = st.one_of(
    st.none(), st.sampled_from(["Inner", "LeftOuter", "RightOuter", "FullOuter"])
)

_filter_type = st.one_of(st.none(), st.sampled_from(["AND", "OR", "Condition"]))

_expression_type = st.one_of(
    st.none(), st.sampled_from(["Column", "Function", "Literal", "Operator"])
)


# ---------------------------------------------------------------------------
# Composite strategies for sub-collections
# ---------------------------------------------------------------------------


@st.composite
def input_table_data(draw):
    """Generate data for an InputTable and expected result."""
    data = {
        "ID": draw(_id_str),
        "InputTableName": draw(_optional_str),
        "IncludeSchema": draw(_optional_bool),
        "Schema": draw(_optional_str),
        "Alias": draw(_optional_str),
        "Options": draw(_optional_str),
        "Expanded": draw(_optional_bool),
        "DataID": draw(_optional_str),
        "OriginalServer": draw(_optional_str),
        "OriginalLibrary": draw(_optional_str),
        "OriginalMember": draw(_optional_str),
        "OriginalEngine": draw(_optional_str),
    }
    return data


@st.composite
def result_item_data(draw):
    """Generate data for a ResultItem and expected result."""
    data = {
        "ResultID": draw(_optional_str),
        "Alias": draw(_optional_str),
        "TableID": draw(_optional_str),
        "Format": draw(_optional_str),
        "Length": draw(_optional_int),
        "Label": draw(_optional_str),
        "LabelModified": draw(_optional_bool),
        "BaseColumnName": draw(_optional_str),
        "CalcID": draw(_optional_str),
    }
    return data


@st.composite
def expression_data(draw, max_depth=2):
    """Generate data for a recursive Expression tree."""
    data = {
        "ExpressionType": draw(_expression_type),
        "ExpressionText": draw(_optional_str),
    }
    if max_depth > 0:
        n_sub = draw(st.integers(min_value=0, max_value=2))
        data["sub_expressions"] = [
            draw(expression_data(max_depth=max_depth - 1)) for _ in range(n_sub)
        ]
    else:
        data["sub_expressions"] = []
    return data


@st.composite
def calculation_data(draw):
    """Generate data for a Calculation with optional Expression."""
    has_expression = draw(st.booleans())
    data = {
        "ID": draw(_id_str),
        "Alias": draw(_optional_str),
        "Format": draw(_optional_str),
        "Label": draw(_optional_str),
        "Length": draw(_optional_int),
        "IsAggregate": draw(_optional_bool),
        "IsReplacement": draw(_optional_bool),
        "ColumnName": draw(_optional_str),
        "expression": draw(expression_data()) if has_expression else None,
    }
    return data


@st.composite
def join_item_data(draw):
    """Generate data for a JoinItem."""
    data = {
        "LeftTableID": draw(_optional_str),
        "LeftColumnName": draw(_optional_str),
        "RightTableID": draw(_optional_str),
        "RightColumnName": draw(_optional_str),
        "JoinOperator": draw(_join_operator),
        "JoinType": draw(_join_type),
        "JoinFilter": draw(_optional_str),
    }
    return data


@st.composite
def filter_node_data(draw, max_depth=2):
    """Generate data for a hierarchical FilterNode."""
    data = {
        "FilterType": draw(_filter_type),
        "TableID": draw(_optional_str),
        "ColumnName": draw(_optional_str),
        "Operator": draw(_join_operator),
        "Value": draw(_optional_str),
    }
    if max_depth > 0:
        n_children = draw(st.integers(min_value=0, max_value=2))
        data["children"] = [
            draw(filter_node_data(max_depth=max_depth - 1)) for _ in range(n_children)
        ]
    else:
        data["children"] = []
    return data


@st.composite
def order_item_data(draw):
    """Generate data for an OrderItem."""
    data = {
        "TableID": draw(_optional_str),
        "ColumnName": draw(_optional_str),
        "SortDirection": draw(_sort_direction),
    }
    return data


@st.composite
def group_item_data(draw):
    """Generate data for a GroupItem."""
    data = {
        "TableID": draw(_optional_str),
        "ColumnName": draw(_optional_str),
    }
    return data


@st.composite
def query_builder_position_data(draw):
    """Generate data for a QueryBuilderTablePosition."""
    data = {
        "TableID": draw(_optional_str),
        "X": draw(_optional_int),
        "Y": draw(_optional_int),
        "Width": draw(_optional_int),
        "Height": draw(_optional_int),
    }
    return data


@st.composite
def scalar_settings_data(draw):
    """Generate scalar settings for QueryModel."""
    data = {
        "UseExplicitAndExecute": draw(_optional_bool),
        "KeepResultsInDatabaseIfPossible": draw(_optional_bool),
        "InObs": draw(_optional_int),
        "OutObs": draw(_optional_int),
        "OutputLibrary": draw(_optional_str),
        "OutputMember": draw(_optional_str),
        "OutputType": draw(_optional_str),
        "Server": draw(_optional_str),
        "AllowDuplicates": draw(_optional_bool),
        "OutputLabel": draw(_optional_str),
        "OutputOptions": draw(_optional_str),
        "Title": draw(_optional_str),
        "Footnote": draw(_optional_str),
        "GroupingStyle": draw(_optional_str),
        "PassthroughEnabled": draw(_optional_bool),
        "PassthroughServer": draw(_optional_str),
        "PassthroughLibrary": draw(_optional_str),
        "PassthroughMember": draw(_optional_str),
        "DisplayVarsSortOrder": draw(_optional_str),
        "UseLabelsForVarNames": draw(_optional_bool),
    }
    return data


@st.composite
def full_query_data(draw):
    """Generate a complete query element with random sub-collections."""
    scalars = draw(scalar_settings_data())

    # Random counts for each sub-collection (some may be 0 = absent)
    n_input_tables = draw(st.integers(min_value=0, max_value=5))
    n_result_items = draw(st.integers(min_value=0, max_value=5))
    n_calculations = draw(st.integers(min_value=0, max_value=3))
    n_join_items = draw(st.integers(min_value=0, max_value=3))
    n_where_filters = draw(st.integers(min_value=0, max_value=3))
    n_having_filters = draw(st.integers(min_value=0, max_value=3))
    n_order_items = draw(st.integers(min_value=0, max_value=3))
    n_group_items = draw(st.integers(min_value=0, max_value=3))
    n_builder_positions = draw(st.integers(min_value=0, max_value=3))

    input_tables = [draw(input_table_data()) for _ in range(n_input_tables)]
    result_items = [draw(result_item_data()) for _ in range(n_result_items)]
    calculations = [draw(calculation_data()) for _ in range(n_calculations)]
    join_items = [draw(join_item_data()) for _ in range(n_join_items)]
    where_filters = [draw(filter_node_data()) for _ in range(n_where_filters)]
    having_filters = [draw(filter_node_data()) for _ in range(n_having_filters)]
    order_items = [draw(order_item_data()) for _ in range(n_order_items)]
    group_items = [draw(group_item_data()) for _ in range(n_group_items)]
    builder_positions = [
        draw(query_builder_position_data()) for _ in range(n_builder_positions)
    ]

    return {
        "scalars": scalars,
        "input_tables": input_tables,
        "result_items": result_items,
        "calculations": calculations,
        "join_items": join_items,
        "where_filters": where_filters,
        "having_filters": having_filters,
        "order_items": order_items,
        "group_items": group_items,
        "builder_positions": builder_positions,
    }


# ---------------------------------------------------------------------------
# XML Building Helpers
# ---------------------------------------------------------------------------


def _set_attr(elem: ET.Element, attr_name: str, value) -> None:
    """Set an attribute on an element if value is not None."""
    if value is not None:
        if isinstance(value, bool):
            elem.set(attr_name, str(value).lower())
        else:
            elem.set(attr_name, str(value))


def _add_child_text(parent: ET.Element, tag: str, value) -> None:
    """Add a child element with text content if value is not None."""
    if value is not None:
        child = ET.SubElement(parent, tag)
        if isinstance(value, bool):
            child.text = str(value).lower()
        else:
            child.text = str(value)


def _build_expression_xml(
    parent: ET.Element, expr_data: dict, tag: str = "Expression"
) -> None:
    """Build an Expression XML element recursively.

    The top-level expression uses the "Expression" tag, but nested
    sub-expressions use the "SubExpression" tag (matching parser expectations).
    """
    expr_elem = ET.SubElement(parent, tag)
    _set_attr(expr_elem, "ExpressionType", expr_data.get("ExpressionType"))
    _set_attr(expr_elem, "ExpressionText", expr_data.get("ExpressionText"))
    for sub_expr in expr_data.get("sub_expressions", []):
        _build_expression_xml(expr_elem, sub_expr, tag="SubExpression")


def _build_filter_node_xml(parent: ET.Element, filter_data: dict) -> None:
    """Build a FilterNode XML element recursively."""
    node_elem = ET.SubElement(parent, "FilterNode")
    _set_attr(node_elem, "FilterType", filter_data.get("FilterType"))
    _set_attr(node_elem, "TableID", filter_data.get("TableID"))
    _set_attr(node_elem, "ColumnName", filter_data.get("ColumnName"))
    _set_attr(node_elem, "Operator", filter_data.get("Operator"))
    _set_attr(node_elem, "Value", filter_data.get("Value"))
    for child in filter_data.get("children", []):
        _build_filter_node_xml(node_elem, child)


def build_query_element_xml(query_data: dict) -> ET.Element:
    """Build a full Query <Element> XML node from generated data.

    Creates the structure:
    <Element Type="SAS.EG.ProjectElements.Query" ID="...">
        <QueryModel>
            <scalar settings as child elements>
            <InputTables><InputTable .../> ...</InputTables>
            <ResultItems><ResultItem .../> ...</ResultItems>
            <Calculations><Calculation ...><Expression .../></Calculation> ...</Calculations>
            <JoinItems><JoinItem .../> ...</JoinItems>
            <WhereFilters><FilterNode .../> ...</WhereFilters>
            <HavingFilters><FilterNode .../> ...</HavingFilters>
            <OrderItems><OrderItem .../> ...</OrderItems>
            <GroupItems><GroupItem .../> ...</GroupItems>
            <QueryBuilderSettings><TablePosition .../> ...</QueryBuilderSettings>
        </QueryModel>
    </Element>
    """
    element = ET.Element("Element")
    element.set("Type", "SAS.EG.ProjectElements.Query")
    element.set("ID", "TestQuery001")

    query_model = ET.SubElement(element, "QueryModel")

    # Add scalar settings as child text elements
    scalars = query_data["scalars"]
    _add_child_text(
        query_model, "UseExplicitAndExecute", scalars.get("UseExplicitAndExecute")
    )
    _add_child_text(
        query_model,
        "KeepResultsInDatabaseIfPossible",
        scalars.get("KeepResultsInDatabaseIfPossible"),
    )
    _add_child_text(query_model, "InObs", scalars.get("InObs"))
    _add_child_text(query_model, "OutObs", scalars.get("OutObs"))
    _add_child_text(query_model, "OutputLibrary", scalars.get("OutputLibrary"))
    _add_child_text(query_model, "OutputMember", scalars.get("OutputMember"))
    _add_child_text(query_model, "OutputType", scalars.get("OutputType"))
    _add_child_text(query_model, "Server", scalars.get("Server"))
    _add_child_text(query_model, "AllowDuplicates", scalars.get("AllowDuplicates"))
    _add_child_text(query_model, "OutputLabel", scalars.get("OutputLabel"))
    _add_child_text(query_model, "OutputOptions", scalars.get("OutputOptions"))
    _add_child_text(query_model, "Title", scalars.get("Title"))
    _add_child_text(query_model, "Footnote", scalars.get("Footnote"))
    _add_child_text(query_model, "GroupingStyle", scalars.get("GroupingStyle"))
    _add_child_text(
        query_model, "PassthroughEnabled", scalars.get("PassthroughEnabled")
    )
    _add_child_text(query_model, "PassthroughServer", scalars.get("PassthroughServer"))
    _add_child_text(
        query_model, "PassthroughLibrary", scalars.get("PassthroughLibrary")
    )
    _add_child_text(query_model, "PassthroughMember", scalars.get("PassthroughMember"))
    _add_child_text(
        query_model, "DisplayVarsSortOrder", scalars.get("DisplayVarsSortOrder")
    )
    _add_child_text(
        query_model, "UseLabelsForVarNames", scalars.get("UseLabelsForVarNames")
    )

    # InputTables
    if query_data["input_tables"]:
        container = ET.SubElement(query_model, "InputTables")
        for tbl in query_data["input_tables"]:
            item = ET.SubElement(container, "InputTable")
            _set_attr(item, "ID", tbl.get("ID"))
            _set_attr(item, "InputTableName", tbl.get("InputTableName"))
            _set_attr(item, "IncludeSchema", tbl.get("IncludeSchema"))
            _set_attr(item, "Schema", tbl.get("Schema"))
            _set_attr(item, "Alias", tbl.get("Alias"))
            _set_attr(item, "Options", tbl.get("Options"))
            _set_attr(item, "Expanded", tbl.get("Expanded"))
            _set_attr(item, "DataID", tbl.get("DataID"))
            _set_attr(item, "OriginalServer", tbl.get("OriginalServer"))
            _set_attr(item, "OriginalLibrary", tbl.get("OriginalLibrary"))
            _set_attr(item, "OriginalMember", tbl.get("OriginalMember"))
            _set_attr(item, "OriginalEngine", tbl.get("OriginalEngine"))

    # ResultItems
    if query_data["result_items"]:
        container = ET.SubElement(query_model, "ResultItems")
        for ri in query_data["result_items"]:
            item = ET.SubElement(container, "ResultItem")
            _set_attr(item, "ResultID", ri.get("ResultID"))
            _set_attr(item, "Alias", ri.get("Alias"))
            _set_attr(item, "TableID", ri.get("TableID"))
            _set_attr(item, "Format", ri.get("Format"))
            _set_attr(item, "Length", ri.get("Length"))
            _set_attr(item, "Label", ri.get("Label"))
            _set_attr(item, "LabelModified", ri.get("LabelModified"))
            _set_attr(item, "BaseColumnName", ri.get("BaseColumnName"))
            _set_attr(item, "CalcID", ri.get("CalcID"))

    # Calculations
    if query_data["calculations"]:
        container = ET.SubElement(query_model, "Calculations")
        for calc in query_data["calculations"]:
            item = ET.SubElement(container, "Calculation")
            _set_attr(item, "ID", calc.get("ID"))
            _set_attr(item, "Alias", calc.get("Alias"))
            _set_attr(item, "Format", calc.get("Format"))
            _set_attr(item, "Label", calc.get("Label"))
            _set_attr(item, "Length", calc.get("Length"))
            _set_attr(item, "IsAggregate", calc.get("IsAggregate"))
            _set_attr(item, "IsReplacement", calc.get("IsReplacement"))
            _set_attr(item, "ColumnName", calc.get("ColumnName"))
            if calc.get("expression") is not None:
                _build_expression_xml(item, calc["expression"])

    # JoinItems
    if query_data["join_items"]:
        container = ET.SubElement(query_model, "JoinItems")
        for ji in query_data["join_items"]:
            item = ET.SubElement(container, "JoinItem")
            _set_attr(item, "LeftTableID", ji.get("LeftTableID"))
            _set_attr(item, "LeftColumnName", ji.get("LeftColumnName"))
            _set_attr(item, "RightTableID", ji.get("RightTableID"))
            _set_attr(item, "RightColumnName", ji.get("RightColumnName"))
            _set_attr(item, "JoinOperator", ji.get("JoinOperator"))
            _set_attr(item, "JoinType", ji.get("JoinType"))
            _set_attr(item, "JoinFilter", ji.get("JoinFilter"))

    # WhereFilters
    if query_data["where_filters"]:
        container = ET.SubElement(query_model, "WhereFilters")
        for wf in query_data["where_filters"]:
            _build_filter_node_xml(container, wf)

    # HavingFilters
    if query_data["having_filters"]:
        container = ET.SubElement(query_model, "HavingFilters")
        for hf in query_data["having_filters"]:
            _build_filter_node_xml(container, hf)

    # OrderItems
    if query_data["order_items"]:
        container = ET.SubElement(query_model, "OrderItems")
        for oi in query_data["order_items"]:
            item = ET.SubElement(container, "OrderItem")
            _set_attr(item, "TableID", oi.get("TableID"))
            _set_attr(item, "ColumnName", oi.get("ColumnName"))
            _set_attr(item, "SortDirection", oi.get("SortDirection"))

    # GroupItems
    if query_data["group_items"]:
        container = ET.SubElement(query_model, "GroupItems")
        for gi in query_data["group_items"]:
            item = ET.SubElement(container, "GroupItem")
            _set_attr(item, "TableID", gi.get("TableID"))
            _set_attr(item, "ColumnName", gi.get("ColumnName"))

    # QueryBuilderSettings
    if query_data["builder_positions"]:
        container = ET.SubElement(query_model, "QueryBuilderSettings")
        for pos in query_data["builder_positions"]:
            item = ET.SubElement(container, "TablePosition")
            _set_attr(item, "TableID", pos.get("TableID"))
            _set_attr(item, "X", pos.get("X"))
            _set_attr(item, "Y", pos.get("Y"))
            _set_attr(item, "Width", pos.get("Width"))
            _set_attr(item, "Height", pos.get("Height"))

    return element


# ---------------------------------------------------------------------------
# Assertion Helpers
# ---------------------------------------------------------------------------


def _assert_expression_matches(parsed: Expression, expected: dict) -> None:
    """Recursively verify an Expression tree matches expected data."""
    assert parsed.expression_type == expected.get("ExpressionType")
    assert parsed.expression_text == expected.get("ExpressionText")

    expected_subs = expected.get("sub_expressions", [])
    assert len(parsed.sub_expressions) == len(expected_subs), (
        f"Expression sub_expression count mismatch: "
        f"got {len(parsed.sub_expressions)}, expected {len(expected_subs)}"
    )
    for i, (p_sub, e_sub) in enumerate(zip(parsed.sub_expressions, expected_subs)):
        _assert_expression_matches(p_sub, e_sub)


def _assert_filter_node_matches(parsed: FilterNode, expected: dict) -> None:
    """Recursively verify a FilterNode tree matches expected data."""
    assert parsed.filter_type == expected.get("FilterType")
    assert parsed.table_id == expected.get("TableID")
    assert parsed.column_name == expected.get("ColumnName")
    assert parsed.operator == expected.get("Operator")
    assert parsed.value == expected.get("Value")

    expected_children = expected.get("children", [])
    assert len(parsed.children) == len(expected_children), (
        f"FilterNode children count mismatch: "
        f"got {len(parsed.children)}, expected {len(expected_children)}"
    )
    for i, (p_child, e_child) in enumerate(zip(parsed.children, expected_children)):
        _assert_filter_node_matches(p_child, e_child)


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------


class TestQueryModelExtractionCompleteness:
    """**Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9, 8.10, 8.12**"""

    @given(data=full_query_data())
    @settings(max_examples=200)
    def test_p1_input_tables_extracted_with_correct_fields(self, data):
        """P1: All present InputTables are extracted with correct field values.

        Every InputTable in the XML must appear in the parsed result with
        all attribute values matching.
        """
        element_xml = build_query_element_xml(data)
        _, query_model = parse_query(element_xml)

        expected = data["input_tables"]
        assert len(query_model.input_tables) == len(expected)

        for i, (parsed, exp) in enumerate(zip(query_model.input_tables, expected)):
            assert parsed.id == exp.get("ID"), f"InputTable {i}: id mismatch"
            assert parsed.input_table_name == exp.get("InputTableName"), (
                f"InputTable {i}: name mismatch"
            )
            assert parsed.include_schema == exp.get("IncludeSchema"), (
                f"InputTable {i}: include_schema mismatch"
            )
            assert parsed.schema == exp.get("Schema"), (
                f"InputTable {i}: schema mismatch"
            )
            assert parsed.alias == exp.get("Alias"), f"InputTable {i}: alias mismatch"
            assert parsed.options == exp.get("Options"), (
                f"InputTable {i}: options mismatch"
            )
            assert parsed.expanded == exp.get("Expanded"), (
                f"InputTable {i}: expanded mismatch"
            )
            assert parsed.data_id == exp.get("DataID"), (
                f"InputTable {i}: data_id mismatch"
            )
            assert parsed.original_server == exp.get("OriginalServer"), (
                f"InputTable {i}: original_server mismatch"
            )
            assert parsed.original_library == exp.get("OriginalLibrary"), (
                f"InputTable {i}: original_library mismatch"
            )
            assert parsed.original_member == exp.get("OriginalMember"), (
                f"InputTable {i}: original_member mismatch"
            )
            assert parsed.original_engine == exp.get("OriginalEngine"), (
                f"InputTable {i}: original_engine mismatch"
            )

    @given(data=full_query_data())
    @settings(max_examples=200)
    def test_p2_result_items_extracted_with_correct_fields(self, data):
        """P2: All present ResultItems are extracted with correct field values.

        Every ResultItem in the XML must appear in the parsed result with
        all attribute values matching.
        """
        element_xml = build_query_element_xml(data)
        _, query_model = parse_query(element_xml)

        expected = data["result_items"]
        assert len(query_model.result_items) == len(expected)

        for i, (parsed, exp) in enumerate(zip(query_model.result_items, expected)):
            assert parsed.result_id == exp.get("ResultID"), (
                f"ResultItem {i}: result_id mismatch"
            )
            assert parsed.alias == exp.get("Alias"), f"ResultItem {i}: alias mismatch"
            assert parsed.table_id == exp.get("TableID"), (
                f"ResultItem {i}: table_id mismatch"
            )
            assert parsed.format == exp.get("Format"), (
                f"ResultItem {i}: format mismatch"
            )
            assert parsed.length == exp.get("Length"), (
                f"ResultItem {i}: length mismatch"
            )
            assert parsed.label == exp.get("Label"), f"ResultItem {i}: label mismatch"
            assert parsed.label_modified == exp.get("LabelModified"), (
                f"ResultItem {i}: label_modified mismatch"
            )
            assert parsed.base_column_name == exp.get("BaseColumnName"), (
                f"ResultItem {i}: base_column_name mismatch"
            )
            assert parsed.calc_id == exp.get("CalcID"), (
                f"ResultItem {i}: calc_id mismatch"
            )

    @given(data=full_query_data())
    @settings(max_examples=200)
    def test_p3_calculations_with_expressions_extracted(self, data):
        """P3: All present Calculations (with Expression trees) are extracted correctly.

        Every Calculation must have correct attributes and its Expression tree
        (if present) must be structurally equivalent.
        """
        element_xml = build_query_element_xml(data)
        _, query_model = parse_query(element_xml)

        expected = data["calculations"]
        assert len(query_model.calculations) == len(expected)

        for i, (parsed, exp) in enumerate(zip(query_model.calculations, expected)):
            assert parsed.id == exp.get("ID"), f"Calculation {i}: id mismatch"
            assert parsed.alias == exp.get("Alias"), f"Calculation {i}: alias mismatch"
            assert parsed.format == exp.get("Format"), (
                f"Calculation {i}: format mismatch"
            )
            assert parsed.label == exp.get("Label"), f"Calculation {i}: label mismatch"
            assert parsed.length == exp.get("Length"), (
                f"Calculation {i}: length mismatch"
            )
            assert parsed.is_aggregate == exp.get("IsAggregate"), (
                f"Calculation {i}: is_aggregate mismatch"
            )
            assert parsed.is_replacement == exp.get("IsReplacement"), (
                f"Calculation {i}: is_replacement mismatch"
            )
            assert parsed.column_name == exp.get("ColumnName"), (
                f"Calculation {i}: column_name mismatch"
            )

            if exp.get("expression") is not None:
                assert parsed.expression is not None, (
                    f"Calculation {i}: expression should not be None"
                )
                _assert_expression_matches(parsed.expression, exp["expression"])
            else:
                assert parsed.expression is None, (
                    f"Calculation {i}: expression should be None"
                )

    @given(data=full_query_data())
    @settings(max_examples=200)
    def test_p4_join_items_extracted_with_correct_fields(self, data):
        """P4: All present JoinItems are extracted with correct field values."""
        element_xml = build_query_element_xml(data)
        _, query_model = parse_query(element_xml)

        expected = data["join_items"]
        assert len(query_model.join_items) == len(expected)

        for i, (parsed, exp) in enumerate(zip(query_model.join_items, expected)):
            assert parsed.left_table_id == exp.get("LeftTableID"), (
                f"JoinItem {i}: left_table_id mismatch"
            )
            assert parsed.left_column_name == exp.get("LeftColumnName"), (
                f"JoinItem {i}: left_column_name mismatch"
            )
            assert parsed.right_table_id == exp.get("RightTableID"), (
                f"JoinItem {i}: right_table_id mismatch"
            )
            assert parsed.right_column_name == exp.get("RightColumnName"), (
                f"JoinItem {i}: right_column_name mismatch"
            )
            assert parsed.join_operator == exp.get("JoinOperator"), (
                f"JoinItem {i}: join_operator mismatch"
            )
            assert parsed.join_type == exp.get("JoinType"), (
                f"JoinItem {i}: join_type mismatch"
            )
            assert parsed.join_filter == exp.get("JoinFilter"), (
                f"JoinItem {i}: join_filter mismatch"
            )

    @given(data=full_query_data())
    @settings(max_examples=200)
    def test_p5_filter_nodes_extracted_with_nesting(self, data):
        """P5: All present FilterNodes in WhereFilters/HavingFilters are extracted
        with correct hierarchical nesting.
        """
        element_xml = build_query_element_xml(data)
        _, query_model = parse_query(element_xml)

        # WhereFilters
        expected_where = data["where_filters"]
        assert len(query_model.where_filters) == len(expected_where), (
            f"WhereFilters count mismatch: got {len(query_model.where_filters)}, "
            f"expected {len(expected_where)}"
        )
        for i, (parsed, exp) in enumerate(
            zip(query_model.where_filters, expected_where)
        ):
            _assert_filter_node_matches(parsed, exp)

        # HavingFilters
        expected_having = data["having_filters"]
        assert len(query_model.having_filters) == len(expected_having), (
            f"HavingFilters count mismatch: got {len(query_model.having_filters)}, "
            f"expected {len(expected_having)}"
        )
        for i, (parsed, exp) in enumerate(
            zip(query_model.having_filters, expected_having)
        ):
            _assert_filter_node_matches(parsed, exp)

    @given(data=full_query_data())
    @settings(max_examples=200)
    def test_p6_order_and_group_items_extracted(self, data):
        """P6: All present OrderItems and GroupItems are extracted correctly."""
        element_xml = build_query_element_xml(data)
        _, query_model = parse_query(element_xml)

        # OrderItems
        expected_orders = data["order_items"]
        assert len(query_model.order_items) == len(expected_orders)
        for i, (parsed, exp) in enumerate(
            zip(query_model.order_items, expected_orders)
        ):
            assert parsed.table_id == exp.get("TableID"), (
                f"OrderItem {i}: table_id mismatch"
            )
            assert parsed.column_name == exp.get("ColumnName"), (
                f"OrderItem {i}: column_name mismatch"
            )
            assert parsed.sort_direction == exp.get("SortDirection"), (
                f"OrderItem {i}: sort_direction mismatch"
            )

        # GroupItems
        expected_groups = data["group_items"]
        assert len(query_model.group_items) == len(expected_groups)
        for i, (parsed, exp) in enumerate(
            zip(query_model.group_items, expected_groups)
        ):
            assert parsed.table_id == exp.get("TableID"), (
                f"GroupItem {i}: table_id mismatch"
            )
            assert parsed.column_name == exp.get("ColumnName"), (
                f"GroupItem {i}: column_name mismatch"
            )

    @given(data=full_query_data())
    @settings(max_examples=200)
    def test_p7_absent_collections_are_empty_lists(self, data):
        """P7: Absent collections are represented as empty lists.

        When a sub-collection has zero items (container element not written),
        the parsed QueryModel must have an empty list for that field.
        """
        element_xml = build_query_element_xml(data)
        _, query_model = parse_query(element_xml)

        if not data["input_tables"]:
            assert query_model.input_tables == [], "input_tables should be empty list"
        if not data["result_items"]:
            assert query_model.result_items == [], "result_items should be empty list"
        if not data["calculations"]:
            assert query_model.calculations == [], "calculations should be empty list"
        if not data["join_items"]:
            assert query_model.join_items == [], "join_items should be empty list"
        if not data["where_filters"]:
            assert query_model.where_filters == [], "where_filters should be empty list"
        if not data["having_filters"]:
            assert query_model.having_filters == [], (
                "having_filters should be empty list"
            )
        if not data["order_items"]:
            assert query_model.order_items == [], "order_items should be empty list"
        if not data["group_items"]:
            assert query_model.group_items == [], "group_items should be empty list"
        if not data["builder_positions"]:
            assert query_model.query_builder_settings == [], (
                "query_builder_settings should be empty list"
            )

    @given(data=full_query_data())
    @settings(max_examples=200)
    def test_p8_scalar_settings_match_input(self, data):
        """P8: Scalar settings match input or are None when absent.

        Each scalar field in QueryModel must match what was generated,
        or be None if the corresponding value was None (element not written).
        """
        element_xml = build_query_element_xml(data)
        _, query_model = parse_query(element_xml)

        scalars = data["scalars"]

        assert query_model.use_explicit_and_execute == scalars["UseExplicitAndExecute"]
        assert (
            query_model.keep_results_in_database_if_possible
            == scalars["KeepResultsInDatabaseIfPossible"]
        )
        assert query_model.in_obs == scalars["InObs"]
        assert query_model.out_obs == scalars["OutObs"]
        assert query_model.output_library == scalars["OutputLibrary"]
        assert query_model.output_member == scalars["OutputMember"]
        assert query_model.output_type == scalars["OutputType"]
        assert query_model.server == scalars["Server"]
        assert query_model.allow_duplicates == scalars["AllowDuplicates"]
        assert query_model.output_label == scalars["OutputLabel"]
        assert query_model.output_options == scalars["OutputOptions"]
        assert query_model.title == scalars["Title"]
        assert query_model.footnote == scalars["Footnote"]
        assert query_model.grouping_style == scalars["GroupingStyle"]
        assert query_model.passthrough_enabled == scalars["PassthroughEnabled"]
        assert query_model.passthrough_server == scalars["PassthroughServer"]
        assert query_model.passthrough_library == scalars["PassthroughLibrary"]
        assert query_model.passthrough_member == scalars["PassthroughMember"]
        assert query_model.display_vars_sort_order == scalars["DisplayVarsSortOrder"]
        assert query_model.use_labels_for_var_names == scalars["UseLabelsForVarNames"]

    @given(data=full_query_data())
    @settings(max_examples=200)
    def test_p9_item_counts_match_generated(self, data):
        """P9: Item counts match what was generated.

        The total number of items in each parsed collection must equal
        the number of items generated into the XML.
        """
        element_xml = build_query_element_xml(data)
        _, query_model = parse_query(element_xml)

        assert len(query_model.input_tables) == len(data["input_tables"])
        assert len(query_model.result_items) == len(data["result_items"])
        assert len(query_model.calculations) == len(data["calculations"])
        assert len(query_model.join_items) == len(data["join_items"])
        assert len(query_model.where_filters) == len(data["where_filters"])
        assert len(query_model.having_filters) == len(data["having_filters"])
        assert len(query_model.order_items) == len(data["order_items"])
        assert len(query_model.group_items) == len(data["group_items"])
        assert len(query_model.query_builder_settings) == len(data["builder_positions"])
