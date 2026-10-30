import pytest
from fastapi.testclient import TestClient

from app.main import app


def test_product_catalog_can_create_and_list_products(tmp_path, monkeypatch):
    monkeypatch.setenv("SALES_DATABASE_PATH", str(tmp_path / "sales.db"))
    monkeypatch.setenv("SALES_LOGIN_PASSWORD", "a-secure-test-password-123")
    with TestClient(app, base_url="https://testserver") as client:
        login = client.post(
            "/api/login",
            json={"password": "a-secure-test-password-123"},
            headers={"Origin": "https://testserver"},
        )
        assert login.status_code == 200
        csrf = login.json()["csrf_token"]
        headers = {"Origin": "https://testserver", "X-CSRF-Token": csrf}
        payload = {
            "sku": "URN-001",
            "name": "Deneme ürünü",
            "description": "Test açıklaması",
            "currency": "EUR",
            "unit_price": 1250,
        }

        created = client.post("/api/products", json=payload, headers=headers)
        assert created.status_code == 201
        assert created.json()["sku"] == "URN-001"
        assert created.json()["unit_price"] == "1250"

        listed = client.get("/api/products")
        assert listed.status_code == 200
        assert [item["sku"] for item in listed.json()] == ["URN-001"]

        duplicate = client.post("/api/products", json=payload, headers=headers)
        assert duplicate.status_code == 409


def test_product_catalog_rejects_fractional_unit_price(tmp_path, monkeypatch):
    monkeypatch.setenv("SALES_DATABASE_PATH", str(tmp_path / "sales.db"))
    monkeypatch.setenv("SALES_LOGIN_PASSWORD", "a-secure-test-password-123")
    with TestClient(app, base_url="https://testserver") as client:
        login = client.post(
            "/api/login",
            json={"password": "a-secure-test-password-123"},
            headers={"Origin": "https://testserver"},
        )
        csrf = login.json()["csrf_token"]
        response = client.post(
            "/api/products",
            json={
                "sku": "URN-002",
                "name": "Kesirli fiyat",
                "currency": "TRY",
                "unit_price": 12.5,
            },
            headers={"Origin": "https://testserver", "X-CSRF-Token": csrf},
        )
        assert response.status_code == 422
