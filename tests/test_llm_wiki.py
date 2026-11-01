from app import db, llm_wiki


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

    assert result["retrieval"] == "local_lexical"
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
        "Arayın: +90 532 123 45 67 veya satis@example.com. Makine fiyatını görüşün."
    )
    assert "+90 532 123 45 67" not in cleaned
    assert "satis@example.com" not in cleaned
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
