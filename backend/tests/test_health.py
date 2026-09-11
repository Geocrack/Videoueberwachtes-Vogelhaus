from app import app


def test_health():
    # Tests that /health answers, the endpoint the container health check calls.
    client = app.test_client()
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
