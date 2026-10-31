from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.main import app


def test_company_structured_address_and_meeting_product_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("SALES_DATABASE_PATH", str(tmp_path / "sales.db"))
    monkeypatch.setenv("SALES_LOGIN_PASSWORD", "a-secure-test-password-123")
    with TestClient(app, base_url="https://testserver") as client:
        login = client.post(
            "/api/login",
            json={"password": "a-secure-test-password-123"},
            headers={"Origin": "https://testserver"},
        )
        assert login.status_code == 200
        headers = {"Origin": "https://testserver", "X-CSRF-Token": login.json()["csrf_token"]}

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



def test_catalog_allows_unknown_price_and_requires_machine_for_option(tmp_path, monkeypatch):
    monkeypatch.setenv("SALES_DATABASE_PATH", str(tmp_path / "sales.db"))
    monkeypatch.setenv("SALES_LOGIN_PASSWORD", "a-secure-test-password-123")
    with TestClient(app, base_url="https://testserver") as client:
        login = client.post(
            "/api/login",
            json={"password": "a-secure-test-password-123"},
            headers={"Origin": "https://testserver"},
        )
        headers = {"Origin": "https://testserver", "X-CSRF-Token": login.json()["csrf_token"]}
        machine = client.post(
            "/api/products",
            headers=headers,
            json={
                "sku": "MAK-UNKNOWN",
                "name": "Fiyatı Sonra Belirlenecek Makine",
                "currency": "EUR",
                "unit_price": None,
                "product_type": "machine",
            },
        )
        assert machine.status_code == 201
        assert machine.json()["unit_price"] == ""

        option = client.post(
            "/api/products",
            headers=headers,
            json={
                "sku": "OPS-001",
                "name": "Askı delik kulesi",
                "currency": "EUR",
                "unit_price": 4500,
                "product_type": "option",
                "parent_product_id": machine.json()["id"],
            },
        )
        assert option.status_code == 201
        assert option.json()["parent_product_id"] == machine.json()["id"]

        company = client.post(
            "/api/companies",
            headers=headers,
            json={"name": "Opsiyon Test Firması"},
        )
        invalid_meeting = client.post(
            "/api/meetings",
            headers=headers,
            json={
                "company_id": company.json()["id"],
                "meeting_date": "2026-10-30T10:00",
                "topic": "Opsiyon",
                "notes": "Ana makine seçilmeden opsiyon eklenmemeli.",
                "product_lines": [
                    {"product_id": option.json()["id"], "quantity": 1, "unit_price": 4500}
                ],
            },
        )
        assert invalid_meeting.status_code == 422


def test_quote_numbers_are_sequential_and_currency_is_eur(tmp_path, monkeypatch):
    monkeypatch.setenv("SALES_DATABASE_PATH", str(tmp_path / "sales.db"))
    monkeypatch.setenv("SALES_LOGIN_PASSWORD", "a-secure-test-password-123")
    with TestClient(app, base_url="https://testserver") as client:
        login = client.post(
            "/api/login",
            json={"password": "a-secure-test-password-123"},
            headers={"Origin": "https://testserver"},
        )
        headers = {"Origin": "https://testserver", "X-CSRF-Token": login.json()["csrf_token"]}
        payload = {"currency": "EUR", "lines": [{"description": "Test makinesi", "quantity": 1, "unit_price": 1000}]}
        first = client.post("/api/quotes", headers=headers, json=payload)
        second = client.post("/api/quotes", headers=headers, json=payload)
        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json()["quote_number"].startswith("ERS-2026-")
        assert second.json()["quote_number"].endswith(f"{int(first.json()['quote_number'][-4:]) + 1:04d}")
        rejected = client.post("/api/quotes", headers=headers, json={**payload, "currency": "TRY"})
        assert rejected.status_code == 422



def test_catalog_update_does_not_change_existing_meeting_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("SALES_DATABASE_PATH", str(tmp_path / "sales.db"))
    monkeypatch.setenv("SALES_LOGIN_PASSWORD", "a-secure-test-password-123")
    with TestClient(app, base_url="https://testserver") as client:
        login = client.post("/api/login", json={"password": "a-secure-test-password-123"}, headers={"Origin": "https://testserver"})
        headers = {"Origin": "https://testserver", "X-CSRF-Token": login.json()["csrf_token"]}
        company = client.post("/api/companies", headers=headers, json={"name": "Snapshot Test"})
        product = client.post("/api/products", headers=headers, json={
            "sku": "SNAP-001", "name": "Eski Makine Adı", "currency": "EUR", "unit_price": 22000,
        })
        meeting = client.post("/api/meetings", headers=headers, json={
            "company_id": company.json()["id"], "meeting_date": "2026-10-30T10:00",
            "topic": "Snapshot", "notes": "Eski fiyat ve isim korunmalı.",
            "product_lines": [{"product_id": product.json()["id"], "quantity": 1, "unit_price": 21500}],
        })
        assert meeting.status_code == 201
        update = client.put("/api/products/" + product.json()["id"], headers=headers, json={
            "sku": "SNAP-001-NEW", "name": "Yeni Makine Adı", "currency": "EUR", "unit_price": 25000,
        })
        assert update.status_code == 200
        stored = client.get("/api/meetings").json()[0]["product_lines"][0]
        assert stored["name"] == "Eski Makine Adı"
        assert stored["sku"] == "SNAP-001"
        assert stored["unit_price"] == "21500"
        edited = client.put("/api/meetings/" + meeting.json()["id"], headers=headers, json={
            "company_id": company.json()["id"], "meeting_date": "2026-10-30T11:00",
            "meeting_type": "phone", "topic": "Snapshot düzenlendi", "notes": "Not güncellendi.",
            "product_lines": [{"product_id": product.json()["id"], "quantity": 1, "unit_price": 21500}],
        })
        assert edited.status_code == 200
        assert edited.json()["product_lines"][0]["name"] == "Eski Makine Adı"
        assert edited.json()["product_lines"][0]["sku"] == "SNAP-001"
        assert edited.json()["product_lines"][0]["unit_price"] == "21500"


