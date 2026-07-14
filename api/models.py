"""
RunBookAI Data Models

Week 2 Day 6 (+ Day 8 updates):
- Structured evidence objects
- Finding (LLM output) vs Investigation (enriched final)
- Agent trace schema
- Tool definitions incl. submit_finding
"""

from enum import Enum
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


# =====================================================
# Enums
# =====================================================


class EvidenceSource(str, Enum):
    METADATA = "metadata"
    LOGS = "logs"
    RUNBOOKS = "runbooks"


class InvestigationStatus(str, Enum):
    RESOLVED = "resolved"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


# =====================================================
# Evidence
# =====================================================


class Evidence(BaseModel):
    """A single piece of evidence discovered by tools."""

    source: EvidenceSource
    content: str = Field(min_length=1, description="Actual evidence content")
    timestamp: datetime | str


# =====================================================
# Finding  (what the LLM submits)
# =====================================================


class Finding(BaseModel):
    """
    The model's raw conclusion, submitted via submit_finding.

    Deliberately has NO confidence_score. The model never scores itself —
    confidence.py does that from the collected evidence.
    """

    root_cause: str
    status: InvestigationStatus
    missing_evidence: list[str] = Field(default_factory=list)


# =====================================================
# Investigation  (enriched final object)
# =====================================================


class Investigation(BaseModel):
    """
    Final conclusion = Finding + deterministic confidence.
    """

    root_cause: str
    status: InvestigationStatus
    confidence_score: float = Field(ge=0.0, le=1.0)
    missing_evidence: list[str] = Field(default_factory=list)

    @classmethod
    def from_finding(cls, finding: "Finding", confidence_score: float) -> "Investigation":
        return cls(
            root_cause=finding.root_cause,
            status=finding.status,
            confidence_score=confidence_score,
            missing_evidence=finding.missing_evidence,
        )


# =====================================================
# Investigation Trace
# =====================================================


class InvestigationTrace(BaseModel):
    """Records every step performed by the agent."""

    step_number: int = Field(ge=1)
    tool_name: str
    tool_input: dict[str, Any]
    tool_output: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)  # utcnow() is deprecated
    )
    latency_ms: float | None = None


# =====================================================
# Agent Tool Schemas
# =====================================================


QUERY_SERVICE_METADATA_TOOL = {
    "type": "function",
    "function": {
        "name": "query_service_metadata",
        "description": "Retrieve deployment and pod health information for a service.",
        "parameters": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "Name of the service to investigate",
                }
            },
            "required": ["service_name"],
        },
    },
}


SEARCH_LOGS_TOOL = {
    "type": "function",
    "function": {
        "name": "search_logs",
        "description": "Search application logs for errors or patterns.",
        "parameters": {
            "type": "object",
            "properties": {
                "service_name": {"type": "string"},
                "pattern": {"type": "string"},
            },
            "required": ["service_name", "pattern"],
        },
    },
}


SEARCH_RUNBOOKS_TOOL = {
    "type": "function",
    "function": {
        "name": "search_runbooks",
        "description": "Search SRE runbooks for troubleshooting guidance.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
}


# NEW — the model's ONLY way to end the investigation.
# Note: no confidence_score field. The model must not score itself.
SUBMIT_FINDING_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_finding",
        "description": (
            "Submit the final conclusion. This is the ONLY way to end the "
            "investigation. Do NOT report a confidence score — confidence is "
            "computed separately."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "root_cause": {
                    "type": "string",
                    "description": "The identified root cause of the incident.",
                },
                "status": {
                    "type": "string",
                    "enum": ["resolved", "insufficient_evidence"],
                    "description": (
                        "resolved if a root cause was found, "
                        "insufficient_evidence otherwise."
                    ),
                },
                "missing_evidence": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Evidence that would have helped but was unavailable.",
                },
            },
            "required": ["root_cause", "status"],
        },
    },
}