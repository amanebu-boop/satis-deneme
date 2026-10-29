from fastapi.testclient import TestClient

from app.main import app


def _authenticated_client(tmp_path, monkeypatch):
    monkeypatch.setenv("SALES_DATABASE_PATH", str(tmp_path / "sales.db"))
    monkeypatch.setenv("SALES_LOGIN_PASSWORD", "a-secure-test-password-123")
    client = TestClient(app, base_url="https://testserver")
    login = client.post(
        "/api/login",
        json={"password": "a-secure-test-password-123"},
        headers={"Origin": "https://testserver"},
    )
    assert login.status_code == 200
    csrf = login.json()["csrf_token"]
    return client, {"Origin": "https://testserver", "X-CSRF-Token": csrf}


def test_company_structured_address_and_meeting_product_snapshot(tmp_path, monkeypatch):
    client, headers = _authenticated_client(tmp_path, monkeypatch)
    with client:
        company = client.post(
            "/api/companies",
            headers=headers,
            json={
                "name": "Deneme Makina",
                "city": "Kayseri",
                "district": "Melikgazi",
                "neighborhood": "Organize Sanayi",
                "street": "1. Cadde",
                "building_number": "12",
                "postal_code": "38070",
                "address_extra": "A blok",
                "address": "1. Cadde, No: 12, Organize Sanayi, Melikgazi, Kayseri, 38070, A blok",
            },
        )
        assert company.status_code == 201
        assert company.json()["city"] == "Kayseri"
        assert company.json()["district"] == "Melikgazi"

        product = client.post(
            "/api/products",
            headers=headers,
            json={
                "sku": "MAK-001",
                "name": "Double Büküm Makinası",
                "description": "Ana makine",
                "currency": "EUR",
                "unit_price": 22000,
            },
        )
        assert product.status_code == 201

        meeting = client.post(
            "/api/meetings",
            headers=headers,
            json={
                "company_id": company.json()["id"],
                "meeting_date": "2026-10-30T10:00",
                "meeting_type": "visit",
                "topic": "Makine ihtiyacı",
                "notes": "İki makine ve fiyat konuşuldu.",
                "product_lines": [
                    {"product_id": product.json()["id"], "quantity": 2, "unit_price": 21500}
                ],
            },
        )
        assert meeting.status_code == 201
        line = meeting.json()["product_lines"][0]
        assert line["name"] == "Double Büküm Makinası"
        assert line["quantity"] == "2"
        assert line["unit_price"] == "21500"
        assert line["currency"] == "EUR"

        listed = client.get("/api/meetings")
        assert listed.status_code == 200
        assert listed.json()[0]["product_lines"][0]["sku"] == "MAK-001"
