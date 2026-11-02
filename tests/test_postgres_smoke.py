import pytest
from uuid import uuid4
from app import db, db_backend

pytestmark = pytest.mark.skipif(
    not db_backend.is_postgres_configured(),
    reason="PostgreSQL integration test requires DATABASE_URL",
)

def test_postgres_company_and_meeting_roundtrip():
    db.init_db()
    company_id = "pg-" + uuid4().hex
    meeting_id = "pg-" + uuid4().hex
    try:
        db.create_company({"id": company_id, "name": "POSTGRES TEST"})
        company = db.get_company(company_id)
        assert company is not None
        assert company["name"] == "POSTGRES TEST"
        db.create_meeting({
            "id": meeting_id,
            "company_id": company_id,
            "meeting_date": "2026-11-02",
            "notes": "synthetic PostgreSQL integration test",
            "meeting_type": "phone",
            "topic": "test",
            "product_lines": [],
        })
        meetings = db.list_company_meetings(company_id)
        assert any(item["id"] == meeting_id for item in meetings)
    finally:
        with db.connect() as connection:
            connection.execute("DELETE FROM companies WHERE id = ?", (company_id,))
