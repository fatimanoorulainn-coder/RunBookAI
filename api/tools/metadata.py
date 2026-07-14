"""
Database metadata lookup tools.

Provides service health information for the investigation agent.
"""

from typing import Any


def query_service_metadata(
    cursor,
    service_name: str,
) -> dict[str, Any]:
    """
    Retrieve complete health snapshot for a service.

    Joins:
    - services
    - deployments
    - pods

    Args:
        cursor:
            Active psycopg2 cursor.

        service_name:
            Name of the service.

    Returns:
        Dictionary containing service health information.

    Raises:
        ValueError:
            If service does not exist.
    """

    query = """
        SELECT
            s.id AS service_id,
            s.name AS service_name,
            s.namespace,
            s.owner_team,

            d.id AS deployment_id,
            d.name AS deployment_name,
            d.replicas_expected,
            d.replicas_available,
            d.status AS deployment_status,

            p.name AS pod_name,
            p.phase AS pod_phase,
            p.restart_count,
            p.status_reason

        FROM services s

        LEFT JOIN deployments d
            ON s.id = d.service_id

        LEFT JOIN pods p
            ON d.id = p.deployment_id

        WHERE s.name = %s;
    """

    cursor.execute(query, (service_name,))

    rows = cursor.fetchall()

    if not rows:
        raise ValueError(
            f"Service '{service_name}' does not exist"
        )

    service = {
        "service_name": rows[0][1],
        "namespace": rows[0][2],
        "owner_team": rows[0][3],
        "deployment": {
            "id": rows[0][4],
            "name": rows[0][5],
            "replicas_expected": rows[0][6],
            "replicas_available": rows[0][7],
            "status": rows[0][8],
        },
        "pods": [],
    }

    for row in rows:
        service["pods"].append(
            {
                "name": row[9],
                "phase": row[10],
                "restart_count": row[11],
                "reason": row[12],
            }
        )

    return service