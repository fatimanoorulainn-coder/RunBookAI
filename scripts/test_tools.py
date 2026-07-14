"""
Manual verification of RunBookAI investigation tools.
"""

import sys
from pathlib import Path


# Allow imports from project root
sys.path.append(
    str(Path(__file__).parent.parent)
)


import psycopg2

from api.tools.metadata import (
    query_service_metadata,
)

from api.tools.logs import (
    search_logs,
)


def main():

    print("\n=== Testing Database Tool ===")

    connection = psycopg2.connect(
        host="localhost",
        port=5432,
        database="runbookai",
        user="postgres",
        password="potty123",
    )

    cursor = connection.cursor()

    metadata = query_service_metadata(
        cursor,
        "checkout-service",
    )

    print(metadata)

    cursor.close()
    connection.close()


    print("\n=== Testing Log Tool ===")

    logs = search_logs(
        "checkout-service",
        "Connection refused|Failed|timeout",
    )

    for log in logs:
        print(log)


if __name__ == "__main__":
    main()