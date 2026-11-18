"""Tests for /health, /ready, and correlation ID handling."""


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "correlation_id" in data
    assert "X-Correlation-ID" in response.headers


def test_custom_correlation_id_propagates(client):
    custom_cid = "test-corr-id-12345"
    response = client.get("/health", headers={"X-Correlation-ID": custom_cid})
    assert response.status_code == 200
    data = response.json()
    assert data["correlation_id"] == custom_cid
    assert response.headers.get("X-Correlation-ID") == custom_cid


def test_ready_check(client):
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "dependencies" in data


def test_api_v1_health(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_404_error_format(client):
    response = client.get("/non-existent-route")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert "code" in data["error"]
    assert "message" in data["error"]
    assert "correlation_id" in data["error"]
