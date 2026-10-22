from fastapi.testclient import TestClient

from app.main import app


def test_health():
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_services_are_seeded():
    with TestClient(app) as client:
        response = client.get("/api/services")
    assert response.status_code == 200
    services = {s["name"]: s for s in response.json()}
    assert len(services) == 6
    assert services["Haircut"] == {
        "id": 1,
        "name": "Haircut",
        "duration_minutes": 30,
        "price_rand": 150,
    }
    assert services["Hair Colour"]["price_rand"] == 450


def test_frontend_is_served():
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "Bloom Beauty Bar" in response.text
