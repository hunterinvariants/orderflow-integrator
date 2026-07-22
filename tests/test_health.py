from fastapi.testclient import TestClient


def test_health_and_readiness(client: TestClient) -> None:
    assert client.get("/health").json()["status"] == "ok"
    ready = client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["database"] == "connected"


def test_dashboard_renders(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "OrderFlow Control Tower" in response.text
