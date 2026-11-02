from fastapi.testclient import TestClient

from app import db
from app.main import app


def test_health_endpoint_reports_database_backend(tmp_path, monkeypatch):
    monkeypatch.setenv("SALES_DATABASE_PATH", str(tmp_path / "health.db"))
    monkeypatch.delenv("SALES_DATABASE_URL", raising=False)
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "stage": "prototype",
        "storage": "sqlite",
    }


def test_health_endpoint_returns_503_when_database_is_unavailable(monkeypatch):
    monkeypatch.setattr(db, "database_ready", lambda: False)
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["detail"] == "Database unavailable"
