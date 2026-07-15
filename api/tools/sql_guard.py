"""Validate LLM-generated SQL before it touches the database (Day 16/17).

Treat the model's SQL as hostile. It passes ONLY if it is a single read-only
SELECT over the allowed tables. Everything else is rejected. Pure stdlib.
"""
from __future__ import annotations
import re

ALLOWED_TABLES = {"services", "deployments", "pods"}

_FORBIDDEN = {
    "insert", "update", "delete", "drop", "alter", "create", "truncate",
    "grant", "revoke", "merge", "replace", "call", "exec", "execute",
    "copy", "attach", "vacuum", "into", "commit", "rollback", "savepoint",
    "pg_sleep", "pg_read_file", "pg_ls_dir", "dblink", "lo_import", "lo_export",
}
_COMMENT = re.compile(r"--[^\n]*|/\*.*?\*/", re.DOTALL)
_WORD = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")
_TABLE_AFTER = re.compile(r"\b(?:from|join)\s+([A-Za-z_][A-Za-z_0-9\.]*)", re.IGNORECASE)


class UnsafeSQL(ValueError):
    """Raised when generated SQL fails validation."""


def validate_select(sql: str, allowed: set[str] = ALLOWED_TABLES) -> str:
    if not sql or not sql.strip():
        raise UnsafeSQL("empty query")
    clean = _COMMENT.sub(" ", sql).strip().rstrip(";").strip()
    if ";" in clean:
        raise UnsafeSQL("multiple statements are not allowed")
    if not clean.lower().startswith("select"):
        raise UnsafeSQL(f"query must start with SELECT: {clean[:20]!r}")
    hit = {w.lower() for w in _WORD.findall(clean)} & _FORBIDDEN
    if hit:
        raise UnsafeSQL(f"forbidden keyword(s): {sorted(hit)}")
    tables = {t.split(".")[-1].lower() for t in _TABLE_AFTER.findall(clean)}
    if not tables:
        raise UnsafeSQL("no table referenced")
    bad = tables - allowed
    if bad:
        raise UnsafeSQL(f"table(s) not in ALLOWED_TABLES: {sorted(bad)}")
    return clean


# ---- Day 17: row-count cap ----
MAX_ROWS = 500

def enforce_limit(sql: str, max_rows: int = MAX_ROWS) -> str:
    """Append a LIMIT if the query has none, so a generated SELECT can't drag
    back an unbounded result set. Idempotent — leaves an existing LIMIT alone."""
    if re.search(r"\blimit\b", sql, re.IGNORECASE):
        return sql
    return f"{sql.rstrip().rstrip(';').rstrip()} LIMIT {int(max_rows)}"