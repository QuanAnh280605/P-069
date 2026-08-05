"""SQLGlot AST extraction into the persistence-free canonical schema IR."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field, replace

from sqlglot import Dialect, ErrorLevel, exp
from sqlglot.errors import SqlglotError

from src.models.schema_metadata import (
    ColumnMetadata,
    DiagnosticCode,
    DiagnosticSeverity,
    ForeignKeyMetadata,
    Identifier,
    ParseCompleteness,
    ParseDiagnostic,
    ParseResult,
    PrimaryKeyMetadata,
    QualifiedIdentifier,
    RawSchemaMetadata,
    SchemaDialect,
    SchemaMetadata,
    TableMetadata,
    default_schema_identifier,
)
from src.services.sql_dump_parser_models import (
    AlterRecord,
    ColumnBuilder,
    ForeignKeySpec,
    PrimaryKeySpec,
    SourceLocation,
    SqlDumpParseError,
    TableBuilder,
)
from src.services.sql_dump_scanner_models import ScannedStatement, ScanResult, StatementKind


@dataclass
class _ParseContext:
    dialect: SchemaDialect
    sqlglot_dialect: str
    schemas: dict[str, Identifier] = field(default_factory=dict)
    declared_schemas: set[str] = field(default_factory=set)
    tables: dict[tuple[str, str], TableBuilder] = field(default_factory=dict)
    alters: list[AlterRecord] = field(default_factory=list)
    diagnostics: list[ParseDiagnostic] = field(default_factory=list)
    max_diagnostics: int = 100


async def parse_sql_dump(scan_result: ScanResult) -> ParseResult:
    """Parse scanner-approved DDL candidates without DB, executor, or LLM access."""
    return await asyncio.to_thread(_parse_sync, scan_result)


def _parse_sync(scan_result: ScanResult) -> ParseResult:
    context = _new_context(scan_result)
    for statement in scan_result.statements:
        expression = _parse_expression(statement, context)
        _register_statement(expression, statement, context)
    _apply_alters(context)
    tables = _resolve_tables(context)
    schema = RawSchemaMetadata(
        dialect=context.dialect,
        schemas=tuple(SchemaMetadata(schema_name=item) for item in context.schemas.values()),
        tables=tuple(tables),
    )
    return ParseResult(
        schema=schema,
        diagnostics=tuple(context.diagnostics),
        completeness=ParseCompleteness.COMPLETE,
    )


def _new_context(scan_result: ScanResult) -> _ParseContext:
    dialect = "postgres" if scan_result.dialect == SchemaDialect.POSTGRESQL else "mysql"
    return _ParseContext(
        dialect=scan_result.dialect,
        sqlglot_dialect=dialect,
        diagnostics=list(scan_result.diagnostics),
        max_diagnostics=scan_result.max_diagnostics,
    )


def _statement_schema(statement: ScannedStatement, context: _ParseContext) -> Identifier | None:
    if statement.default_schema_name is None:
        return None
    return Identifier.from_raw(
        statement.default_schema_name,
        context.dialect,
        quoted=statement.default_schema_quoted,
    )


def _parse_expression(statement: ScannedStatement, context: _ParseContext) -> exp.Expression:
    source = SourceLocation.from_statement(statement)
    try:
        dialect = Dialect.get_or_raise(context.sqlglot_dialect)
        parser = dialect.parser(error_level=ErrorLevel.RAISE)
        parser._warn_unsupported = lambda: None
        expressions = parser.parse(dialect.tokenize(statement.text), statement.text)
    except SqlglotError as error:
        raise _fatal(source, DiagnosticCode.DDL_PARSE_ERROR, "Supported DDL could not be parsed") from error
    if len(expressions) != 1 or expressions[0] is None:
        raise _fatal(source, DiagnosticCode.DDL_PARSE_ERROR, "Expected exactly one supported DDL statement")
    return expressions[0]


def _register_statement(
    expression: exp.Expression,
    statement: ScannedStatement,
    context: _ParseContext,
) -> None:
    source = SourceLocation.from_statement(statement)
    default_schema = _statement_schema(statement, context)
    if isinstance(expression, exp.Command):
        raise _fatal(source, DiagnosticCode.UNSUPPORTED_STATEMENT, "Core DDL produced an unsupported AST")
    if statement.kind == StatementKind.CREATE_SCHEMA:
        _register_schema(expression, source, context)
    elif statement.kind == StatementKind.CREATE_TABLE:
        _register_table(expression, source, context, default_schema)
    elif statement.kind == StatementKind.ALTER_TABLE:
        _register_alter(expression, source, context, default_schema)
    else:
        raise _fatal(source, DiagnosticCode.DDL_PARSE_ERROR, "Scanner emitted an unknown DDL kind")


def _register_schema(expression: exp.Expression, source: SourceLocation, context: _ParseContext) -> None:
    if not isinstance(expression, exp.Create) or str(expression.args.get("kind", "")).upper() != "SCHEMA":
        raise _fatal(source, DiagnosticCode.DDL_PARSE_ERROR, "CREATE SCHEMA did not produce a supported AST")
    table = expression.this
    if not isinstance(table, exp.Table):
        raise _fatal(source, DiagnosticCode.DDL_PARSE_ERROR, "CREATE SCHEMA has no valid identifier")
    identifier = _identifier(table.args.get("db") or table.this, context, source)
    key = identifier.normalized_name
    if key in context.declared_schemas:
        raise _fatal(source, DiagnosticCode.DUPLICATE_OBJECT, "Duplicate schema identity")
    context.declared_schemas.add(key)
    context.schemas.setdefault(key, identifier)


def _register_table(
    expression: exp.Expression,
    source: SourceLocation,
    context: _ParseContext,
    default_schema: Identifier | None,
) -> None:
    schema_ast = _require_table_create(expression, source)
    schema_name, table_name = _table_identifiers(schema_ast.this, context, source, default_schema)
    columns = _extract_columns(schema_ast, source, context)
    table = TableBuilder(schema_name, table_name, columns, source)
    if table.key in context.tables:
        raise _fatal(source, DiagnosticCode.DUPLICATE_OBJECT, "Duplicate qualified table identity", table)
    context.tables[table.key] = table
    context.schemas.setdefault(schema_name.normalized_name, schema_name)
    _collect_create_constraints(schema_ast, table, context)


def _require_table_create(expression: exp.Expression, source: SourceLocation) -> exp.Schema:
    if not isinstance(expression, exp.Create) or str(expression.args.get("kind", "")).upper() != "TABLE":
        raise _fatal(source, DiagnosticCode.DDL_PARSE_ERROR, "CREATE TABLE did not produce a supported AST")
    if not isinstance(expression.this, exp.Schema) or not isinstance(expression.this.this, exp.Table):
        raise _fatal(source, DiagnosticCode.DDL_PARSE_ERROR, "CREATE TABLE has no explicit column schema")
    return expression.this


def _register_alter(
    expression: exp.Expression,
    source: SourceLocation,
    context: _ParseContext,
    default_schema: Identifier | None,
) -> None:
    if not isinstance(expression, exp.Alter) or str(expression.args.get("kind", "")).upper() != "TABLE":
        raise _fatal(source, DiagnosticCode.DDL_PARSE_ERROR, "ALTER TABLE did not produce a supported AST")
    if not isinstance(expression.this, exp.Table):
        raise _fatal(source, DiagnosticCode.DDL_PARSE_ERROR, "ALTER TABLE has no valid target")
    context.alters.append(AlterRecord(expression, source, default_schema))


def _extract_columns(schema_ast: exp.Schema, source: SourceLocation, context: _ParseContext) -> list[ColumnBuilder]:
    definitions = [item for item in schema_ast.expressions if isinstance(item, exp.ColumnDef)]
    if not definitions:
        raise _fatal(source, DiagnosticCode.DDL_PARSE_ERROR, "CREATE TABLE contains no supported columns")
    columns = [_column_builder(item, position, source, context) for position, item in enumerate(definitions, 1)]
    keys = [item.name.normalized_name for item in columns]
    if len(keys) != len(set(keys)):
        raise _fatal(source, DiagnosticCode.DUPLICATE_OBJECT, "Duplicate normalized column identity")
    return columns


def _column_builder(
    definition: exp.ColumnDef,
    position: int,
    source: SourceLocation,
    context: _ParseContext,
) -> ColumnBuilder:
    name = _identifier(definition.this, context, source)
    kind = definition.args.get("kind")
    if not isinstance(kind, exp.DataType) or kind.is_type(exp.DataType.Type.UNKNOWN):
        raise _fatal(source, DiagnosticCode.DDL_PARSE_ERROR, "Column has no supported data type")
    constraints = definition.args.get("constraints") or []
    nullable = not any(_constraint_is(item, exp.NotNullColumnConstraint) for item in constraints)
    default = _column_default(constraints, context.sqlglot_dialect)
    return ColumnBuilder(
        name=name,
        ordinal_position=position,
        raw_data_type=kind.sql(dialect=context.sqlglot_dialect),
        data_type=kind.sql(),
        nullable=nullable,
        default_expression=default,
    )


def _column_default(constraints: list[exp.Expression], dialect: str) -> str | None:
    defaults = [item.args.get("kind") for item in constraints]
    defaults = [item for item in defaults if isinstance(item, exp.DefaultColumnConstraint)]
    if not defaults:
        return None
    expression = defaults[0].this
    return expression.sql(dialect=dialect) if isinstance(expression, exp.Expression) else None


def _constraint_is(wrapper: exp.Expression, kind_type: type[exp.Expression]) -> bool:
    return isinstance(wrapper.args.get("kind"), kind_type)


def _collect_create_constraints(schema_ast: exp.Schema, table: TableBuilder, context: _ParseContext) -> None:
    for definition in schema_ast.expressions:
        if isinstance(definition, exp.ColumnDef):
            _collect_column_constraints(definition, table, context)
        elif isinstance(definition, (exp.PrimaryKey, exp.ForeignKey, exp.Constraint)):
            _collect_constraint(definition, table, table.source, context)


def _collect_column_constraints(
    definition: exp.ColumnDef,
    table: TableBuilder,
    context: _ParseContext,
) -> None:
    column_name = _identifier(definition.this, context, table.source)
    for wrapper in definition.args.get("constraints") or []:
        kind = wrapper.args.get("kind")
        name = _optional_identifier(wrapper.args.get("this"), context, table.source)
        if isinstance(kind, exp.PrimaryKeyColumnConstraint):
            table.primary_keys.append(PrimaryKeySpec((column_name,), name, table.source))
        elif isinstance(kind, exp.Reference):
            table.foreign_keys.append(_foreign_spec((column_name,), kind, name, table, table.source, context))


def _collect_constraint(
    node: exp.Expression,
    table: TableBuilder,
    source: SourceLocation,
    context: _ParseContext,
    name: Identifier | None = None,
) -> int:
    if isinstance(node, exp.Constraint):
        constraint_name = _optional_identifier(node.this, context, source)
        return sum(_collect_constraint(item, table, source, context, constraint_name) for item in node.expressions)
    if isinstance(node, exp.PrimaryKey):
        columns = _identifier_tuple(node.expressions, context, source)
        table.primary_keys.append(PrimaryKeySpec(columns, name, source))
        return 1
    if isinstance(node, exp.ForeignKey):
        columns = _identifier_tuple(node.expressions, context, source)
        table.foreign_keys.append(_foreign_spec(columns, node.args.get("reference"), name, table, source, context))
        return 1
    return 0


def _foreign_spec(
    columns: tuple[Identifier, ...],
    reference: object,
    name: Identifier | None,
    table: TableBuilder,
    source: SourceLocation,
    context: _ParseContext,
) -> ForeignKeySpec:
    if not isinstance(reference, exp.Reference) or not isinstance(reference.this, exp.Schema):
        raise _fatal(source, DiagnosticCode.DDL_PARSE_ERROR, "Foreign key has no supported reference")
    target_ast = reference.this
    referred_schema, referred_table = _table_identifiers(target_ast.this, context, source, table.schema_name)
    referred_columns = _identifier_tuple(target_ast.expressions, context, source)
    if reference.args.get("options"):
        _add_warning(context, source, "Foreign key actions are not represented in the P1 canonical IR")
    return ForeignKeySpec(columns, name, referred_schema, referred_table, referred_columns, source)


def _apply_alters(context: _ParseContext) -> None:
    for record in context.alters:
        target_ast = record.expression.this
        schema_name, table_name = _table_identifiers(target_ast, context, record.source, record.default_schema)
        key = (schema_name.normalized_name, table_name.normalized_name)
        table = context.tables.get(key)
        if table is None:
            raise _fatal(record.source, DiagnosticCode.DDL_PARSE_ERROR, "ALTER TABLE target is not declared")
        _apply_alter_actions(record, table, context)


def _apply_alter_actions(record: AlterRecord, table: TableBuilder, context: _ParseContext) -> None:
    actions = record.expression.args.get("actions") or []
    if not actions:
        raise _fatal(record.source, DiagnosticCode.DDL_PARSE_ERROR, "ALTER TABLE contains no supported action")
    for action in actions:
        if isinstance(action, exp.AddConstraint):
            _apply_added_constraint(action, record, table, context)
        elif isinstance(action, exp.AlterColumn):
            _apply_altered_column(action, record, table, context)
        else:
            raise _fatal(record.source, DiagnosticCode.DDL_PARSE_ERROR, "ALTER TABLE changes unsupported core metadata")


def _apply_added_constraint(
    action: exp.AddConstraint,
    record: AlterRecord,
    table: TableBuilder,
    context: _ParseContext,
) -> None:
    supported = sum(_collect_constraint(item, table, record.source, context) for item in action.expressions)
    if not supported:
        _add_warning(context, record.source, "An out-of-scope table constraint was ignored")


def _apply_altered_column(
    action: exp.AlterColumn,
    record: AlterRecord,
    table: TableBuilder,
    context: _ParseContext,
) -> None:
    column_name = _identifier(action.this, context, record.source)
    index = next((i for i, item in enumerate(table.columns) if item.name == column_name), None)
    if index is None:
        raise _fatal(record.source, DiagnosticCode.DDL_PARSE_ERROR, "ALTER COLUMN references an unknown column")
    default = _altered_default(action, record, context)
    table.columns[index] = replace(table.columns[index], default_expression=default)


def _altered_default(
    action: exp.AlterColumn,
    record: AlterRecord,
    context: _ParseContext,
) -> str | None:
    expression = action.args.get("default")
    if isinstance(expression, exp.Expression):
        return expression.sql(dialect=context.sqlglot_dialect)
    if action.args.get("drop") and "allow_null" not in action.args:
        return None
    raise _fatal(record.source, DiagnosticCode.DDL_PARSE_ERROR, "ALTER COLUMN action is not supported")


def _resolve_tables(context: _ParseContext) -> list[TableMetadata]:
    return [_resolve_table(table, context) for table in context.tables.values()]


def _resolve_table(table: TableBuilder, context: _ParseContext) -> TableMetadata:
    column_index = {item.name.normalized_name: item for item in table.columns}
    primary_key = _resolve_primary_key(table, column_index)
    foreign_keys = _resolve_foreign_keys(table, column_index, context)
    primary_names = {item.normalized_name for item in primary_key.constrained_columns} if primary_key else set()
    columns = tuple(_build_column(item, primary_names) for item in table.columns)
    return TableMetadata(
        schema_name=table.schema_name,
        table_name=table.table_name,
        columns=columns,
        primary_key=primary_key,
        foreign_keys=foreign_keys,
    )


def _resolve_primary_key(
    table: TableBuilder,
    column_index: dict[str, ColumnBuilder],
) -> PrimaryKeyMetadata | None:
    if len(table.primary_keys) > 1:
        raise _fatal(table.source, DiagnosticCode.CONFLICTING_CONSTRAINT, "Table declares multiple primary keys", table)
    if not table.primary_keys:
        return None
    spec = table.primary_keys[0]
    names = [item.normalized_name for item in spec.columns]
    if not names or len(names) != len(set(names)) or any(item not in column_index for item in names):
        raise _fatal(
            spec.source, DiagnosticCode.CONFLICTING_CONSTRAINT, "Primary key references an unknown column", table
        )
    return PrimaryKeyMetadata(constraint_name=spec.constraint_name, constrained_columns=spec.columns)


def _resolve_foreign_keys(
    table: TableBuilder,
    column_index: dict[str, ColumnBuilder],
    context: _ParseContext,
) -> tuple[ForeignKeyMetadata, ...]:
    _reject_duplicate_foreign_keys(table)
    return tuple(_resolve_foreign_key(spec, table, column_index, context) for spec in table.foreign_keys)


def _resolve_foreign_key(
    spec: ForeignKeySpec,
    table: TableBuilder,
    column_index: dict[str, ColumnBuilder],
    context: _ParseContext,
) -> ForeignKeyMetadata:
    if not spec.columns or len(spec.columns) != len(spec.referred_columns):
        raise _fatal(spec.source, DiagnosticCode.CONFLICTING_CONSTRAINT, "Foreign key column arity is invalid", table)
    local_names = [item.normalized_name for item in spec.columns]
    target_names = [item.normalized_name for item in spec.referred_columns]
    if len(local_names) != len(set(local_names)) or len(target_names) != len(set(target_names)):
        raise _fatal(spec.source, DiagnosticCode.CONFLICTING_CONSTRAINT, "Foreign key repeats a mapped column", table)
    if any(item.normalized_name not in column_index for item in spec.columns):
        raise _fatal(
            spec.source, DiagnosticCode.CONFLICTING_CONSTRAINT, "Foreign key references an unknown local column", table
        )
    target = context.tables.get((spec.referred_schema.normalized_name, spec.referred_table.normalized_name))
    if target is None or not _target_has_columns(target, spec.referred_columns):
        raise _fatal(spec.source, DiagnosticCode.UNRESOLVED_FOREIGN_KEY, "Foreign key target cannot be resolved", table)
    return ForeignKeyMetadata(
        constraint_name=spec.constraint_name,
        constrained_columns=spec.columns,
        referred_schema=spec.referred_schema,
        referred_table=spec.referred_table,
        referred_columns=spec.referred_columns,
    )


def _reject_duplicate_foreign_keys(table: TableBuilder) -> None:
    keys = [
        (
            tuple(item.normalized_name for item in spec.columns),
            spec.referred_schema.normalized_name,
            spec.referred_table.normalized_name,
            tuple(item.normalized_name for item in spec.referred_columns),
        )
        for spec in table.foreign_keys
    ]
    names = [item.constraint_name.normalized_name for item in table.foreign_keys if item.constraint_name]
    primary_name = table.primary_keys[0].constraint_name if len(table.primary_keys) == 1 else None
    if primary_name:
        names.append(primary_name.normalized_name)
    if len(keys) != len(set(keys)) or len(names) != len(set(names)):
        raise _fatal(table.source, DiagnosticCode.CONFLICTING_CONSTRAINT, "Duplicate foreign key constraint", table)


def _target_has_columns(table: TableBuilder, columns: tuple[Identifier, ...]) -> bool:
    target_names = {item.name.normalized_name for item in table.columns}
    return bool(columns) and all(item.normalized_name in target_names for item in columns)


def _build_column(column: ColumnBuilder, primary_names: set[str]) -> ColumnMetadata:
    primary = column.name.normalized_name in primary_names
    return ColumnMetadata(
        column_name=column.name,
        ordinal_position=column.ordinal_position,
        raw_data_type=column.raw_data_type,
        data_type=column.data_type,
        nullable=column.nullable and not primary,
        default_expression=column.default_expression,
        primary_key=primary,
    )


def _table_identifiers(
    node: object,
    context: _ParseContext,
    source: SourceLocation,
    fallback_schema: Identifier | None = None,
) -> tuple[Identifier, Identifier]:
    if not isinstance(node, exp.Table) or node.args.get("catalog"):
        raise _fatal(source, DiagnosticCode.DDL_PARSE_ERROR, "Only schema-qualified table identities are supported")
    table_name = _identifier(node.this, context, source)
    schema_ast = node.args.get("db")
    schema_name = _optional_identifier(schema_ast, context, source)
    return schema_name or fallback_schema or default_schema_identifier(context.dialect), table_name


def _identifier(node: object, context: _ParseContext, source: SourceLocation) -> Identifier:
    if not isinstance(node, exp.Identifier) or not node.name:
        raise _fatal(source, DiagnosticCode.DDL_PARSE_ERROR, "Expected a valid SQL identifier")
    return Identifier.from_raw(node.name, context.dialect, quoted=bool(node.args.get("quoted")))


def _optional_identifier(
    node: object,
    context: _ParseContext,
    source: SourceLocation,
) -> Identifier | None:
    return _identifier(node, context, source) if node is not None else None


def _identifier_tuple(
    nodes: list[exp.Expression],
    context: _ParseContext,
    source: SourceLocation,
) -> tuple[Identifier, ...]:
    identifiers = []
    for node in nodes:
        candidate = node.this if isinstance(node, exp.Column) else node
        identifiers.append(_identifier(candidate, context, source))
    return tuple(identifiers)


def _add_warning(context: _ParseContext, source: SourceLocation, message: str) -> None:
    if len(context.diagnostics) >= context.max_diagnostics:
        return
    context.diagnostics.append(
        ParseDiagnostic(
            severity=DiagnosticSeverity.WARNING,
            code=DiagnosticCode.UNSUPPORTED_STATEMENT,
            message=message,
            statement_index=source.statement_index,
            line=source.line,
            column=source.column,
            recoverable=True,
        )
    )


def _fatal(
    source: SourceLocation,
    code: DiagnosticCode,
    message: str,
    table: TableBuilder | None = None,
) -> SqlDumpParseError:
    object_name = None
    if table is not None:
        object_name = QualifiedIdentifier(schema_name=table.schema_name, object_name=table.table_name)
    diagnostic = ParseDiagnostic(
        severity=DiagnosticSeverity.ERROR,
        code=code,
        message=message,
        statement_index=source.statement_index,
        line=source.line,
        column=source.column,
        object_name=object_name,
        recoverable=False,
    )
    return SqlDumpParseError((diagnostic,))
