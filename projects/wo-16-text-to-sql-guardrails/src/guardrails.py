"""Static SQL checks and read-only SQLite execution controls."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import sqlglot
from sqlglot import exp

MAX_LIMIT = 10_000
MAX_VM_STEPS = 20_000_000
PROGRESS_INTERVAL = 1_000
DENIED_FUNCTIONS = {"load_extension", "readfile", "writefile"}


@dataclass(frozen=True)
class GuardResult:
    """Outcome of static validation before a query reaches SQLite."""

    accepted: bool
    sql: str | None
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]


def validate_sql(sql: str, dialect: str = "sqlite") -> GuardResult:
    """Allow a single SELECT statement and cap its returned rows."""
    try:
        statements = sqlglot.parse(sql, read=dialect)
    except sqlglot.errors.ParseError as exc:
        return GuardResult(False, None, (f"syntax_error: {exc.errors[0]['description']}",), ())
    if len(statements) != 1 or statements[0] is None:
        return GuardResult(False, None, ("exactly_one_statement_required",), ())
    tree = statements[0]
    if not isinstance(tree, exp.Query):
        return GuardResult(False, None, ("select_only",), ())
    functions = {node.name.lower() for node in tree.find_all(exp.Func)}
    denied = sorted(functions & DENIED_FUNCTIONS)
    if denied:
        return GuardResult(False, None, (f"denied_function: {','.join(denied)}",), ())
    warnings: list[str] = []
    if tree.args.get("limit") is None:
        tree = tree.limit(MAX_LIMIT)
        warnings.append(f"limit_added:{MAX_LIMIT}")
    elif tree.args["limit"].expression and tree.args["limit"].expression.is_number:
        requested = int(tree.args["limit"].expression.this)
        if requested > MAX_LIMIT:
            tree.set("limit", exp.Limit(expression=exp.Literal.number(MAX_LIMIT)))
            warnings.append(f"limit_capped:{requested}->{MAX_LIMIT}")
    else:
        warnings.append("non_literal_limit_review")
    if not any(tree.find_all(exp.Where)):
        warnings.append("no_where_clause_possible_full_scan")
    return GuardResult(True, tree.sql(dialect=dialect), (), tuple(warnings))


def readonly_connection(database: Path, vm_budget: int = MAX_VM_STEPS) -> sqlite3.Connection:
    """Open a SQLite database read-only and abort pathological virtual-machine work."""
    uri = f"file:{database.resolve().as_posix()}?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True, timeout=2.0)
    connection.execute("PRAGMA query_only = ON")
    remaining = [vm_budget]

    def progress() -> int:
        remaining[0] -= PROGRESS_INTERVAL
        return int(remaining[0] <= 0)

    connection.set_progress_handler(progress, PROGRESS_INTERVAL)

    def authorizer(action: int, arg1: str | None, arg2: str | None,
                   database_name: str | None, source: str | None) -> int:
        allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION,
                   sqlite3.SQLITE_RECURSIVE}
        if action in allowed:
            if action == sqlite3.SQLITE_FUNCTION and (arg2 or arg1 or "").lower() in DENIED_FUNCTIONS:
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY

    connection.set_authorizer(authorizer)
    return connection


def validate_schema(database: Path, sql: str) -> None:
    """Compile a read-only query so SQLite rejects unknown tables and columns."""
    with closing(readonly_connection(database)) as connection:
        connection.execute(f"EXPLAIN QUERY PLAN {sql}").fetchall()


def execute_sql(database: Path, sql: str) -> tuple[list[tuple[Any, ...]], list[str]]:
    """Execute SQL on a read-only connection and return rows plus column names."""
    with closing(readonly_connection(database)) as connection:
        cursor = connection.execute(sql)
        rows = cursor.fetchmany(MAX_LIMIT + 1)
        if len(rows) > MAX_LIMIT:
            raise sqlite3.DataError(f"result_row_cap_exceeded:{MAX_LIMIT}")
        columns = [item[0] for item in cursor.description or ()]
    return rows, columns


def explain_warnings(database: Path, sql: str) -> tuple[str, ...]:
    """Return full-scan table warnings from SQLite's query planner."""
    with closing(readonly_connection(database)) as connection:
        details = [str(row[3]) for row in connection.execute(f"EXPLAIN QUERY PLAN {sql}")]
    return tuple(f"full_scan:{detail}" for detail in details if "SCAN " in detail.upper()
                 and "USING INDEX" not in detail.upper())
