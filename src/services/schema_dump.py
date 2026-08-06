"""Parse PostgreSQL/MySQL schema dumps into the shared raw-schema contract."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import Lock

import sqlglot
import sqlglot.expressions as exp

from src.models.raw_schema import (
    ColumnMetadata,
    ColumnReference,
    DumpDatabaseType,
    DumpSchemaRequest,
    ForeignKeyMetadata,
    IndexMetadata,
    RawSchema,
    RelationshipMetadata,
    SchemaExtractionResult,
    TableMetadata,
)
from src.services.introspection_errors import InvalidSchemaDumpError, UnsupportedDatabaseTypeError
from src.services.schema_normalization import build_fk_links, normalize_data_type, utc_timestamp

SQLGLOT_DIALECTS: dict[DumpDatabaseType, str] = {
    "postgresql": "postgres",
    "mysql": "mysql",
}
_SQLGLOT_LOG_LOCK = Lock()
TableKey = tuple[str | None, str]


@dataclass
class _ColumnBuild:
    name: str
    data_type: str
    dialect: str
    default_schema: str | None
    is_nullable: bool = True
    is_primary_key: bool = False
    default_value: str | None = None
    reference: exp.Reference | None = None

    def metadata(self) -> ColumnMetadata:
        return {
            "column_name": self.name,
            "data_type": self.data_type,
            "is_nullable": self.is_nullable,
            "is_primary_key": self.is_primary_key,
            "is_foreign_key": False,
            "default_value": self.default_value,
            "sample_values": None,
            "references": None,
        }


@dataclass
class _TableBuilder:
    table_name: str
    schema_name: str | None
    dialect: str
    relationships: list[RelationshipMetadata]
    columns: list[ColumnMetadata] = field(default_factory=list)
    primary_keys: list[str] = field(default_factory=list)
    foreign_keys: list[ForeignKeyMetadata] = field(default_factory=list)
    indexes: list[IndexMetadata] = field(default_factory=list)
    references: dict[str, ColumnReference] = field(default_factory=dict)

    def add_column(self, expression: exp.ColumnDef) -> None:
        state = _column_state(expression, self.dialect, self.schema_name)
        for constraint in expression.constraints:
            _apply_column_constraint(state, constraint)
        column = state.metadata()
        self.columns.append(column)
        if state.is_primary_key:
            self.primary_keys.append(state.name)
        if state.reference:
            self.add_foreign_key(_inline_foreign_key(state, self.schema_name))

    def add_foreign_key(self, foreign_key: ForeignKeyMetadata) -> None:
        links, relationships = build_fk_links(self.table_name, self.schema_name, foreign_key)
        self.foreign_keys.append(foreign_key)
        self.references.update(links)
        self.relationships.extend(relationships)

    def add_primary_key(self, columns: list[str]) -> None:
        for column in columns:
            if column not in self.primary_keys:
                self.primary_keys.append(column)

    def apply_column_flags(self) -> None:
        primary_keys = set(self.primary_keys)
        for column in self.columns:
            name = column["column_name"]
            if name in primary_keys:
                column["is_primary_key"] = True
                column["is_nullable"] = False
            if name in self.references:
                column["is_foreign_key"] = True
                column["references"] = self.references[name]

    def metadata(self) -> TableMetadata:
        self.apply_column_flags()
        return {
            "table_name": self.table_name,
            "schema_name": self.schema_name,
            "table_type": "BASE TABLE",
            "row_count_estimate": None,
            "columns": self.columns,
            "primary_keys": self.primary_keys,
            "foreign_keys": self.foreign_keys,
            "indexes": sorted(self.indexes, key=lambda item: item["index_name"]),
        }


@dataclass
class _DumpParser:
    db_type: DumpDatabaseType
    dialect: str
    current_schema: str | None
    tables: dict[TableKey, _TableBuilder] = field(default_factory=dict)
    relationships: list[RelationshipMetadata] = field(default_factory=list)

    def consume(self, statements: list[exp.Expression]) -> None:
        for statement in statements:
            if isinstance(statement, exp.Use) and statement.this:
                self.current_schema = statement.this.name
            elif isinstance(statement, exp.Create) and statement.kind == "TABLE":
                self._create_table(statement)
            elif isinstance(statement, exp.Alter):
                self._alter_table(statement)
            elif isinstance(statement, exp.Create) and _is_index(statement):
                self._create_index(statement)
            elif _is_broken_schema_command(statement):
                raise ValueError("Malformed schema DDL.")

    def _create_table(self, statement: exp.Create) -> None:
        if not isinstance(statement.this, exp.Schema):
            raise ValueError("CREATE TABLE has no column schema.")
        table_name, schema_name = _table_identity(statement.this, self.current_schema)
        key = (schema_name, table_name)
        if key in self.tables:
            raise ValueError("Duplicate table definition.")
        builder = _TableBuilder(table_name, schema_name, self.dialect, self.relationships)
        for expression in statement.this.expressions:
            _apply_table_expression(builder, expression)
        if not builder.columns:
            raise ValueError("CREATE TABLE has no typed columns.")
        self.tables[key] = builder

    def _alter_table(self, statement: exp.Alter) -> None:
        builder = self._find_table(statement.this)
        if not builder:
            return
        for action in statement.args.get("actions", []):
            if not isinstance(action, exp.AddConstraint):
                continue
            for expression in action.expressions:
                _apply_table_expression(builder, expression)

    def _create_index(self, statement: exp.Create) -> None:
        index_expression = statement.this
        if not isinstance(index_expression, exp.Index):
            return
        table_expression = index_expression.args.get("table")
        builder = self._find_table(table_expression)
        if not builder:
            return
        builder.indexes.append(_index_metadata(statement, index_expression, self.dialect))

    def _find_table(self, expression: exp.Expression | None) -> _TableBuilder | None:
        if not isinstance(expression, exp.Table):
            return None
        key = (expression.db or self.current_schema, expression.name)
        return self.tables.get(key)

    def result(self) -> SchemaExtractionResult:
        tables = [self.tables[key].metadata() for key in sorted(self.tables, key=_table_key)]
        raw_schema: RawSchema = {
            "source": {
                "type": "sql_dump",
                "db_engine": self.db_type,
                "connection_id": None,
                "extracted_at": utc_timestamp(),
            },
            "tables": tables,
            "relationships": sorted(self.relationships, key=_relationship_key),
        }
        return {"raw_schema": raw_schema, "warnings": []}


def parse_schema_dump(request: DumpSchemaRequest) -> SchemaExtractionResult:
    """Parse schema-only SQL without executing any statement."""
    db_type = request["db_type"]
    if db_type not in SQLGLOT_DIALECTS:
        raise UnsupportedDatabaseTypeError("SQL dump parsing supports only postgresql and mysql.")
    content = request["sql_content"].strip()
    if not content:
        raise InvalidSchemaDumpError("Invalid SQL schema dump.")
    try:
        statements = _parse_statements(content, SQLGLOT_DIALECTS[db_type])
        parser = _DumpParser(db_type, SQLGLOT_DIALECTS[db_type], _default_schema(db_type))
        parser.consume(statements)
        if not parser.tables:
            raise ValueError("No table DDL found.")
        return parser.result()
    except (sqlglot.errors.SqlglotError, ValueError) as exc:
        raise InvalidSchemaDumpError("Invalid SQL schema dump.") from exc


def _parse_statements(content: str, dialect: str) -> list[exp.Expression]:
    sqlglot_logger = logging.getLogger("sqlglot")
    with _SQLGLOT_LOG_LOCK:
        was_disabled = sqlglot_logger.disabled
        sqlglot_logger.disabled = True
        try:
            parsed = sqlglot.parse(content, read=dialect, error_level=sqlglot.ErrorLevel.RAISE)
        finally:
            sqlglot_logger.disabled = was_disabled
    return [statement for statement in parsed if statement is not None]


def _default_schema(db_type: DumpDatabaseType) -> str | None:
    return "public" if db_type == "postgresql" else None


def _column_state(expression: exp.ColumnDef, dialect: str, schema: str | None) -> _ColumnBuild:
    if not expression.name or not expression.kind:
        raise ValueError("Column name or type is missing.")
    data_type = normalize_data_type(expression.kind.sql(dialect=dialect))
    return _ColumnBuild(expression.name, data_type, dialect, schema)


def _apply_column_constraint(state: _ColumnBuild, constraint: exp.ColumnConstraint) -> None:
    kind = constraint.kind
    if isinstance(kind, exp.PrimaryKeyColumnConstraint):
        state.is_primary_key = True
        state.is_nullable = False
    elif isinstance(kind, exp.NotNullColumnConstraint):
        state.is_nullable = False
    elif isinstance(kind, exp.DefaultColumnConstraint) and kind.this:
        state.default_value = kind.this.sql(dialect=state.dialect)
    elif isinstance(kind, exp.Reference):
        state.reference = kind


def _inline_foreign_key(state: _ColumnBuild, schema: str | None) -> ForeignKeyMetadata:
    if not state.reference:
        raise ValueError("Inline foreign key reference is missing.")
    table, target_schema, columns = _reference_identity(state.reference, schema)
    if len(columns) != 1:
        raise ValueError("Inline foreign key must refer to one column.")
    return {
        "constraint_name": None,
        "constrained_columns": [state.name],
        "referred_schema": target_schema,
        "referred_table": table,
        "referred_columns": columns,
    }


def _apply_table_expression(builder: _TableBuilder, expression: exp.Expression) -> None:
    if isinstance(expression, exp.ColumnDef):
        builder.add_column(expression)
    elif isinstance(expression, exp.PrimaryKey):
        builder.add_primary_key(_expression_columns(expression))
    elif isinstance(expression, exp.ForeignKey):
        builder.add_foreign_key(_foreign_key_metadata(expression, None, builder.schema_name))
    elif isinstance(expression, exp.Constraint):
        _apply_named_constraint(builder, expression)
    elif isinstance(expression, exp.IndexColumnConstraint):
        builder.indexes.append(_inline_index(expression))


def _apply_named_constraint(builder: _TableBuilder, constraint: exp.Constraint) -> None:
    name = constraint.this.name if isinstance(constraint.this, exp.Identifier) else None
    for expression in constraint.expressions:
        if isinstance(expression, exp.ForeignKey):
            builder.add_foreign_key(_foreign_key_metadata(expression, name, builder.schema_name))
        elif isinstance(expression, exp.PrimaryKey):
            builder.add_primary_key(_expression_columns(expression))


def _foreign_key_metadata(
    expression: exp.ForeignKey,
    name: str | None,
    schema: str | None,
) -> ForeignKeyMetadata:
    reference = expression.args.get("reference")
    if not isinstance(reference, exp.Reference):
        raise ValueError("Foreign key target is missing.")
    table, target_schema, target_columns = _reference_identity(reference, schema)
    source_columns = _expression_columns(expression)
    if not source_columns or len(source_columns) != len(target_columns):
        raise ValueError("Foreign key column count does not match its target.")
    return {
        "constraint_name": name,
        "constrained_columns": source_columns,
        "referred_schema": target_schema,
        "referred_table": table,
        "referred_columns": target_columns,
    }


def _reference_identity(
    reference: exp.Reference,
    default_schema: str | None,
) -> tuple[str, str | None, list[str]]:
    if not isinstance(reference.this, exp.Schema):
        raise ValueError("Foreign key reference has no target columns.")
    table_name, schema_name = _table_identity(reference.this, default_schema)
    columns = _expression_columns(reference.this)
    if not columns:
        raise ValueError("Foreign key reference has no target columns.")
    return table_name, schema_name, columns


def _table_identity(expression: exp.Expression, default_schema: str | None) -> tuple[str, str | None]:
    table = expression.this if isinstance(expression, exp.Schema) else expression
    if not isinstance(table, exp.Table) or not table.name:
        raise ValueError("Table name is missing.")
    return table.name, table.db or default_schema


def _expression_columns(expression: exp.Expression) -> list[str]:
    columns: list[str] = []
    for item in expression.expressions:
        if isinstance(item, exp.Identifier):
            columns.append(item.name)
        elif isinstance(item, exp.Column):
            columns.append(item.name)
    return columns


def _inline_index(expression: exp.IndexColumnConstraint) -> IndexMetadata:
    name = expression.this.name if isinstance(expression.this, exp.Identifier) else ""
    columns = _expression_columns(expression)
    return {"index_name": name, "columns": columns, "is_unique": False}


def _index_metadata(statement: exp.Create, index: exp.Index, dialect: str) -> IndexMetadata:
    name = index.this.name if isinstance(index.this, exp.Identifier) else ""
    parameters = index.args.get("params")
    columns = _index_parameter_columns(parameters, dialect)
    is_unique = bool(statement.args.get("unique") or index.args.get("unique"))
    return {"index_name": name, "columns": columns, "is_unique": is_unique}


def _index_parameter_columns(parameters: exp.Expression | None, dialect: str) -> list[str]:
    if not parameters:
        return []
    columns = parameters.args.get("columns", [])
    result: list[str] = []
    for item in columns:
        target = item.this if hasattr(item, "this") else item
        result.append(target.name if hasattr(target, "name") else target.sql(dialect=dialect))
    return result


def _is_index(statement: exp.Create) -> bool:
    return statement.kind == "INDEX" or isinstance(statement.this, exp.Index)


def _is_broken_schema_command(statement: exp.Expression) -> bool:
    if not isinstance(statement, exp.Command):
        return False
    command = str(statement.this).strip().upper()
    return command.startswith("CREATE TABLE") or command.startswith("ALTER TABLE")


def _table_key(value: TableKey) -> tuple[str, str]:
    schema, table = value
    return schema or "", table


def _relationship_key(value: RelationshipMetadata) -> tuple[str, str, str, str]:
    return value["from_table"], value["from_column"], value["to_table"], value["to_column"]
