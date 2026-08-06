"""Bounded lexical scanner for PostgreSQL and MySQL schema dumps."""

from __future__ import annotations

import codecs
import re
from collections.abc import AsyncIterable
from dataclasses import dataclass, field

from src.models.schema_metadata import (
    DiagnosticCode,
    DiagnosticSeverity,
    ParseDiagnostic,
    SchemaDialect,
)
from src.services.sql_dump_scanner_models import (
    ScannedStatement,
    ScannerLimits,
    ScannerMode,
    ScanResult,
    SqlDumpScanError,
    StatementCategory,
    StatementKind,
)
from src.services.sql_dump_scanner_models import (
    scan_error as _scan_error,
)
from src.services.sql_dump_scanner_models import (
    validate_extension as _validate_extension,
)
from src.services.sql_dump_scanner_models import (
    validate_file_size as _validate_file_size,
)

_CONTROL_PREVIEW_LIMIT = 512
_COMMENT_PREVIEW_LIMIT = 512
_PG_IDENTIFIER = r'(?:[A-Za-z_][A-Za-z0-9_$]*|"(?:[^"]|"")+")'
_PG_QUALIFIED_IDENTIFIER = rf"{_PG_IDENTIFIER}(?:\s*\.\s*{_PG_IDENTIFIER})*"
_PG_OWNER_STATEMENT = re.compile(
    rf"(?is)^ALTER\s+TABLE(?:\s+ONLY)?\s+{_PG_QUALIFIED_IDENTIFIER}\s+OWNER\s+TO\s+"
    rf"(?:{_PG_IDENTIFIER}|CURRENT_ROLE|CURRENT_USER|SESSION_USER)$"
)


