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
