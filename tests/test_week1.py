"""
Week 1 manual validation tests.

Tests:
1. Investigation creation
2. Trace persistence
3. Failed service handling
"""

import requests
import psycopg2


BASE_URL = (
    "http://127.0.0.1:8000"
)


DB = {
    "host": "localhost",
    "database": "runbookai",
    "user": "postgres",
    "password": "potty123",
}


def db():

    return psycopg2.connect(
        **DB
    )



def test_successful_investigation():

    response = requests.post(
        BASE_URL + "/api/v1/investigate",
        json={
            "service_name":
                "checkout-service",
            "question":
                "Why is checkout failing?"
        }
    )


    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "resolved"
    assert data["investigation_id"]



def test_trace_saved():

    conn = db()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM investigation_traces;
        """
    )

    count = cursor.fetchone()[0]

    assert count >= 2

    cursor.close()
    conn.close()



def test_unknown_service():

    response = requests.post(
        BASE_URL + "/api/v1/investigate",
        json={
            "service_name":
                "does-not-exist",
            "question":
                "Why broken?"
        }
    )


    assert response.status_code == 404



if __name__ == "__main__":

    test_successful_investigation()
    test_trace_saved()
    test_unknown_service()

    print(
        "Week 1 tests passed"
    )