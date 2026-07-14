from api.models import (
    Evidence,
    EvidenceSource,
    Investigation,
    InvestigationStatus,
    InvestigationTrace
)


evidence = Evidence(
    source=EvidenceSource.LOGS,
    content="checkout-service returned 503",
    timestamp="2026-07-14"
)


print(evidence)


investigation = Investigation(
    root_cause="Database connection failure",
    status=InvestigationStatus.RESOLVED,
    confidence_score=0.8
)


print(investigation)


trace = InvestigationTrace(
    step_number=1,
    tool_name="search_logs",
    tool_input={
        "service_name":"checkout-service",
        "pattern":"503"
    },
    tool_output="Found 503 errors"
)


print(trace)