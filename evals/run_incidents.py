"""
evals/run_incidents.py — Day 10 incident benchmark runner.

Loads every evals/incidents/incident_XXX/{scenario,expected}.json pair, runs the
agent, and scores status + root-cause keywords + confidence band + abstention.

Run:  python -m evals.run_incidents
"""

from __future__ import annotations

import json
from pathlib import Path

from api.agent import run_investigation

INCIDENTS_DIR = Path("evals/incidents")


def load_cases() -> list[tuple[dict, dict]]:
    cases = []
    for d in sorted(INCIDENTS_DIR.glob("incident_*")):
        scenario = json.loads((d / "scenario.json").read_text())
        expected = json.loads((d / "expected.json").read_text())
        cases.append((scenario, expected))
    return cases


def score_case(scenario: dict, expected: dict) -> dict:
    investigation, _traces = run_investigation(scenario["question"])
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

    passed = status_ok and kw_ok and conf_ok and abstain_ok
    return {
        "id": scenario["id"],
        "passed": passed,
        "got_status": investigation.status.value,
        "got_conf": investigation.confidence_score,
        "root_cause": investigation.root_cause,
    }


def main():
    cases = load_cases()
    results = [score_case(s, e) for s, e in cases]

    passed = sum(r["passed"] for r in results)
    print(f"\n{'id':<16}{'pass':>6}{'status':>22}{'conf':>7}  root_cause")
    print("-" * 80)
    for r in results:
        flag = "PASS" if r["passed"] else "FAIL"
        print(f"{r['id']:<16}{flag:>6}{r['got_status']:>22}{r['got_conf']:>7.2f}  {r['root_cause'][:28]}")
    print("-" * 80)
    print(f"{passed}/{len(results)} passed")


if __name__ == "__main__":
    main()