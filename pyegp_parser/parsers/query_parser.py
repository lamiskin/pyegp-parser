"""Parser for Query elements from project.xml.

Provides functions to parse SubmitableElement sections and full QueryModel
definitions including InputTables, ResultItems, Calculations (with nested
Expression trees), JoinItems, WhereFilters/HavingFilters (hierarchical
FilterNode trees), OrderItems, GroupItems, and QueryBuilderSettings.
"""

import xml.etree.ElementTree as ET
from typing import Any

from ..models.query import (
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
from ..models.tasks import SubmitableElement


def parse_query(element_node: ET.Element) -> tuple[SubmitableElement, QueryModel]:
    """Parse a Query element's SubmitableElement and QueryModel.

    Args:
        element_node: The <Element> XML node for a Query element.

    Returns:
        Tuple of (SubmitableElement, QueryModel).

    Raises:
        ValueError: If the QueryModel section is missing from the element.
    """
    submitable = parse_submitable_element(element_node)

    # Look for QueryModel directly on the element, or nested inside a <Query> wrapper
    query_model_node = element_node.find("QueryModel")
    if query_model_node is None:
        query_wrapper = element_node.find("Query")
        if query_wrapper is not None:
            query_model_node = query_wrapper.find("QueryModel")

    if query_model_node is None:
        element_id = element_node.get("ID", "unknown")
        raise ValueError(
            f"Query element '{element_id}' is missing required QueryModel section"
        )

    query_model = _parse_query_model(query_model_node)
    return submitable, query_model


def parse_submitable_element(element_node: ET.Element) -> SubmitableElement:
    """Parse the SubmitableElement section from an element node.

    This is reusable across multiple task types (Query, ImportTask,
    CodeTask, EGTask, ExportTask, AppendTask) that share this section.

    Args:
        element_node: The parent <Element> XML node containing a
            <SubmitableElement> child.

    Returns:
        SubmitableElement with all available fields populated.
        Returns a default SubmitableElement if the section is absent.
    """
    sub_elem = element_node.find("SubmitableElement")
    if sub_elem is None:
        return SubmitableElement()

    use_global_options = _get_child_bool(sub_elem, "UseGlobalOptions")
    server = _get_child_text(sub_elem, "Server")
    has_error = _get_child_bool(sub_elem, "HASERROR")
    has_warning = _get_child_bool(sub_elem, "HASWARNING")
    execution_time_span = _get_child_text(sub_elem, "ExecutionTimeSpan")

    # Parse ODS style overrides
    ods_style_overrides = _parse_ods_style_overrides(sub_elem)

    # Parse ExpectedOutputDataList
    expected_output_data_list = _parse_expected_output_data_list(sub_elem)

    # Parse Parameters
    parameters = _parse_parameters(sub_elem)

    # Parse JobRecipe (preserve as raw dict structure)
    job_recipe = _parse_job_recipe(sub_elem)

    return SubmitableElement(
        use_global_options=use_global_options,
        server=server,
        has_error=has_error,
        has_warning=has_warning,
        ods_style_overrides=ods_style_overrides,
        expected_output_data_list=expected_output_data_list,
        parameters=parameters,
        execution_time_span=execution_time_span,
        job_recipe=job_recipe,
    )


def _parse_query_model(query_model_node: ET.Element) -> QueryModel:
    """Parse the full QueryModel element into a QueryModel dataclass."""
    # Parse scalar settings
    model = QueryModel(
        use_explicit_and_execute=_get_child_bool(
            query_model_node, "UseExplicitAndExecute"
        ),
        keep_results_in_database_if_possible=_get_child_bool(
            query_model_node, "KeepResultsInDatabaseIfPossible"
        ),
        in_obs=_get_child_int(query_model_node, "InObs"),
        out_obs=_get_child_int(query_model_node, "OutObs"),
        output_library=_get_child_text(query_model_node, "OutputLibrary"),
        output_member=_get_child_text(query_model_node, "OutputMember"),
        output_type=_get_child_text(query_model_node, "OutputType"),
        server=_get_child_text(query_model_node, "Server"),
        allow_duplicates=_get_child_bool(query_model_node, "AllowDuplicates"),
        output_label=_get_child_text(query_model_node, "OutputLabel"),
        output_options=_get_child_text(query_model_node, "OutputOptions"),
        title=_get_child_text(query_model_node, "Title"),
        footnote=_get_child_text(query_model_node, "Footnote"),
        grouping_style=_get_child_text(query_model_node, "GroupingStyle"),
        passthrough_enabled=_get_child_bool(query_model_node, "PassthroughEnabled"),
        passthrough_server=_get_child_text(query_model_node, "PassthroughServer"),
        passthrough_library=_get_child_text(query_model_node, "PassthroughLibrary"),
        passthrough_member=_get_child_text(query_model_node, "PassthroughMember"),
        display_vars_sort_order=_get_child_text(
            query_model_node, "DisplayVarsSortOrder"
        ),
        use_labels_for_var_names=_get_child_bool(
            query_model_node, "UseLabelsForVarNames"
        ),
    )

    # Parse collections
    model.input_tables = _parse_input_tables(query_model_node)
    model.result_items = _parse_result_items(query_model_node)
    model.calculations = _parse_calculations(query_model_node)
    model.join_items = _parse_join_items(query_model_node)
    model.where_filters = _parse_filter_nodes(query_model_node, "WhereFilters")
    model.having_filters = _parse_filter_nodes(query_model_node, "HavingFilters")
    model.order_items = _parse_order_items(query_model_node)
    model.group_items = _parse_group_items(query_model_node)
    model.query_builder_settings = _parse_query_builder_settings(query_model_node)

    return model


# --- Collection parsers ---


def _parse_input_tables(query_model_node: ET.Element) -> list[InputTable]:
    """Parse InputTables collection from QueryModel."""
    container = query_model_node.find("InputTables")
    if container is None:
        return []

    tables: list[InputTable] = []
    for item in container.findall("InputTable"):
        tables.append(
            InputTable(
                id=item.get("ID"),
                input_table_name=item.get("InputTableName"),
                include_schema=_get_attr_bool(item, "IncludeSchema"),
                schema=item.get("Schema"),
                alias=item.get("Alias"),
                options=item.get("Options"),
                expanded=_get_attr_bool(item, "Expanded"),
                data_id=item.get("DataID"),
                original_server=item.get("OriginalServer"),
                original_library=item.get("OriginalLibrary"),
                original_member=item.get("OriginalMember"),
                original_engine=item.get("OriginalEngine"),
            )
        )
    return tables


def _parse_result_items(query_model_node: ET.Element) -> list[ResultItem]:
    """Parse ResultItems collection from QueryModel."""
    container = query_model_node.find("ResultItems")
    if container is None:
        return []

    items: list[ResultItem] = []
    for item in container.findall("ResultItem"):
        items.append(
            ResultItem(
                result_id=item.get("ResultID"),
                alias=item.get("Alias"),
                table_id=item.get("TableID"),
                format=item.get("Format"),
                length=_get_attr_int(item, "Length"),
                label=item.get("Label"),
                label_modified=_get_attr_bool(item, "LabelModified"),
                base_column_name=item.get("BaseColumnName"),
                calc_id=item.get("CalcID"),
            )
        )
    return items


def _parse_calculations(query_model_node: ET.Element) -> list[Calculation]:
    """Parse Calculations collection from QueryModel."""
    container = query_model_node.find("Calculations")
    if container is None:
        return []

    calcs: list[Calculation] = []
    for item in container.findall("Calculation"):
        expression = _parse_expression(item.find("Expression"))
        calcs.append(
            Calculation(
                id=item.get("ID"),
                alias=item.get("Alias"),
                format=item.get("Format"),
                label=item.get("Label"),
                length=_get_attr_int(item, "Length"),
                is_aggregate=_get_attr_bool(item, "IsAggregate"),
                is_replacement=_get_attr_bool(item, "IsReplacement"),
                column_name=item.get("ColumnName"),
                expression=expression,
            )
        )
    return calcs


def _parse_expression(expr_node: ET.Element | None) -> Expression | None:
    """Parse a recursive Expression tree.

    Expressions can have nested SubExpression children forming a tree.
    """
    if expr_node is None:
        return None

    sub_expressions: list[Expression] = []
    for sub_expr in expr_node.findall("SubExpression"):
        parsed_sub = _parse_expression(sub_expr)
        if parsed_sub is not None:
            sub_expressions.append(parsed_sub)

    return Expression(
        expression_type=expr_node.get("ExpressionType"),
        expression_text=expr_node.get("ExpressionText"),
        sub_expressions=sub_expressions,
    )


def _parse_join_items(query_model_node: ET.Element) -> list[JoinItem]:
    """Parse JoinItems collection from QueryModel."""
    container = query_model_node.find("JoinItems")
    if container is None:
        return []

    items: list[JoinItem] = []
    for item in container.findall("JoinItem"):
        items.append(
            JoinItem(
                left_table_id=item.get("LeftTableID"),
                left_column_name=item.get("LeftColumnName"),
                right_table_id=item.get("RightTableID"),
                right_column_name=item.get("RightColumnName"),
                join_operator=item.get("JoinOperator"),
                join_type=item.get("JoinType"),
                join_filter=item.get("JoinFilter"),
            )
        )
    return items


def _parse_filter_nodes(
    query_model_node: ET.Element, section_name: str
) -> list[FilterNode]:
    """Parse WhereFilters or HavingFilters into a list of FilterNode trees.

    Each top-level FilterNode within the section becomes a root in the list.
    FilterNodes can be hierarchically nested for compound expressions.
    """
    container = query_model_node.find(section_name)
    if container is None:
        return []

    nodes: list[FilterNode] = []
    for filter_elem in container.findall("FilterNode"):
        nodes.append(_parse_single_filter_node(filter_elem))
    return nodes


def _parse_single_filter_node(filter_elem: ET.Element) -> FilterNode:
    """Recursively parse a single FilterNode element."""
    children: list[FilterNode] = []
    for child_elem in filter_elem.findall("FilterNode"):
        children.append(_parse_single_filter_node(child_elem))

    return FilterNode(
        filter_type=filter_elem.get("FilterType"),
        table_id=filter_elem.get("TableID"),
        column_name=filter_elem.get("ColumnName"),
        operator=filter_elem.get("Operator"),
        value=filter_elem.get("Value"),
        children=children,
    )


def _parse_order_items(query_model_node: ET.Element) -> list[OrderItem]:
    """Parse OrderItems collection from QueryModel."""
    container = query_model_node.find("OrderItems")
    if container is None:
        return []

    items: list[OrderItem] = []
    for item in container.findall("OrderItem"):
        items.append(
            OrderItem(
                table_id=item.get("TableID"),
                column_name=item.get("ColumnName"),
                sort_direction=item.get("SortDirection"),
            )
        )
    return items


def _parse_group_items(query_model_node: ET.Element) -> list[GroupItem]:
    """Parse GroupItems collection from QueryModel."""
    container = query_model_node.find("GroupItems")
    if container is None:
        return []

    items: list[GroupItem] = []
    for item in container.findall("GroupItem"):
        items.append(
            GroupItem(
                table_id=item.get("TableID"),
                column_name=item.get("ColumnName"),
            )
        )
    return items


def _parse_query_builder_settings(
    query_model_node: ET.Element,
) -> list[QueryBuilderTablePosition]:
    """Parse QueryBuilderSettings table positions from QueryModel."""
    container = query_model_node.find("QueryBuilderSettings")
    if container is None:
        return []

    positions: list[QueryBuilderTablePosition] = []
    for item in container.findall("TablePosition"):
        positions.append(
            QueryBuilderTablePosition(
                table_id=item.get("TableID"),
                x=_get_attr_int(item, "X"),
                y=_get_attr_int(item, "Y"),
                width=_get_attr_int(item, "Width"),
                height=_get_attr_int(item, "Height"),
            )
        )
    return positions


# --- SubmitableElement helpers ---


def _parse_ods_style_overrides(sub_elem: ET.Element) -> dict | None:
    """Parse ODS style override elements from SubmitableElement.

    Collects all ODS-related child elements into a dictionary.
    Returns None if no ODS override elements are found.
    """
    ods_tags = [
        "ODSGraphicsEnabled",
        "ODSHTMLEnabled",
        "ODSHTMLStyle",
        "ODSListingEnabled",
        "ODSPDFEnabled",
        "ODSPDFStyle",
        "ODSRTFEnabled",
        "ODSRTFStyle",
        "ODSPowerPointEnabled",
        "ODSPowerPointStyle",
        "ODSExcelEnabled",
        "ODSExcelStyle",
    ]

    overrides: dict[str, str] = {}
    for tag in ods_tags:
        value = _get_child_text(sub_elem, tag)
        if value is not None:
            overrides[tag] = value

    return overrides if overrides else None


def _parse_expected_output_data_list(sub_elem: ET.Element) -> list[str]:
    """Parse ExpectedOutputDataList from SubmitableElement."""
    container = sub_elem.find("ExpectedOutputDataList")
    if container is None:
        return []

    items: list[str] = []
    for output_data in container.findall("OutputData"):
        if output_data.text and output_data.text.strip():
            items.append(output_data.text.strip())
    return items


def _parse_parameters(sub_elem: ET.Element) -> list[dict[str, str]]:
    """Parse Parameters collection from SubmitableElement.

    Each Parameter is stored as a dict with Name and Value keys.
    """
    container = sub_elem.find("Parameters")
    if container is None:
        return []

    params: list[dict[str, str]] = []
    for param in container.findall("Parameter"):
        name = param.get("Name")
        value = param.get("Value")
        if name is not None:
            params.append({"Name": name, "Value": value or ""})
    return params


def _parse_job_recipe(sub_elem: ET.Element) -> Any:
    """Parse JobRecipe section from SubmitableElement.

    Preserves the structure as a dictionary with relevant fields.
    Returns None if JobRecipe is absent.
    """
    job_recipe_elem = sub_elem.find("JobRecipe")
    if job_recipe_elem is None:
        return None

    recipe: dict[str, Any] = {}

    # Extract ODS results list
    ods_list_elem = job_recipe_elem.find("ODSResultsList")
    if ods_list_elem is not None:
        ods_items: list[dict[str, str]] = []
        for ods_item in ods_list_elem.findall("ODSResult"):
            ods_items.append(
                {
                    "ID": ods_item.get("ID", ""),
                    "Type": ods_item.get("Type", ""),
                }
            )
        recipe["ODSResultsList"] = ods_items

    # Extract any other attributes on the JobRecipe element
    for attr_name, attr_value in job_recipe_elem.attrib.items():
        recipe[attr_name] = attr_value

    return recipe if recipe else None


# --- Utility functions ---


def _get_child_text(parent: ET.Element, tag: str) -> str | None:
    """Get text content of a child element, returning None if absent or empty."""
    child = parent.find(tag)
    if child is None or child.text is None or child.text.strip() == "":
        return None
    return child.text.strip()


def _get_child_bool(parent: ET.Element, tag: str) -> bool | None:
    """Get boolean value from a child element's text content."""
    text = _get_child_text(parent, tag)
    if text is None:
        return None
    return text.lower() == "true"


def _get_child_int(parent: ET.Element, tag: str) -> int | None:
    """Get integer value from a child element's text content."""
    text = _get_child_text(parent, tag)
    if text is None:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _get_attr_bool(elem: ET.Element, attr: str) -> bool | None:
    """Get boolean value from an element's attribute."""
    value = elem.get(attr)
    if value is None:
        return None
    return value.lower() == "true"


def _get_attr_int(elem: ET.Element, attr: str) -> int | None:
    """Get integer value from an element's attribute."""
    value = elem.get(attr)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None
