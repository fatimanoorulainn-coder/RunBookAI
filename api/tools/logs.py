"""
Log searching utilities.

Used by the investigation agent to search raw SRE logs.
"""

from pathlib import Path
import re


LOG_FILE = (
    Path(__file__)
    .parent
    .parent
    .parent
    / "data"
    / "logs"
    / "openstack_sandbox.log"
)


def search_logs(
    service_name: str,
    pattern: str,
) -> list[str]:
    """
    Search logs for a service and regex pattern.

    Args:
        service_name:
            Service identifier.

        pattern:
            Regex keyword/pattern.

    Returns:
        Matching log lines.
    """

    if not LOG_FILE.exists():
        raise FileNotFoundError(
            f"Log file missing: {LOG_FILE}"
        )

    matches = []

    regex = re.compile(
        pattern,
        re.IGNORECASE,
    )

    with LOG_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:

        for line in file:
            if service_name.lower() not in line.lower():
                continue

            if regex.search(line):
                matches.append(
                    line.strip()
                )

    return matches