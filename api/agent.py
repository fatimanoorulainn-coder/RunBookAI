"""
api/agent.py — Week 2 Day 9 agent loop.

- model calls tools in a loop (Groq / OpenAI-compatible tool calling)
- hard step budget with forced termination
- duplicate-call detection (same tool + near-identical args)
- submit_finding is the ONLY way to return a final answer
- confidence is computed deterministically AFTER the model submits
- Day 9: abstention — a FORCED stop with low confidence is downgraded to
  insufficient_evidence instead of presenting a best guess. Empty tool
  results do NOT count as evidence, so a no-data run scores near zero.
"""

import json
import time
from groq import Groq, BadRequestError
from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv()

from groq import Groq

from api.models import (
    Evidence,
    EvidenceSource,
    Finding,
    Investigation,
    InvestigationStatus,
    InvestigationTrace,
    QUERY_SERVICE_METADATA_TOOL,
    SEARCH_LOGS_TOOL,
    SEARCH_RUNBOOKS_TOOL,
    SUBMIT_FINDING_TOOL,
)
from api.confidence import calculate_confidence, detect_contradiction

from api.tools import query_service_metadata, search_logs, search_runbooks

import psycopg2

MODEL = "llama-3.3-70b-versatile"  
MAX_STEPS = 6
CONFIDENCE_THRESHOLD = 0.4   # below this at a FORCED stop => abstain, don't guess

client = Groq()

TOOLS = [
    QUERY_SERVICE_METADATA_TOOL,
    SEARCH_LOGS_TOOL,
    SEARCH_RUNBOOKS_TOOL,
    SUBMIT_FINDING_TOOL,
]

# tool name -> (callable, EvidenceSource, needs_cursor)
# needs_cursor=True means the agent injects the DB cursor at call time;
# the LLM only ever supplies the query args (service_name, pattern, ...).
TOOL_REGISTRY = {
    "query_service_metadata": (query_service_metadata, EvidenceSource.METADATA, True),
    "search_logs": (search_logs, EvidenceSource.LOGS, False),
    "search_runbooks": (search_runbooks, EvidenceSource.RUNBOOKS, False),
}

SYSTEM_PROMPT = (
    "You are an SRE incident investigator. ALWAYS gather evidence before "
    "concluding: call query_service_metadata AND search_logs before you call "
    "submit_finding. "
    "Use the tools to gather evidence about the incident. When you have enough "
    "evidence — or are confident no more is available — call submit_finding to "
    "conclude. submit_finding is the ONLY way to finish. Do not report a "
    "confidence score; it is computed separately. If the tools return no "
    "relevant evidence, do NOT guess — set status to insufficient_evidence and "
    "list what was missing."
    "When logs contain a specific error (port bind failure, OOMKilled, "
    "ImagePullBackOff, connection pool exhausted), you MUST name that specific "
    "error as the root cause and set status=resolved. Do not abstain when a "
    "concrete error is present in the evidence."
)

FORCE_TERMINATION_MSG = (
    "Step budget reached (or a duplicate call was detected). You must call "
    "submit_finding NOW with whatever you have. If the evidence is insufficient, "
    "set status to insufficient_evidence."
)


def _safe_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}


def _arg_signature(name: str, raw_args: str) -> str:
    """Normalise args so {'a':1,'b':2} and {'b':2,'a':1} collide."""
    return name + "::" + json.dumps(_safe_json(raw_args), sort_keys=True)


def _finalize(args: dict, evidence: list[Evidence], forced: bool = False) -> Investigation:
    finding = Finding(
        root_cause=args.get("root_cause", ""),
        status=InvestigationStatus(args.get("status", "insufficient_evidence")),
        missing_evidence=args.get("missing_evidence", []),
    )
    score = calculate_confidence(
        evidence_sources=[e.source.value for e in evidence],
        evidence_count=len(evidence),
        contradiction=detect_contradiction(evidence),
    )
    # Day 9: a forced stop with low confidence must abstain, not present a best guess.
    if forced and score < CONFIDENCE_THRESHOLD:
        finding.status = InvestigationStatus.INSUFFICIENT_EVIDENCE
        if not finding.missing_evidence:
            finding.missing_evidence = ["Confidence below threshold at step budget."]
    return Investigation.from_finding(finding, score)


