"""Query model dataclasses for EGP Query elements."""

from dataclasses import dataclass, field


@dataclass
class InputTable:
    """A table input to a query."""

    id: str | None = None
    input_table_name: str | None = None
    include_schema: bool | None = None
    schema: str | None = None
    alias: str | None = None
    options: str | None = None
    expanded: bool | None = None
    data_id: str | None = None
    original_server: str | None = None
    original_library: str | None = None
    original_member: str | None = None
    original_engine: str | None = None


@dataclass
class ResultItem:
    """A result column in a query output."""

    result_id: str | None = None
    alias: str | None = None
    table_id: str | None = None
    format: str | None = None
    length: int | None = None
    label: str | None = None
    label_modified: bool | None = None
    base_column_name: str | None = None
    calc_id: str | None = None


@dataclass
class Expression:
    """A recursive expression tree used within calculations.

    Expressions can be nested to represent complex formulas.
    """

    expression_type: str | None = None
    expression_text: str | None = None
    sub_expressions: list["Expression"] = field(default_factory=list)


@dataclass
class Calculation:
    """A computed column definition in a query."""

    id: str | None = None
    alias: str | None = None
    format: str | None = None
    label: str | None = None
    length: int | None = None
    is_aggregate: bool | None = None
    is_replacement: bool | None = None
    column_name: str | None = None
    expression: Expression | None = None


@dataclass
class JoinItem:
    """A join condition between two tables in a query."""

    left_table_id: str | None = None
    left_column_name: str | None = None
    right_table_id: str | None = None
    right_column_name: str | None = None
    join_operator: str | None = None
    join_type: str | None = None
    join_filter: str | None = None


@dataclass
class FilterNode:
    """A filter condition node, potentially hierarchical.

    FilterNodes can have children to represent AND/OR groupings.
    """

    filter_type: str | None = None
    table_id: str | None = None
    column_name: str | None = None
    operator: str | None = None
    value: str | None = None
    children: list["FilterNode"] = field(default_factory=list)


@dataclass
class OrderItem:
    """A sort specification for query results."""

    table_id: str | None = None
    column_name: str | None = None
    sort_direction: str | None = None


@dataclass
class GroupItem:
    """A grouping specification for aggregate queries."""

    table_id: str | None = None
    column_name: str | None = None


@dataclass
class QueryBuilderTablePosition:
    """Visual position of a table in the query builder UI."""

    table_id: str | None = None
    x: int | None = None
    y: int | None = None
    width: int | None = None
    height: int | None = None


@dataclass
class QueryModel:
    """Complete query definition extracted from a Query element.

    Contains all sub-collections: input tables, result columns,
    calculations, joins, filters, ordering, and grouping.
    """

    use_explicit_and_execute: bool | None = None
    keep_results_in_database_if_possible: bool | None = None
    in_obs: int | None = None
    out_obs: int | None = None
    output_library: str | None = None
    output_member: str | None = None
    output_type: str | None = None
    server: str | None = None
    allow_duplicates: bool | None = None
    output_label: str | None = None
    output_options: str | None = None
    title: str | None = None
    footnote: str | None = None
    grouping_style: str | None = None
    passthrough_enabled: bool | None = None
    passthrough_server: str | None = None
    passthrough_library: str | None = None
    passthrough_member: str | None = None
    input_tables: list[InputTable] = field(default_factory=list)
    result_items: list[ResultItem] = field(default_factory=list)
    calculations: list[Calculation] = field(default_factory=list)
    join_items: list[JoinItem] = field(default_factory=list)
    where_filters: list[FilterNode] = field(default_factory=list)
    having_filters: list[FilterNode] = field(default_factory=list)
    order_items: list[OrderItem] = field(default_factory=list)
    group_items: list[GroupItem] = field(default_factory=list)
    query_builder_settings: list[QueryBuilderTablePosition] = field(
        default_factory=list
    )
    display_vars_sort_order: str | None = None
    use_labels_for_var_names: bool | None = None