@dataclass
class _DumpScanner:
    limits: ScannerLimits
    mode: ScannerMode = ScannerMode.NEUTRAL
    line: int = 1
    column: int = 1
    statement_index: int = 0
    nesting_depth: int = 0
    delimiter: str = ";"
    category: StatementCategory | None = None
    kind: StatementKind | None = None
    start_line: int | None = None
    start_column: int | None = None
    escaped: bool = False
    dollar_tag: str = ""
    neutral_previous: str = ""
    terminator_tail: str = ""
    block_depth: int = 0
    comment_previous: str = ""
    comment_preview: str = ""
    copy_line: str = ""
    data_warning_added: bool = False
    current_namespace: tuple[str, bool] | None = None
    buffer_bytes: int = 0
    buffer: list[str] = field(default_factory=list)
    preview: list[str] = field(default_factory=list)
    control_preview: list[str] = field(default_factory=list)
    lexical_tail: str = ""
    statements: list[ScannedStatement] = field(default_factory=list)
    diagnostics: list[ParseDiagnostic] = field(default_factory=list)
    evidence: set[SchemaDialect] = field(default_factory=set)

    def feed(self, text: str) -> None:
        """Consume one decoded text chunk without retaining the dump body."""
        for character in text:
            self._consume(character)
            self._advance(character)

    def finish(self, total_bytes: int, override: SchemaDialect | None) -> ScanResult:
        """Validate EOF state and return deterministic scanner output."""
        if self.mode == ScannerMode.LINE_COMMENT:
            self._finish_comment()
            self.mode = ScannerMode.NEUTRAL
        if self.mode == ScannerMode.COPY_DATA and self.copy_line.rstrip("\r") == r"\.":
            self.mode = ScannerMode.NEUTRAL
        if self.mode != ScannerMode.NEUTRAL or self.nesting_depth:
            self._fatal(DiagnosticCode.DDL_PARSE_ERROR, "SQL dump ends in an incomplete lexical state")
        if self.buffer or self.category:
            self._finalize_statement()
        if not self.statements:
            self._fatal(DiagnosticCode.NO_SUPPORTED_DDL, "SQL dump contains no supported schema DDL")
        dialect = self._resolve_dialect(override)
        return ScanResult(
            dialect=dialect,
            statements=tuple(self.statements),
            diagnostics=tuple(self.diagnostics),
            total_bytes=total_bytes,
            max_diagnostics=self.limits.max_diagnostics,
        )

    def _consume(self, character: str) -> None:
        handlers = {
            ScannerMode.NEUTRAL: self._consume_neutral,
            ScannerMode.SINGLE_QUOTE: self._consume_quote,
            ScannerMode.DOUBLE_QUOTE: self._consume_quote,
            ScannerMode.BACKTICK: self._consume_quote,
            ScannerMode.LINE_COMMENT: self._consume_line_comment,
            ScannerMode.BLOCK_COMMENT: self._consume_block_comment,
            ScannerMode.DOLLAR_QUOTE: self._consume_dollar_quote,
            ScannerMode.COPY_DATA: self._consume_copy_data,
        }
        handlers[self.mode](character)

    def _consume_neutral(self, character: str) -> None:
        if self.category == StatementCategory.DIRECTIVE:
            self._consume_directive(character)
            return
        if character == "-" and self.neutral_previous == "-":
            self._open_comment(ScannerMode.LINE_COMMENT, "--")
            return
        if character == "*" and self.neutral_previous == "/":
            self._open_comment(ScannerMode.BLOCK_COMMENT, "/*")
            return
        if self._consume_terminator(character):
            return
        if character in "'\"`":
            self._open_quote(character)
            return
        self._append_code(character)
        self._update_structure(character)

    def _consume_directive(self, character: str) -> None:
        if character not in "\r\n":
            self._append_code(character)
            return
        directive = "".join(self.buffer).strip()
        match = re.match(r"(?is)^DELIMITER\s+(\S+)$", directive)
        if match:
            self.delimiter = match.group(1)
            self.evidence.add(SchemaDialect.MYSQL)
        elif directive.startswith("\\"):
            self.evidence.add(SchemaDialect.POSTGRESQL)
        self._reset_statement()

    def _consume_quote(self, character: str) -> None:
        self._append_code(character)
        if self.escaped:
            self.escaped = False
            return
        if character == "\\":
            self.escaped = True
            return
        quote = {ScannerMode.SINGLE_QUOTE: "'", ScannerMode.DOUBLE_QUOTE: '"', ScannerMode.BACKTICK: "`"}[self.mode]
        if character == quote:
            self.mode = ScannerMode.NEUTRAL
            self.neutral_previous = ""

    def _consume_dollar_quote(self, character: str) -> None:
        self._append_code(character)
        if self.lexical_tail.endswith(self.dollar_tag):
            self.mode = ScannerMode.NEUTRAL
            self.dollar_tag = ""
            self.neutral_previous = ""

    def _consume_line_comment(self, character: str) -> None:
        if character in "\r\n":
            self._finish_comment()
            self.mode = ScannerMode.NEUTRAL
            self.neutral_previous = ""
            self._append_code(" ")
            return
        self._append_comment_preview(character)

    def _consume_block_comment(self, character: str) -> None:
        self._append_comment_preview(character)
        pair = self.comment_previous + character
        if pair == "/*":
            self.block_depth += 1
        elif pair == "*/":
            self.block_depth -= 1
            if self.block_depth == 0:
                self._finish_comment()
                self.mode = ScannerMode.NEUTRAL
                self._append_code(" ")
        self.comment_previous = character

    def _consume_copy_data(self, character: str) -> None:
        if character == "\n":
            if self.copy_line.rstrip("\r") == r"\.":
                self.mode = ScannerMode.NEUTRAL
            self.copy_line = ""
            return
        if len(self.copy_line) <= 2:
            self.copy_line += character

    def _consume_terminator(self, character: str) -> bool:
        if self.nesting_depth or not self.delimiter:
            self.terminator_tail = ""
            return False
        self.terminator_tail = (self.terminator_tail + character)[-len(self.delimiter) :]
        if self.terminator_tail != self.delimiter:
            return False
        if len(self.delimiter) > 1:
            self._remove_buffer_suffix(len(self.delimiter) - 1)
        self._finalize_statement()
        return True

    def _open_quote(self, character: str) -> None:
        self._append_code(character)
        self.neutral_previous = ""
        self.terminator_tail = ""
        if character == "`":
            self.mode = ScannerMode.BACKTICK
            self.evidence.add(SchemaDialect.MYSQL)
        elif character == '"':
            self.mode = ScannerMode.DOUBLE_QUOTE
        else:
            self.mode = ScannerMode.SINGLE_QUOTE

    def _open_comment(self, mode: ScannerMode, opener: str) -> None:
        self._remove_buffer_suffix(1)
        self.mode = mode
        self.comment_preview = opener
        self.comment_previous = opener[-1]
        self.block_depth = 1 if mode == ScannerMode.BLOCK_COMMENT else 0
        self.neutral_previous = ""
        self.terminator_tail = ""

    def _finish_comment(self) -> None:
        upper = self.comment_preview.upper()
        if "POSTGRESQL DATABASE DUMP" in upper or "DUMPED BY PG_DUMP" in upper:
            self.evidence.add(SchemaDialect.POSTGRESQL)
        if "MYSQL DUMP" in upper or "MYSQLDUMP" in upper or upper.startswith("/*!"):
            self.evidence.add(SchemaDialect.MYSQL)
        self.comment_preview = ""
        self.comment_previous = ""

    def _append_comment_preview(self, character: str) -> None:
        if len(self.comment_preview) < _COMMENT_PREVIEW_LIMIT:
            self.comment_preview += character

    def _append_code(self, character: str) -> None:
        if not self.buffer and self.category is None and character.isspace():
            return
        self._mark_statement_start()
        if self.category not in {
            StatementCategory.DATA,
            StatementCategory.COPY,
            StatementCategory.SKIP,
            StatementCategory.UNSUPPORTED,
        }:
            self.buffer.append(character)
            self.buffer_bytes += len(character.encode("utf-8"))
        if len(self.control_preview) < _CONTROL_PREVIEW_LIMIT:
            self.control_preview.append(character)
        self.lexical_tail = (self.lexical_tail + character)[-130:]
        if self.category is None:
            self.preview.append(character)
            self._classify()
        self._enforce_statement_limit()

    def _mark_statement_start(self) -> None:
        if self.start_line is None:
            self.start_line = self.line
            self.start_column = self.column

    def _classify(self) -> None:
        value = "".join(self.preview).lstrip()
        upper = value.upper()
        if upper.startswith("\\") or re.match(r"^DELIMITER(?:\s|$)", upper):
            self.category = StatementCategory.DIRECTIVE
            return
        match = re.match(r"^([A-Z]+)(?:\s+([A-Z]+))?", upper)
        if not match or not self._classification_ready(upper, match):
            return
        self._apply_classification(match.group(1), match.group(2))

    @staticmethod
    def _classification_ready(value: str, match: re.Match[str]) -> bool:
        first, second = match.group(1), match.group(2)
        if first in {"CREATE", "ALTER"}:
            return second is not None and len(value) > match.end(2)
        return len(value) > match.end(1) or value.endswith(";")

    def _apply_classification(self, first: str, second: str | None) -> None:
        if first == "CREATE" and second in {"SCHEMA", "TABLE"}:
            self.category = StatementCategory.CANDIDATE
            self.kind = StatementKind(f"create_{second.lower()}")
        elif first == "ALTER" and second == "TABLE":
            self.category = StatementCategory.CANDIDATE
            self.kind = StatementKind.ALTER_TABLE
        elif first == "COPY":
            self.category = StatementCategory.COPY
        elif first in {"INSERT", "REPLACE", "UPDATE", "DELETE", "LOCK", "UNLOCK"}:
            self.category = StatementCategory.DATA
        elif first == "USE":
            self.category = StatementCategory.NAMESPACE
        elif first in {"SET", "SELECT", "DROP", "GRANT", "REVOKE", "COMMENT", "ANALYZE"}:
            self.category = StatementCategory.SKIP
        else:
            self.category = StatementCategory.UNSUPPORTED
        if self.category not in {StatementCategory.CANDIDATE, StatementCategory.NAMESPACE}:
            self.buffer.clear()
            self.buffer_bytes = 0

    def _update_structure(self, character: str) -> None:
        self.neutral_previous = character
        if character == "(":
            self.nesting_depth += 1
            if self.nesting_depth > self.limits.max_nesting_depth:
                self._fatal(DiagnosticCode.DDL_PARSE_ERROR, "SQL nesting depth exceeds configured limit")
        elif character == ")" and self.nesting_depth:
            self.nesting_depth -= 1
        if character == "$":
            self._try_open_dollar_quote()

    def _try_open_dollar_quote(self) -> None:
        match = re.search(r"(\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$)$", self.lexical_tail)
        if match:
            self.dollar_tag = match.group(1)
            self.mode = ScannerMode.DOLLAR_QUOTE
            self.evidence.add(SchemaDialect.POSTGRESQL)
            self.neutral_previous = ""

    def _enforce_statement_limit(self) -> None:
        if self.buffer_bytes > self.limits.max_statement_bytes:
            self._fatal(DiagnosticCode.STATEMENT_TOO_LARGE, "Retained DDL statement exceeds configured limit")

    def _finalize_statement(self) -> None:
        category = self.category
        if category == StatementCategory.CANDIDATE:
            self._emit_candidate()
        elif category == StatementCategory.NAMESPACE:
            self._finish_namespace()
        elif category in {StatementCategory.DATA, StatementCategory.COPY}:
            self._finish_data_statement(category)
        elif category == StatementCategory.UNSUPPORTED:
            self._warn_unsupported()
        if category not in {None, StatementCategory.DIRECTIVE}:
            self.statement_index += 1
        self._reset_statement()

    def _emit_candidate(self) -> None:
        text = "".join(self.buffer).strip()
        if not text or self.kind is None:
            return
        if self.kind == StatementKind.ALTER_TABLE and _PG_OWNER_STATEMENT.fullmatch(text):
            self._warn_unsupported("Object ownership statement was ignored")
            return
        upper = text.upper()
        if "ALTER TABLE ONLY" in upper:
            self.evidence.add(SchemaDialect.POSTGRESQL)
        if re.search(r"\bENGINE\s*=", upper):
            self.evidence.add(SchemaDialect.MYSQL)
        self.statements.append(
            ScannedStatement(
                text=text,
                kind=self.kind,
                statement_index=self.statement_index,
                line=self.start_line or 1,
                column=self.start_column or 1,
                default_schema_name=self.current_namespace[0] if self.current_namespace else None,
                default_schema_quoted=self.current_namespace[1] if self.current_namespace else False,
            )
        )

    def _finish_namespace(self) -> None:
        statement = "".join(self.buffer).strip()
        match = re.fullmatch(r"(?is)USE\s+(`(?:``|[^`])+`|[A-Za-z_][A-Za-z0-9_$]*)", statement)
        if not match:
            self._fatal(DiagnosticCode.DDL_PARSE_ERROR, "USE has no supported database identifier")
        token = match.group(1)
        quoted = token.startswith("`")
        name = token[1:-1].replace("``", "`") if quoted else token
        self.current_namespace = (name, quoted)
        self.evidence.add(SchemaDialect.MYSQL)

    def _finish_data_statement(self, category: StatementCategory) -> None:
        header = "".join(self.control_preview).upper()
        if category == StatementCategory.COPY:
            self.evidence.add(SchemaDialect.POSTGRESQL)
            if re.search(r"\bFROM\s+STDIN\b", header):
                self.mode = ScannerMode.COPY_DATA
        if not self.data_warning_added:
            self._add_warning(DiagnosticCode.DATA_STATEMENTS_IGNORED, "Row data statements were ignored")
            self.data_warning_added = True

    def _warn_unsupported(self, message: str = "A non-core SQL statement was ignored") -> None:
        self._add_warning(
            DiagnosticCode.UNSUPPORTED_STATEMENT,
            message,
        )

    def _add_warning(self, code: DiagnosticCode, message: str) -> None:
        if len(self.diagnostics) >= self.limits.max_diagnostics:
            return
        self.diagnostics.append(
            ParseDiagnostic(
                severity=DiagnosticSeverity.WARNING,
                code=code,
                message=message,
                statement_index=self.statement_index,
                line=self.start_line,
                column=self.start_column,
                recoverable=True,
            )
        )

    def _resolve_dialect(self, override: SchemaDialect | None) -> SchemaDialect:
        if override is not None and any(item != override for item in self.evidence):
            self._fatal(DiagnosticCode.DIALECT_CONFLICT, "Dialect override conflicts with dump evidence")
        if len(self.evidence) > 1:
            self._fatal(DiagnosticCode.DIALECT_CONFLICT, "SQL dump contains mixed dialect evidence")
        if override is not None:
            return override
        if len(self.evidence) != 1:
            self._fatal(DiagnosticCode.DIALECT_AMBIGUOUS, "SQL dump dialect cannot be determined")
        return next(iter(self.evidence))

    def _remove_buffer_suffix(self, count: int) -> None:
        for _ in range(min(count, len(self.buffer))):
            removed = self.buffer.pop()
            self.buffer_bytes -= len(removed.encode("utf-8"))
        for _ in range(min(count, len(self.preview))):
            self.preview.pop()
        if not self.buffer and self.category is None:
            self.start_line = None
            self.start_column = None

    def _reset_statement(self) -> None:
        self.category = None
        self.kind = None
        self.start_line = None
        self.start_column = None
        self.nesting_depth = 0
        self.neutral_previous = ""
        self.terminator_tail = ""
        self.buffer_bytes = 0
        self.buffer.clear()
        self.preview.clear()
        self.control_preview.clear()
        self.lexical_tail = ""

    def _advance(self, character: str) -> None:
        if character == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1

    def _fatal(self, code: DiagnosticCode, message: str) -> None:
        raise SqlDumpScanError(
            ParseDiagnostic(
                severity=DiagnosticSeverity.ERROR,
                code=code,
                message=message,
                statement_index=self.statement_index,
                line=self.line,
                column=self.column,
                recoverable=False,
            )
        )


async def scan_sql_dump(
    chunks: AsyncIterable[bytes],
    filename: str,
    limits: ScannerLimits | None = None,
    dialect_override: SchemaDialect | None = None,
) -> ScanResult:
    """Scan bounded UTF-8 chunks and return safe core DDL candidates."""
    effective_limits = limits or ScannerLimits.configured()
    _validate_extension(filename)
    scanner = _DumpScanner(effective_limits)
    decoder = codecs.getincrementaldecoder("utf-8-sig")("strict")
    total_bytes = 0
    decoded_characters = 0
    try:
        async for chunk in chunks:
            total_bytes += len(chunk)
            _validate_file_size(total_bytes, effective_limits)
            decoded = decoder.decode(chunk, final=False)
            decoded_characters += len(decoded)
            scanner.feed(decoded)
        final_text = decoder.decode(b"", final=True)
        decoded_characters += len(final_text)
        scanner.feed(final_text)
    except UnicodeDecodeError as error:
        raise _scan_error(DiagnosticCode.INVALID_ENCODING, "SQL dump must be valid UTF-8") from error
    if decoded_characters == 0:
        raise _scan_error(DiagnosticCode.EMPTY_FILE, "SQL dump is empty")
    return scanner.finish(total_bytes, dialect_override)
