"""Database metadata lookup .

Flow: model generates a parameterized SELECT -> sql_guard validates it ->
execute read-only with a bound service_name -> parse results BY COLUMN NAME
(robust to column reordering). Any failure falls back to a trusted static
query, so a bad LLM turn degrades to "still works", never "incident breaks".
"""
from typing import Any

from api.tools.sql_gen import (
    generate_metadata_sql, STATIC_SQL, REQUIRED_COLUMNS,
)
from api.tools.sql_guard import validate_select, enforce_limit, UnsafeSQL


def _run(cursor, sql: str, service_name: str) -> list[dict]:
    """Execute a validated SELECT and return rows as dicts keyed by column name."""
    cursor.execute(enforce_limit(sql), {"service_name": service_name})
    columns = [d[0] for d in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _build(rows: list[dict]) -> dict[str, Any]:
    first = rows[0]
    return {
        "service_name": first["service_name"],
        "namespace": first["namespace"],
        "owner_team": first["owner_team"],
        "deployment": {
            "id": first["deployment_id"],
            "name": first["deployment_name"],
            "replicas_expected": first["replicas_expected"],
            "replicas_available": first["replicas_available"],
            "status": first["deployment_status"],
        },
        "pods": [
            {
                "name": r["pod_name"],
                "phase": r["pod_phase"],
                "restart_count": r["restart_count"],
                "reason": r["status_reason"],
            }
            for r in rows if r["pod_name"] is not None
        ],
    }


def query_service_metadata(cursor, service_name: str) -> dict[str, Any]:
    """Retrieve a service health snapshot. Same return shape as before."""
    rows = None

    # 1. try the model-generated, validated query
    try:
        sql = validate_select(generate_metadata_sql())
        rows = _run(cursor, sql, service_name)
        if rows and not all(c in rows[0] for c in REQUIRED_COLUMNS):
            rows = None                       # missing an expected alias -> distrust
    except (UnsafeSQL, Exception):
        # a bad/failed query can leave the transaction aborted; clear it
        try:
            cursor.connection.rollback()
        except Exception:
            pass
        rows = None

    # 2. trusted static fallback
    if rows is None:
        rows = _run(cursor, STATIC_SQL, service_name)

    if not rows:
        raise ValueError(f"Service '{service_name}' does not exist")

    return _build(rows)