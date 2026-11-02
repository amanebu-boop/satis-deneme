from __future__ import annotations

import pytest

from app import db, db_backend, agent_foundation, ai_usage, llm_wiki


pytestmark = pytest.mark.skipif(
    not db_backend.is_postgres_configured(),
    reason="requires the PostgreSQL CI service",
)


def test_agent_and_wiki_foundation_initializes_on_postgresql():
    db.initialize()
    agent_foundation.init_agent_foundation()
    ai_usage.init_ai_usage()
    llm_wiki.init_wiki()
    assert llm_wiki._fts_available is False

    agents = agent_foundation.list_agents()
    assert {item["id"] for item in agents} >= {"company", "product", "meeting", "quotation", "sales"}

    with db.connect() as connection:
        assert connection.execute("SELECT COUNT(*) AS total FROM agent_ai_usage").fetchone()["total"] == 0
        assert connection.execute("SELECT COUNT(*) AS total FROM llm_wiki_documents").fetchone()["total"] == 0
