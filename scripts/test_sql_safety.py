"""Adversarial tests for the SQL safety layer (Day 17).

Confirms validate_select rejects every dangerous shape and accepts only
legitimate single SELECTs over the allowed tables.

    python -m scripts.test_sql_safety
"""
from api.tools.sql_guard import validate_select, enforce_limit, UnsafeSQL, ALLOWED_TABLES

SHOULD_PASS = [
    "SELECT s.name FROM services s WHERE s.name = %(service_name)s",
    "select * from pods where deployment_id = 1",
    "SELECT status FROM deployments JOIN services ON services.id = deployments.service_id",
]

SHOULD_REJECT = {
    "attempted DROP (stacked)":      "SELECT * FROM services; DROP TABLE services;",
    "attempted DROP (inline)":       "SELECT * FROM services WHERE 1=1; DROP TABLE pods",
    "DELETE":                        "DELETE FROM services",
    "UPDATE":                        "UPDATE deployments SET status='Healthy'",
    "INSERT":                        "INSERT INTO services (name) VALUES ('x')",
    "TRUNCATE":                      "TRUNCATE services",
    "disallowed table":             "SELECT * FROM investigations",
    "disallowed table (users)":     "SELECT password FROM users",
    "SELECT INTO (exfil)":          "SELECT * FROM services INTO OUTFILE '/tmp/x'",
    "pg_sleep DoS":                 "SELECT pg_sleep(10)",
    "GRANT escalation":             "GRANT ALL ON services TO PUBLIC",
    "CTE bypass":                   "WITH t AS (DELETE FROM pods RETURNING *) SELECT * FROM t",
    "comment-hidden stack":         "SELECT * FROM services -- ok\n; DROP TABLE services",
    "empty":                        "   ",
    "not a query":                  "help me",
}


def main() -> None:
    failures = 0

    print("=== must PASS ===")
    for q in SHOULD_PASS:
        try:
            validate_select(q)
            print(f"  pass  {q[:55]}")
        except UnsafeSQL as e:
            failures += 1
            print(f"  FAIL (wrongly rejected: {e})  {q[:45]}")

    print("\n=== must REJECT ===")
    for label, q in SHOULD_REJECT.items():
        try:
            validate_select(q)
            failures += 1
            print(f"  FAIL (wrongly passed)  {label}")
        except UnsafeSQL as e:
            print(f"  reject  {label:24s} -> {str(e)[:45]}")

    print(f"\nALLOWED_TABLES = {sorted(ALLOWED_TABLES)}")
    print(f"LIMIT enforced: {enforce_limit('SELECT 1 FROM services').endswith('LIMIT 500')}")
    if failures:
        raise SystemExit(f"\n{failures} SAFETY TEST(S) FAILED")
    print("\nall SQL safety tests passed")


if __name__ == "__main__":
    main()