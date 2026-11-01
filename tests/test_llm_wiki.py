from app import db, llm_wiki


import pytest


@pytest.fixture(autouse=True)
def reset_refresh_cache():
    llm_wiki._last_refresh_at = 0


def test_wiki_retrieves_relevant_catalog_item_without_external_embeddings(tmp_path, monkeypatch):
    monkeypatch.setenv("SALES_DATABASE_PATH", str(tmp_path / "wiki.db"))
    db.init_db()
    monkeypatch.setattr(db, "list_products", lambda: [{
        "id": "p-1", "sku": "DB-01", "name": "Çift Kafa Büküm Makinası",
        "description": "Askı delik kulesi opsiyonu", "product_type": "machine",
        "currency": "EUR", "unit_price": "22000", "parent_product_id": None,
    }])
    monkeypatch.setattr(db, "list_companies", lambda: [])
    monkeypatch.setattr(db, "list_meetings", lambda: [])

    result = llm_wiki.search_wiki("çift kafa büküm", limit=3)

    assert result["retrieval"] in {"local_lexical", "local_fts5"}
    assert result["results"]
    assert result["results"][0]["source_type"] == "product"
    assert "22000" in result["results"][0]["content"]


def test_wiki_removes_deleted_dynamic_records(tmp_path, monkeypatch):
    monkeypatch.setenv("SALES_DATABASE_PATH", str(tmp_path / "wiki-delete.db"))
    db.init_db()
    products = [{
        "id": "p-old", "sku": "OLD", "name": "Eski makine",
        "description": "silinmiş kayıt", "product_type": "machine",
        "currency": "EUR", "unit_price": "100", "parent_product_id": None,
    }]
    monkeypatch.setattr(db, "list_products", lambda: products)
    monkeypatch.setattr(db, "list_companies", lambda: [])
    monkeypatch.setattr(db, "list_meetings", lambda: [])
    llm_wiki.search_wiki("eski makine")
    products.clear()
    llm_wiki._last_refresh_at = 0
    result = llm_wiki.search_wiki("eski makine")
    assert not any(item["source_type"] == "product" for item in result["results"])


