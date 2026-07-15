"""Generate a parameterized metadata SELECT from the model .

The model only ever produces a query TEMPLATE with a %(service_name)s
placeholder — it never sees or emits the actual service value, so the value
can't be an injection vector. The result is validated by sql_guard before use.
Generation is cached (the query is identical for every service), so it costs
one Groq call per process, not one per lookup.
"""
from __future__ import annotations
import re
from functools import lru_cache
from groq import Groq
from dotenv import load_dotenv
load_dotenv()

MODEL = "llama-3.3-70b-versatile"

# Downstream code reads these exact aliases. The model is told to produce them.
REQUIRED_COLUMNS = [
    "service_name", "namespace", "owner_team",
    "deployment_id", "deployment_name", "replicas_expected",
    "replicas_available", "deployment_status",
    "pod_name", "pod_phase", "restart_count", "status_reason",
]

SCHEMA_DESCRIPTION = """\
services(id PK, name, namespace, owner_team)
deployments(id PK, service_id -> services.id, name,
            replicas_expected, replicas_available,
            status in ('Healthy','Degraded'))
pods(id PK, deployment_id -> deployments.id, name,
     phase in ('Running','Failed'), restart_count, status_reason)"""

# Trusted, hand-written fallback. Named placeholder, passes sql_guard.
STATIC_SQL = """
SELECT
    s.name              AS service_name,
    s.namespace         AS namespace,
    s.owner_team        AS owner_team,
    d.id                AS deployment_id,
    d.name              AS deployment_name,
    d.replicas_expected AS replicas_expected,
    d.replicas_available AS replicas_available,
    d.status            AS deployment_status,
    p.name              AS pod_name,
    p.phase             AS pod_phase,
    p.restart_count     AS restart_count,
    p.status_reason     AS status_reason
FROM services s
LEFT JOIN deployments d ON s.id = d.service_id
LEFT JOIN pods p ON d.id = p.deployment_id
WHERE s.name = %(service_name)s
""".strip()

_PROMPT = f"""You generate ONE PostgreSQL query and nothing else.

Schema:
{SCHEMA_DESCRIPTION}

Write a single SELECT that returns a full health snapshot for one service:
- join services -> deployments -> pods with LEFT JOINs
- filter by the service name using the named placeholder %(service_name)s
  (do NOT inline a literal service name)
- alias the selected columns EXACTLY as, and only as, these names:
  {', '.join(REQUIRED_COLUMNS)}

Return ONLY the SQL. No markdown, no backticks, no explanation, no semicolon."""

_FENCE = re.compile(r"^```(?:sql)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def _clean(text: str) -> str:
    return _FENCE.sub("", text).strip().rstrip(";").strip()


@lru_cache(maxsize=1)
def generate_metadata_sql() -> str:
    """One cached Groq call -> a metadata SELECT template (unvalidated)."""
    client = Groq()
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": _PROMPT}],
        temperature=0,
    )
    return _clean(resp.choices[0].message.content or "")