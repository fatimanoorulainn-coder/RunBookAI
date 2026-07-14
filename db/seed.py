"""
RunbookAI Database Seeder

Creates deterministic mock infrastructure data for:
- services
- deployments
- pods

The dataset intentionally contains multiple incidents (for the Day 10 benchmark):
- checkout-service : CrashLoopBackOff pods, port-bind conflict  -> Degraded
- payment-service  : ImagePullBackOff, bad image tag            -> Degraded
- inventory-service: OOMKilled pods, memory limit               -> Degraded
- notification-service: healthy metadata BUT error logs         -> contradiction case (stays Healthy)
- user-service     : fully healthy control                      -> Healthy
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Dict

import psycopg2
from psycopg2.extensions import connection, cursor


# ============================================================
# Logging Configuration
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# ============================================================
# Configuration
# ============================================================

@dataclass(frozen=True)
class DatabaseConfig:
    """
    PostgreSQL configuration.

    Values should come from environment variables.
    """

    host: str
    port: int
    database: str
    user: str
    password: str

    @classmethod
    def from_environment(cls) -> "DatabaseConfig":
        return cls(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            database=os.getenv("DB_NAME", "runbookai"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
        )


# ============================================================
# Database Connection Manager
# ============================================================

class DatabaseConnection:
    """
    Handles PostgreSQL connection lifecycle.
    """

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.connection: connection | None = None

    def __enter__(self) -> connection:
        self.connection = psycopg2.connect(
            host=self.config.host,
            port=self.config.port,
            database=self.config.database,
            user=self.config.user,
            password=self.config.password,
        )

        logger.info("Connected to PostgreSQL")

        return self.connection

    def __exit__(self, exc_type, exc_value, traceback):

        if self.connection:

            if exc_type:
                self.connection.rollback()
                logger.error(
                    "Transaction rolled back due to error"
                )
            else:
                self.connection.commit()
                logger.info(
                    "Transaction committed successfully"
                )

            self.connection.close()
            logger.info(
                "Database connection closed"
            )


# ============================================================
# Repository Layer
# ============================================================

class SeedRepository:
    """
    Handles database persistence operations.
    """

    def __init__(self, db_cursor: cursor):
        self.cursor = db_cursor


    def create_service(
        self,
        name: str,
        namespace: str,
        owner_team: str,
    ) -> int:

        query = """
        INSERT INTO services(
            name,
            namespace,
            owner_team
        )
        VALUES (%s, %s, %s)

        ON CONFLICT(name)
        DO UPDATE SET
            namespace = EXCLUDED.namespace,
            owner_team = EXCLUDED.owner_team

        RETURNING id;
        """

        self.cursor.execute(
            query,
            (
                name,
                namespace,
                owner_team,
            ),
        )

        return self.cursor.fetchone()[0]


    def create_deployment(
        self,
        service_id: int,
        name: str,
        expected: int,
        available: int,
        status: str,
    ) -> int:

        query = """
        INSERT INTO deployments(
            service_id,
            name,
            replicas_expected,
            replicas_available,
            status
        )
        VALUES (%s,%s,%s,%s,%s)

        RETURNING id;
        """

        self.cursor.execute(
            query,
            (
                service_id,
                name,
                expected,
                available,
                status,
            ),
        )

        return self.cursor.fetchone()[0]


    def create_pod(
        self,
        deployment_id: int,
        name: str,
        phase: str,
        restart_count: int,
        reason: str | None,
    ):

        query = """
        INSERT INTO pods(
            deployment_id,
            name,
            phase,
            restart_count,
            status_reason
        )
        VALUES (%s,%s,%s,%s,%s);
        """

        self.cursor.execute(
            query,
            (
                deployment_id,
                name,
                phase,
                restart_count,
                reason,
            ),
        )


# ============================================================
# Business Logic Layer
# ============================================================

class SeedService:
    """
    Creates the infrastructure dataset.
    """

    SERVICES = [
        (
            "checkout-service",
            "production",
            "payments-team",
        ),
        (
            "user-service",
            "production",
            "identity-team",
        ),
        (
            "payment-service",
            "production",
            "payments-team",
        ),
        (
            "inventory-service",
            "production",
            "warehouse-team",
        ),
        (
            "notification-service",
            "production",
            "platform-team",
        ),
    ]


    def __init__(self, repository: SeedRepository):
        self.repository = repository


    def seed(self):

        logger.info("Starting database seed")

        service_ids: Dict[str, int] = {}

        # -----------------------------
        # Services
        # -----------------------------

        for (
            name,
            namespace,
            owner,
        ) in self.SERVICES:

            service_id = (
                self.repository.create_service(
                    name,
                    namespace,
                    owner,
                )
            )

            service_ids[name] = service_id

            logger.info(
                "Created service: %s",
                name,
            )


        # -----------------------------
        # Deployments
        # -----------------------------

        deployments = {}

        deployment_data = {

            # INCIDENT 1: port-bind conflict -> crashloop -> degraded
            "checkout-service": (
                "checkout-v2",
                5,
                2,
                "Degraded",
            ),

            # HEALTHY CONTROL: nothing wrong here
            "user-service": (
                "user-v1",
                3,
                3,
                "Healthy",
            ),

            # INCIDENT 2: bad image tag -> ImagePullBackOff -> degraded
            "payment-service": (
                "payment-v3",
                4,
                1,
                "Degraded",
            ),

            # INCIDENT 3: OOMKilled -> zero available -> degraded
            "inventory-service": (
                "inventory-v1",
                2,
                0,
                "Degraded",
            ),

            # INCIDENT 4 (contradiction): metadata Healthy, but error logs exist
            "notification-service": (
                "notification-v1",
                3,
                3,
                "Healthy",
            ),
        }


        for service, data in deployment_data.items():

            deployment_id = (
                self.repository.create_deployment(
                    service_ids[service],
                    *data,
                )
            )

            deployments[service] = deployment_id

            logger.info(
                "Created deployment: %s",
                data[0],
            )


        # -----------------------------
        # Pods
        # -----------------------------

        pods = [

            # checkout-service: crashlooping (port-bind conflict)
            (
                "checkout-service",
                "checkout-v2-x1",
                "Failed",
                8,
                "CrashLoopBackOff",
            ),

            (
                "checkout-service",
                "checkout-v2-x2",
                "Failed",
                5,
                "CrashLoopBackOff",
            ),

            # user-service: healthy control
            (
                "user-service",
                "user-v1-x1",
                "Running",
                0,
                None,
            ),

            # payment-service: bad image tag
            (
                "payment-service",
                "payment-v3-x1",
                "Failed",
                6,
                "ImagePullBackOff",
            ),

            # inventory-service: OOMKilled
            (
                "inventory-service",
                "inventory-v1-x1",
                "Failed",
                7,
                "OOMKilled",
            ),

            # notification-service: pod looks fine (contradiction with error logs)
            (
                "notification-service",
                "notification-v1-x1",
                "Running",
                0,
                None,
            ),
        ]


        for (
            service,
            name,
            phase,
            restarts,
            reason,
        ) in pods:

            self.repository.create_pod(
                deployments[service],
                name,
                phase,
                restarts,
                reason,
            )

            logger.info(
                "Created pod: %s",
                name,
            )


        logger.info(
            "Database seed completed"
        )


# ============================================================
# Entry Point
# ============================================================

def main():

    config = DatabaseConfig.from_environment()

    with DatabaseConnection(config) as db:

        cursor = db.cursor()

        repository = SeedRepository(cursor)

        service = SeedService(repository)

        service.seed()


if __name__ == "__main__":
    main()