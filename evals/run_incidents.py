"""
evals/run_incidents.py — incident benchmark runner (Day 10 + Day 18 groundedness).

Loads every evals/incidents/incident_XXX/{scenario,expected}.json pair, runs the
agent, and scores status + root-cause keywords + confidence band + abstention.
Day 18: also reports groundedness — lexical overlap between root_cause and the
evidence the agent actually gathered (reconstructed from the trace outputs).

Run:  python -m evals.run_incidents
"""

from __future__ import annotations

import json
from pathlib import Path

from api.agent import run_investigation
from api.groundedness import check_groundedness

INCIDENTS_DIR = Path("evals/incidents")

# Approximate lexical-overlap cutoff. Below this, a RESOLVED root_cause is likely
# not supported by the evidence. Reported only — does NOT change pass/fail here.
# Tune from your own run (see README). NOT NLI entailment.
GROUNDEDNESS_THRESHOLD = 0.4


def load_cases() -> list[tuple[dict, dict]]:
    cases = []
    for d in sorted(INCIDENTS_DIR.glob("incident_*")):
        scenario = json.loads((d / "scenario.json").read_text())
        expected = json.loads((d / "expected.json").read_text())
        cases.append((scenario, expected))
    return cases


def score_case(scenario: dict, expected: dict) -> dict:
    investigation, traces = run_investigation(scenario["question"])
    rc = investigation.root_cause.lower()

    status_ok = investigation.status.value == expected["expected_status"]

    keywords = expected.get("root_cause_keywords", [])
    kw_hits = [k for k in keywords if k.lower() in rc]
    kw_ok = (not keywords) or len(kw_hits) > 0

    lo = expected.get("min_confidence", 0.0)
    hi = expected.get("max_confidence", 1.0)
    conf_ok = lo <= investigation.confidence_score <= hi

    abstain_ok = (not expected.get("unsolvable")) or (
        investigation.status.value == "insufficient_evidence"
    )

    # Day 18: groundedness from the evidence the agent actually saw (trace outputs)
    grounded = check_groundedness(
        investigation.root_cause,
        [t.tool_output for t in traces],
    )

    passed = status_ok and kw_ok and conf_ok and abstain_ok
    return {
        "id": scenario["id"],
        "passed": passed,
        "got_status": investigation.status.value,
        "got_conf": investigation.confidence_score,
        "grounded": grounded,
        "root_cause": investigation.root_cause,
    }


def main():
    cases = load_cases()
    results = [score_case(s, e) for s, e in cases]

    passed = sum(r["passed"] for r in results)
    print(f"\n{'id':<16}{'pass':>6}{'status':>22}{'conf':>7}{'grnd':>7}  root_cause")
    print("-" * 90)
    for r in results:
        flag = "PASS" if r["passed"] else "FAIL"
        # flag a resolved-but-ungrounded finding with '*'
        low = "*" if (r["got_status"] == "resolved" and r["grounded"] < GROUNDEDNESS_THRESHOLD) else " "
        print(f"{r['id']:<16}{flag:>6}{r['got_status']:>22}"
              f"{r['got_conf']:>7.2f}{r['grounded']:>6.2f}{low} {r['root_cause'][:26]}")
    print("-" * 90)
    print(f"{passed}/{len(results)} passed")

    resolved = [r for r in results if r["got_status"] == "resolved"]
    if resolved:
        avg = sum(r["grounded"] for r in resolved) / len(resolved)
        ungrounded = [r["id"] for r in resolved if r["grounded"] < GROUNDEDNESS_THRESHOLD]
        print(f"avg groundedness (resolved): {avg:.2f}   "
              f"below {GROUNDEDNESS_THRESHOLD} (marked *): {ungrounded or 'none'}")


if __name__ == "__main__":
    main()