"""
RunBookAI FastAPI Application

Week 1:
- Database-backed investigations
- Manual diagnostic tools
- Investigation trace persistence
Week 5 Day 21:
- Agent-backed /investigate endpoint returning investigation + traces + evidence
- CORS for the Next.js dev server
"""

import uuid
import json
import logging
import os
from datetime import datetime

import psycopg2
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from api.tools.metadata import query_service_metadata
from api.tools.logs import search_logs
from api.agent import run_investigation


# -------------------------------------------------
# Logging
# -------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("runbookai")


# -------------------------------------------------
# Database config
# -------------------------------------------------

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "database": os.getenv("DB_NAME", "runbookai"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
}


def get_connection():
    """
    Create database connection.

    Production:
    replace with connection pooling.
    """

    return psycopg2.connect(**DB_CONFIG)


# -------------------------------------------------
# FastAPI
# -------------------------------------------------

app = FastAPI(
    title="RunBookAI API",
    version="1.0.0",
)

# Allow the Next.js dev server (localhost:3000) to call this API from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------------------------
# Schemas
# -------------------------------------------------

class InvestigationRequest(BaseModel):
    service_name: str = Field(
        min_length=2,
        max_length=100,
    )

    question: str = Field(
        min_length=5,
        max_length=500,
    )


class InvestigationResponse(BaseModel):
    investigation_id: str
    status: str
    root_cause: str
    confidence_score: float
    steps: list[str]


# Week 5: the agent endpoint only needs a free-text question.
class AgentInvestigateRequest(BaseModel):
    question: str = Field(min_length=5, max_length=500)


# -------------------------------------------------
# Database helpers
# -------------------------------------------------

def create_investigation(
    cursor,
    service_name: str,
) -> str:

    investigation_id = str(uuid.uuid4())

    cursor.execute(
        """
        INSERT INTO investigations
        (
            id,
            service_name,
            status
        )
        VALUES
        (
            %s,
            %s,
            'running'
        )
        RETURNING id;
        """,
        (
            investigation_id,
            service_name,
        ),
    )

    return investigation_id



def save_trace(
    cursor,
    investigation_id: str,
    step_number: int,
    tool_name: str,
    tool_input: dict,
    tool_output: dict | list,
):
    """
    Persist investigation step.

    JSON columns require valid JSON.
    """

    cursor.execute(
        """
        INSERT INTO investigation_traces
        (
            investigation_id,
            step_number,
            timestamp,
            tool_name,
            tool_input,
            tool_output
        )
        VALUES
        (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s
        );
        """,
        (
            investigation_id,
            step_number,
            datetime.utcnow(),
            tool_name,
            json.dumps(tool_input),
            json.dumps(tool_output),
        ),
    )


# -------------------------------------------------
# Routes
# -------------------------------------------------

@app.get("/health")
def health():

    try:

        with get_connection() as conn:

            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT 1;"
                )

        return {
            "status": "ok",
            "database": "connected",
        }

    except Exception:

        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        )


# Week 5: agent-backed endpoint the frontend calls.
# Returns the full investigation (incl. evidence) + the execution trace.
@app.post("/investigate")
def investigate_agent(request: AgentInvestigateRequest):

    logger.info("Agent investigation: %s", request.question)

    try:
        investigation, traces = run_investigation(request.question)
    except Exception:
        logger.exception("Agent investigation failed")
        raise HTTPException(status_code=500, detail="Investigation failed")

    return {
        "investigation": investigation.model_dump(mode="json"),
        "traces": [t.model_dump(mode="json") for t in traces],
    }


@app.post(
    "/api/v1/investigate",
    response_model=InvestigationResponse,
)
def investigate(
    request: InvestigationRequest,
):

    logger.info(
        "Starting investigation for %s",
        request.service_name,
    )

    try:

        with get_connection() as conn:

            with conn.cursor() as cursor:

                # -------------------------
                # Create investigation
                # -------------------------

                investigation_id = create_investigation(
                    cursor,
                    request.service_name,
                )


                # -------------------------
                # Tool 1: Metadata lookup
                # -------------------------

                metadata = query_service_metadata(
                    cursor,
                    request.service_name,
                )


                save_trace(
                    cursor,
                    investigation_id,
                    1,
                    "query_service_metadata",
                    {
                        "service_name": request.service_name
                    },
                    metadata,
                )


                # -------------------------
                # Tool 2: Log search
                # -------------------------

                logs = search_logs(
                    request.service_name,
                    request.service_name,
                )


                save_trace(
                    cursor,
                    investigation_id,
                    2,
                    "search_logs",
                    {
                        "service_name": request.service_name,
                        "pattern": request.service_name,
                    },
                    logs,
                )


                # -------------------------
                # Create evidence summary
                # -------------------------

                summary = (
                    "Metadata Evidence:\n"
                    f"{json.dumps(metadata, indent=2)}\n\n"
                    "Log Evidence:\n"
                    f"{json.dumps(logs, indent=2)}"
                )


                cursor.execute(
                    """
                    UPDATE investigations
                    SET
                        status='resolved',
                        root_cause=%s
                    WHERE id=%s;
                    """,
                    (
                        summary,
                        investigation_id,
                    ),
                )


                conn.commit()


        return InvestigationResponse(

            investigation_id=investigation_id,

            status="resolved",

            root_cause=summary,

            confidence_score=0.50,

            steps=[
                "query_service_metadata",
                "search_logs",
            ],
        )


    except ValueError as error:

        raise HTTPException(
            status_code=404,
            detail=str(error),
        )


    except Exception:

        logger.exception(
            "Investigation failed"
        )

        raise HTTPException(
            status_code=500,
            detail="Investigation failed",
        )