def test_quote_exports_use_template_images_serial_and_matching_pdf(tmp_path, monkeypatch):
    monkeypatch.setenv("SALES_DATABASE_PATH", str(tmp_path / "sales.db"))
    monkeypatch.setenv("SALES_LOGIN_PASSWORD", "a-secure-test-password-123")
    with TestClient(app, base_url="https://testserver") as client:
        login = client.post("/api/login", json={"password": "a-secure-test-password-123"}, headers={"Origin": "https://testserver"})
        headers = {"Origin": "https://testserver", "X-CSRF-Token": login.json()["csrf_token"]}
        company = client.post("/api/companies", headers=headers, json={"name": "PDF Deneme Ltd"})
        quote = client.post("/api/quotes", headers=headers, json={
            "currency": "EUR", "company_id": company.json()["id"],
            "lines": [{"description": "Şablonlu makine", "quantity": 1, "unit_price": 1000}],
        })
        assert quote.status_code == 201
        quote_number = quote.json()["quote_number"]
        excel = client.get("/api/quotes/" + quote.json()["id"] + "/excel")
        assert excel.status_code == 200
        workbook = load_workbook(BytesIO(excel.content), data_only=False)
        sheet = workbook["Teklif"]
        assert sheet["C28"].value == 1
        assert len(sheet._images) >= 2
        workbook.close()
        expected_name = "PDF_Deneme_Ltd_" + quote_number
        assert expected_name in excel.headers["content-disposition"]
        pdf = client.get("/api/quotes/" + quote.json()["id"] + "/pdf")
        preview = client.get("/api/quotes/" + quote.json()["id"] + "/document")
        download = client.get("/api/quotes/" + quote.json()["id"] + "/pdf?download=true")
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")
        assert preview.status_code == 200 and preview.content.startswith(b"%PDF-")
        assert download.status_code == 200 and "attachment" in download.headers["content-disposition"]
        assert expected_name in preview.headers["content-disposition"]



def test_pdf_generation_refuses_different_layout_when_template_converter_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("SALES_DATABASE_PATH", str(tmp_path / "sales.db"))
    from app import quote_pdf
    from app.quote_excel import render_quote_excel
    from fastapi import HTTPException

    company = {"name": "PDF Template Test", "address": "Kayseri"}
    quote = {
        "id": "template-test", "quote_number": "ERS-2026-9999",
        "currency": "EUR", "created_at": "2026-10-30T00:00:00+00:00",
        "lines": [{"description": "Test Makinesi", "quantity": "1", "unit_price": "12000"}],
    }
    xlsx = render_quote_excel(quote, company)
    monkeypatch.setattr(quote_pdf.shutil, "which", lambda _name: None)
    with pytest.raises(HTTPException) as exc:
        quote_pdf.convert_excel_to_pdf(xlsx)
    assert exc.value.status_code == 503
    assert "LibreOffice" in str(exc.value.detail)


def test_profile_qr_endpoint_returns_local_png(tmp_path, monkeypatch):
    monkeypatch.setenv("SALES_DATABASE_PATH", str(tmp_path / "sales.db"))
    monkeypatch.setenv("SALES_LOGIN_PASSWORD", "a-secure-test-password-123")
    with TestClient(app, base_url="https://testserver") as client:
        login = client.post("/api/login", json={"password": "a-secure-test-password-123"}, headers={"Origin": "https://testserver"})
        headers = {"Origin": "https://testserver", "X-CSRF-Token": login.json()["csrf_token"]}
        response = client.post("/api/profile/qr", headers=headers, json={
            "vcard": "BEGIN:VCARD\nVERSION:3.0\nFN:Test Kullanıcı\nORG:Erşen Makina\nEND:VCARD",
        })
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("image/png")
        assert response.content.startswith(b"\x89PNG\r\n\x1a\n")