def test_authenticated_document_upload_search_and_delete(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app

    monkeypatch.setenv("SALES_DATABASE_PATH", str(tmp_path / "wiki-api.db"))
    monkeypatch.setenv("SALES_LOGIN_PASSWORD", "a-secure-test-password-123")
    with TestClient(app, base_url="https://testserver") as client:
        login = client.post(
            "/api/login", json={"password": "a-secure-test-password-123"},
            headers={"Origin": "https://testserver"},
        )
        assert login.status_code == 200
        headers = {"Origin": "https://testserver", "X-CSRF-Token": login.json()["csrf_token"]}
        uploaded = client.post(
            "/api/wiki/documents", headers=headers,
            files={"file": ("bukum-teknik-notu.txt", "Büküm makinası için teknik bakım talimatı.".encode(), "text/plain")},
        )
        assert uploaded.status_code == 201, uploaded.json()
        source_id = uploaded.json()["source_id"]
        assert uploaded.json()["characters_indexed"] > 0
        listed = client.get("/api/wiki/documents")
        assert listed.status_code == 200
        assert any(item["source_id"] == source_id for item in listed.json())
        result = llm_wiki.search_wiki("teknik bakım talimatı")
        assert any(item["source_type"] == "uploaded_document" for item in result["results"])
        deleted = client.delete(f"/api/wiki/documents/{source_id}", headers=headers)
        assert deleted.status_code == 200
        result = llm_wiki.search_wiki("teknik bakım talimatı")
        assert not any(item["source_type"] == "uploaded_document" for item in result["results"])


def test_wiki_upload_rejects_unsupported_file_type(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app

    monkeypatch.setenv("SALES_DATABASE_PATH", str(tmp_path / "wiki-invalid.db"))
    monkeypatch.setenv("SALES_LOGIN_PASSWORD", "a-secure-test-password-123")
    with TestClient(app, base_url="https://testserver") as client:
        login = client.post(
            "/api/login", json={"password": "a-secure-test-password-123"},
            headers={"Origin": "https://testserver"},
        )
        headers = {"Origin": "https://testserver", "X-CSRF-Token": login.json()["csrf_token"]}
        response = client.post(
            "/api/wiki/documents", headers=headers,
            files={"file": ("payload.exe", b"not executable", "application/octet-stream")},
        )
        assert response.status_code == 415


def test_meeting_contact_fields_are_redacted_from_wiki_text():
    from app.llm_wiki import _redact_meeting_contacts
    cleaned = _redact_meeting_contacts(
        "Arayın: +90 532 123 45 67 veya satis@example.com. Vergi numarası 1234567890. Makine fiyatını görüşün."
    )
    assert "+90 532 123 45 67" not in cleaned
    assert "satis@example.com" not in cleaned
    assert "1234567890" not in cleaned
    assert "Makine fiyatını görüşün" in cleaned


def test_pdf_and_docx_text_extraction():
    from io import BytesIO
    from docx import Document
    from reportlab.pdfgen import canvas
    from app.llm_wiki import _extract_document_text

    docx_stream = BytesIO()
    document = Document()
    document.add_paragraph("CNC büküm makinası teknik föyü")
    document.save(docx_stream)
    docx_text = _extract_document_text("teknik.docx", docx_stream.getvalue())
    assert "CNC büküm makinası" in docx_text

    pdf_stream = BytesIO()
    pdf = canvas.Canvas(pdf_stream)
    pdf.drawString(60, 760, "CNC bending machine technical sheet")
    pdf.save()
    pdf_text = _extract_document_text("technical.pdf", pdf_stream.getvalue())
    assert "CNC bending machine" in pdf_text


def test_wiki_indexes_quotation_history_and_followups(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    monkeypatch.setenv("SALES_DATABASE_PATH", str(tmp_path / "wiki-sales-history.db"))
    db.init_db()
    db.create_company({
        "id": "company-history", "name": "ABC Makina", "sector": "Mobilya",
        "authorized_people": [], "phone_numbers": [],
    })
    with db.connect() as connection:
        connection.execute(
            """INSERT INTO quotations
               (id, quote_number, revision, company_id, currency, subtotal, tax_rate,
                tax_amount, total, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("quote-history", "ERS-2026-0001", 0, "company-history", "EUR",
             "22000", "0.20", "4400", "26400", "draft", datetime.now(timezone.utc).isoformat()),
        )
        connection.execute(
            """INSERT INTO quotation_lines
               (id, quotation_id, description, quantity, unit_price, line_total)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("line-history", "quote-history", "Çift Kafa Büküm Makinası", "1", "22000", "22000"),
        )
        connection.execute(
            """INSERT INTO follow_up_tasks
               (id, company_id, title, due_date, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("follow-history", "company-history", "Teklif geri dönüşü", "2026-11-10", "open",
             datetime.now(timezone.utc).isoformat()),
        )
    monkeypatch.setattr(db, "list_products", lambda: [])
    result = llm_wiki.search_wiki("ERS-2026-0001 büküm")
    assert any(item["source_type"] == "quotation" for item in result["results"])
    result = llm_wiki.search_wiki("teklif geri dönüşü")
    assert any(item["source_type"] == "follow_up" for item in result["results"])


def test_parent_product_wiki_entry_contains_linked_options(tmp_path, monkeypatch):
    monkeypatch.setenv("SALES_DATABASE_PATH", str(tmp_path / "wiki-options.db"))
    db.init_db()
    monkeypatch.setattr(db, "list_products", lambda: [
        {"id": "machine", "sku": "M-01", "name": "Çift Kafa Büküm Makinası",
         "description": "Ana makine", "product_type": "machine", "currency": "EUR",
         "unit_price": "22000", "parent_product_id": None},
        {"id": "option", "sku": "O-01", "name": "Askı delik kulesi",
         "description": "Opsiyon", "product_type": "option", "currency": "EUR",
         "unit_price": "4500", "parent_product_id": "machine"},
    ])
    monkeypatch.setattr(db, "list_companies", lambda: [])
    monkeypatch.setattr(db, "list_meetings", lambda: [])
    result = llm_wiki.search_wiki("Çift Kafa Büküm Makinası")
    machine = next(item for item in result["results"] if item["source_type"] == "product")
    assert "Askı delik kulesi" in machine["content"]
    assert "4500" in machine["content"]


def test_uploading_same_filename_replaces_previous_wiki_version(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    monkeypatch.setenv("SALES_DATABASE_PATH", str(tmp_path / "wiki-version.db"))
    monkeypatch.setenv("SALES_LOGIN_PASSWORD", "a-secure-test-password-123")
    with TestClient(app, base_url="https://testserver") as client:
        login = client.post(
            "/api/login", json={"password": "a-secure-test-password-123"},
            headers={"Origin": "https://testserver"},
        )
        headers = {"Origin": "https://testserver", "X-CSRF-Token": login.json()["csrf_token"]}
        first = client.post(
            "/api/wiki/documents", headers=headers,
            files={"file": ("machine-manual.txt", b"obsolete legacy machine procedure", "text/plain")},
        )
        second = client.post(
            "/api/wiki/documents", headers=headers,
            files={"file": ("machine-manual.txt", b"updated current machine procedure", "text/plain")},
        )
        assert first.status_code == second.status_code == 201
        documents = client.get("/api/wiki/documents").json()
        assert len([doc for doc in documents if doc["title"] == "machine-manual.txt"]) == 1
        old_results = llm_wiki.search_wiki("obsolete legacy")
        new_results = llm_wiki.search_wiki("updated current")
        assert not any(item["source_type"] == "uploaded_document" for item in old_results["results"])
        assert any(item["source_type"] == "uploaded_document" for item in new_results["results"])
