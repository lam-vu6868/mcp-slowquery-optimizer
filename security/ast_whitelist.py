"""Fail-closed SQL AST whitelist for MySQL queries."""

from __future__ import annotations

import re
from typing import Iterable

from sqlglot import exp, parse_one

_ALLOWED_SYSTEM_SCHEMAS = {"information_schema", "mysql", "performance_schema", "sys"}
_FORBIDDEN_PATTERNS = (
    r"/\*!\s*\d+",
    r"/\*M!",
    r"\bINTO\s+(?:OUTFILE|DUMPFILE)\b",
    r"\bLOAD_FILE\s*\(",
    r"\bFOR\s+UPDATE\b",
    r"\bLOCK\s+IN\s+SHARE\s+MODE\b",
    r"\bSLEEP\s*\(",
    r"\bBENCHMARK\s*\(",
    r"\bGET_LOCK\s*\(",
    r"\bRELEASE_LOCK\s*\(",
)


def _normalize_sql(sql: str) -> str:
    if not isinstance(sql, str):
        raise TypeError("SQL must be a string.")

    normalized = sql.strip()
    if not normalized:
        raise ValueError("SQL cannot be empty.")
    return normalized


def _contains_forbidden_pattern(sql: str) -> bool:
    return any(re.search(pattern, sql, flags=re.IGNORECASE) for pattern in _FORBIDDEN_PATTERNS)


def _table_names(statement: exp.Expression) -> Iterable[str]:
    seen: set[str] = set()
    for table in statement.find_all(exp.Table):
        names = []
        if table.db:
            names.append(table.db)
        if table.name:
            names.append(table.name)
        for name in names:
            normalized = str(name).strip()
            if normalized:
                seen.add(normalized.lower())
    return sorted(seen)


def validate_sql(sql: str, *, allowed_schemas: set[str] | None = None) -> str:
    """Validate and normalize a SQL statement.

    Returns the trimmed SQL string when valid. Raises ValueError on any unsafe payload.
    """

    normalized = _normalize_sql(sql)

    if normalized.count(";") > 0:
        raise ValueError("Only one SQL statement is allowed at a time.")

    if _contains_forbidden_pattern(normalized):
        raise ValueError("SQL contains forbidden execution or lock patterns.")

    try:
        statement = parse_one(normalized, read="mysql")
    except Exception as exc:  # sqlglot raises parser exceptions, so fail closed.
        raise ValueError("Unable to parse SQL safely.") from exc

    if statement is None:
        raise ValueError("No SQL statement found.")

    is_select = isinstance(statement, exp.Select)
    is_explain = normalized.upper().startswith("EXPLAIN ")
    if not is_select and not is_explain:
        raise ValueError("Only SELECT and EXPLAIN statements are permitted.")

    allowed = {str(schema).lower() for schema in (allowed_schemas or set())}
    for table_name in _table_names(statement):
        if table_name in _ALLOWED_SYSTEM_SCHEMAS:
            raise ValueError("Access to system schemas is forbidden.")
        if allowed and table_name not in allowed:
            if "." in table_name:
                schema_name, _, _ = table_name.partition(".")
                if schema_name not in allowed:
                    raise ValueError("Table access is restricted to the allowed schema list.")

    return normalized


def is_allowed_sql(sql: str, *, allowed_schemas: set[str] | None = None) -> bool:
    try:
        validate_sql(sql, allowed_schemas=allowed_schemas)
        return True
    except (TypeError, ValueError):
        return False


validate_statement = validate_sql
is_safe_sql = is_allowed_sql
allowlist_sql = validate_sql
__all__ = [
    "validate_sql",
    "validate_statement",
    "is_allowed_sql",
    "is_safe_sql",
    "allowlist_sql",
]