def _fallback(evidence: list[Evidence]) -> Investigation:
    score = calculate_confidence(
        evidence_sources=[e.source.value for e in evidence],
        evidence_count=len(evidence),
        contradiction=detect_contradiction(evidence),
    )
    return Investigation(
        root_cause="No conclusion reached within step budget.",
        status=InvestigationStatus.INSUFFICIENT_EVIDENCE,
        confidence_score=score,
        missing_evidence=["Investigation exceeded step budget before submit_finding."],
    )


def run_investigation(question: str) -> tuple[Investigation, list[InvestigationTrace]]:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    evidence: list[Evidence] = []
    traces: list[InvestigationTrace] = []
    seen_calls: set[str] = set()

    # One DB connection for the whole investigation; injected into tools that need it.
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="runbookai",
        user="postgres",
        password="potty123",
    )
    cursor = conn.cursor()
    try:
        for step in range(1, MAX_STEPS + 1):
            try:
                response = client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    tools=TOOLS,
                    tool_choice="required",   # must call a tool; no free-text answers
                )
            except BadRequestError as exc:
                if "tool_use_failed" in str(exc):
                    messages.append({
                        "role": "system",
                        "content": (
                            "Your previous tool call was malformed. Call the tool "
                            "again using the proper function-calling format."
                        ),
                    })
                    continue
                raise
            msg = response.choices[0].message
            messages.append(msg)

            if not msg.tool_calls:
                messages.append(
                    {"role": "system", "content": "You must call submit_finding to finish."}
                )
                continue

            force_finish = False
            for call in msg.tool_calls:
                name = call.function.name
                raw_args = call.function.arguments
                args = _safe_json(raw_args)

                # ---- the only exit ----
                # ---- the only exit ----
                if name == "submit_finding":
                    # Don't allow a conclusion before ANY evidence was gathered.
                    if not evidence:
                        messages.append({
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": (
                                "Rejected: you have not gathered any evidence yet. "
                                "Call query_service_metadata and search_logs FIRST, "
                                "then submit_finding."
                            ),
                        })
                        continue
                    return _finalize(args, evidence), traces
                    # voluntary finish: trust the model (forced defaults to False)
                    

                # ---- duplicate-call detection ----
                signature = _arg_signature(name, raw_args)
                if signature in seen_calls:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": (
                            "Duplicate call ignored — you already ran this exact query. "
                            "Use different evidence or call submit_finding."
                        ),
                    })
                    force_finish = True
                    continue
                seen_calls.add(signature)

                # ---- execute a real tool ----
                fn, source, needs_cursor = TOOL_REGISTRY[name]
                call_kwargs = dict(args)              # LLM-supplied args
                if needs_cursor:
                    call_kwargs["cursor"] = cursor     # code-supplied infrastructure arg

                start = time.perf_counter()
                try:
                    output = fn(**call_kwargs)
                except Exception:                      # missing service, bad args, etc.
                    output = ""                         # treat a failed tool as no evidence
                latency_ms = (time.perf_counter() - start) * 1000
                output_str = output if isinstance(output, str) else json.dumps(output)

                # Day 9: only real results count toward confidence. Empty list/dict/
                # string or None is NOT evidence — otherwise a no-data run looks confident.
                is_empty = output is None or (
                    isinstance(output, (list, dict, str)) and len(output) == 0
                )
                if not is_empty:
                    evidence.append(Evidence(
                        source=source,
                        content=output_str,
                        timestamp=datetime.now(timezone.utc),
                    ))

                # trace + message ALWAYS happen, so the model still sees "nothing found"
                traces.append(InvestigationTrace(
                    step_number=step,
                    tool_name=name,
                    tool_input=args,                   # log only LLM args, not the cursor
                    tool_output=output_str,
                    latency_ms=latency_ms,
                ))
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": output_str or "(no results found)",
                })

            # budget hit or duplicate seen -> force a final submit next
            if force_finish or step == MAX_STEPS:
                messages.append({"role": "system", "content": FORCE_TERMINATION_MSG})
                break

        # ---- guaranteed final turn: force submit_finding specifically ----
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice={"type": "function", "function": {"name": "submit_finding"}},
            )
        except BadRequestError:
            return _fallback(evidence), traces
        msg = response.choices[0].message
        if msg.tool_calls:
            args = _safe_json(msg.tool_calls[0].function.arguments)
            # forced finish: apply the abstention threshold
            return _finalize(args, evidence, forced=True), traces

        return _fallback(evidence), traces

    finally:
        cursor.close()
        conn.close()