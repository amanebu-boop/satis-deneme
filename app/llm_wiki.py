"""Lightweight local LLM Wiki retrieval for Ersen Makina sales knowledge.

The index stores searchable excerpts locally in SQLite. Only the selected results
are sent to the OpenAI assistant when a user explicitly asks a relevant question.
"""
from __future__ import annotations

import hashlib
import json
import re
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from app import db

router = APIRouter()
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_EXTRACTED_CHARS = 200_000

_ROOT = Path(__file__).resolve().parent.parent
_MAX_CONTENT = 12000
_TOKEN_RE = re.compile(r"[\w-]+", re.UNICODE)


def _tokens(value: str) -> list[str]:
    return [item.casefold() for item in _TOKEN_RE.findall(value or "") if len(item) > 1]


def init_wiki() -> None:
    with db.connect() as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS llm_wiki_documents (
                id TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                source_id TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(source_type, source_id)
            )"""
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_llm_wiki_source ON llm_wiki_documents(source_type, source_id)"
        )


def _upsert(source_type: str, source_id: str, title: str, content: str) -> None:
    content = (content or "").strip()[:_MAX_CONTENT]
    if not content:
        return
    digest = hashlib.sha256((title + "\n" + content).encode("utf-8")).hexdigest()
    with db.connect() as connection:
        connection.execute(
            """INSERT INTO llm_wiki_documents
               (id, source_type, source_id, title, content, content_hash, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(source_type, source_id) DO UPDATE SET
                 title=excluded.title, content=excluded.content,
                 content_hash=excluded.content_hash, updated_at=CURRENT_TIMESTAMP
               WHERE llm_wiki_documents.content_hash != excluded.content_hash""",
            (f"{source_type}:{source_id}", source_type, source_id, title, content, digest),
        )


def refresh_wiki_index() -> None:
    """Refresh local markdown knowledge and current catalog/customer activity."""
    init_wiki()
    markdown_paths = [_ROOT / "AGENTS.md", _ROOT / "AGENT_ARCHITECTURE.md"]
    markdown_paths.extend(sorted((_ROOT / "agents").glob("*.md")))
    docs_root = _ROOT / "docs"
    if docs_root.exists():
        markdown_paths.extend(sorted(docs_root.rglob("*.md")))
    active_markdown_ids: set[str] = set()
    for path in markdown_paths:
        if not path.is_file():
            continue
        relative = path.relative_to(_ROOT).as_posix()
        active_markdown_ids.add(relative)
        try:
            _upsert("markdown", relative, relative, path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError):
            continue
    with db.connect() as connection:
        rows = connection.execute("SELECT source_id FROM llm_wiki_documents WHERE source_type='markdown'").fetchall()
        for row in rows:
            if row["source_id"] not in active_markdown_ids:
                connection.execute(
                    "DELETE FROM llm_wiki_documents WHERE source_type='markdown' AND source_id=?",
                    (row["source_id"],),
                )

    products = db.list_products()
    product_by_id = {str(item["id"]): item for item in products}
    active_ids: dict[str, set[str]] = {"product": set(), "company": set(), "meeting": set()}
    for item in products:
        parent_id = item.get("parent_product_id")
        parent = product_by_id.get(str(parent_id)) if parent_id else None
        content = {
            "sku": item.get("sku"), "name": item.get("name"),
            "description": item.get("description"), "type": item.get("product_type"),
            "currency": item.get("currency"), "unit_price": item.get("unit_price"),
            "parent_product": parent.get("name") if parent else None,
        }
        active_ids["product"].add(str(item["id"]))
        _upsert("product", str(item["id"]), str(item.get("name") or item.get("sku") or "Ürün"),
                json.dumps(content, ensure_ascii=False))

    for item in db.list_companies():
        sectors = item.get("sectors") or ([item.get("sector")] if item.get("sector") else [])
        content = {
            "name": item.get("name"), "sectors": sectors,
            "city": item.get("city"), "district": item.get("district"),
        }
        active_ids["company"].add(str(item["id"]))
        _upsert("company", str(item["id"]), str(item.get("name") or "Firma"),
                json.dumps(content, ensure_ascii=False))

    for item in db.list_meetings():
        content = {
            "company": item.get("company_name"), "date": item.get("meeting_date"),
            "type": item.get("meeting_type"), "topic": item.get("topic"),
            "notes": item.get("notes"),
            "products": [
                {"name": line.get("name"), "quantity": line.get("quantity")}
                for line in item.get("product_lines", [])
            ],
        }
        title = f"Görüşme · {item.get('company_name') or 'Firma'} · {item.get('meeting_date') or ''}"
        active_ids["meeting"].add(str(item["id"]))
        _upsert("meeting", str(item["id"]), title, json.dumps(content, ensure_ascii=False))

    # Deleted catalog/customer records must not remain searchable in the Wiki.
    with db.connect() as connection:
        for source_type, ids in active_ids.items():
            existing_ids = connection.execute(
                "SELECT source_id FROM llm_wiki_documents WHERE source_type=?",
                (source_type,),
            ).fetchall()
            for row in existing_ids:
                if row["source_id"] not in ids:
                    connection.execute(
                        "DELETE FROM llm_wiki_documents WHERE source_type=? AND source_id=?",
                        (source_type, row["source_id"]),
                    )


def _extract_document_text(filename: str, data: bytes) -> str:
    suffix = Path(filename).suffix.casefold()
    if suffix in {".txt", ".md"}:
        return data.decode("utf-8-sig")
    if suffix == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(data))
        return "\\n".join((page.extract_text() or "") for page in reader.pages[:100])
    if suffix == ".docx":
        from docx import Document
        document = Document(BytesIO(data))
        parts = [paragraph.text for paragraph in document.paragraphs]
        for table in document.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text for cell in row.cells))
        return "\\n".join(parts)
    raise HTTPException(status_code=415, detail="Yalnızca PDF, DOCX, TXT veya MD dosyaları kabul edilir.")


@router.get("/api/wiki/documents")
def list_wiki_documents(request: Request) -> list[dict[str, Any]]:
    from app.main import _require_browser_session
    _require_browser_session(request)
    with db.connect() as connection:
        rows = connection.execute(
            """SELECT source_id, title, updated_at FROM llm_wiki_documents
               WHERE source_type='uploaded_document' ORDER BY title"""
        ).fetchall()
    return [dict(row) for row in rows]


@router.post("/api/wiki/documents", status_code=201)
async def upload_wiki_document(request: Request, file: UploadFile = File(...)) -> dict[str, Any]:
    from app.main import _require_browser_session, _require_csrf
    _require_csrf(request, _require_browser_session(request))
    filename = Path(file.filename or "").name.strip()
    if not filename or Path(filename).suffix.casefold() not in {".pdf", ".docx", ".txt", ".md"}:
        raise HTTPException(status_code=415, detail="Yalnızca PDF, DOCX, TXT veya MD dosyaları kabul edilir.")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Bilgi belgesi en fazla 8 MB olabilir.")
    if not data:
        raise HTTPException(status_code=422, detail="Dosya boş.")
    try:
        content = _extract_document_text(filename, data).strip()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Belge metni okunamadı; dosya biçimini kontrol edin.") from exc
    if not content:
        raise HTTPException(status_code=422, detail="Belgede aranabilir metin bulunamadı. Taranmış PDF için OCR gerekir.")
    if len(content) > MAX_EXTRACTED_CHARS:
        content = content[:MAX_EXTRACTED_CHARS]
    source_id = hashlib.sha256((filename + hashlib.sha256(data).hexdigest()).encode("utf-8")).hexdigest()[:32]
    _upsert("uploaded_document", source_id, filename, content)
    return {"source_id": source_id, "title": filename, "characters_indexed": len(content)}


@router.delete("/api/wiki/documents/{source_id}")
def delete_wiki_document(source_id: str, request: Request) -> dict[str, bool]:
    from app.main import _require_browser_session, _require_csrf
    _require_csrf(request, _require_browser_session(request))
    with db.connect() as connection:
        changed = connection.execute(
            "DELETE FROM llm_wiki_documents WHERE source_type='uploaded_document' AND source_id=?",
            (source_id,),
        ).rowcount
    if not changed:
        raise HTTPException(status_code=404, detail="Bilgi belgesi bulunamadı.")
    return {"deleted": True}


def search_wiki(query: str, limit: int = 5) -> dict[str, Any]:
    """Return a small lexical retrieval set; no external embedding call is made."""
    query = (query or "").strip()
    terms = list(dict.fromkeys(_tokens(query)))
    if not terms:
        return {"query": query, "results": [], "retrieval": "local_lexical"}
    refresh_wiki_index()
    with db.connect() as connection:
        rows = connection.execute(
            "SELECT source_type, source_id, title, content FROM llm_wiki_documents"
        ).fetchall()
    ranked = []
    for row in rows:
        title = str(row["title"] or "")
        content = str(row["content"] or "")
        title_lower, content_lower = title.casefold(), content.casefold()
        score = sum((4 if term in title_lower else 0) + content_lower.count(term) for term in terms)
        if score:
            ranked.append((score, row))
    ranked.sort(key=lambda pair: (-pair[0], pair[1]["source_type"], pair[1]["title"]))
    results = []
    for score, row in ranked[:max(1, min(int(limit), 8))]:
        results.append({
            "source_type": row["source_type"],
            "title": row["title"],
            "content": str(row["content"])[:1800],
            "relevance_score": score,
        })
    return {"query": query, "retrieval": "local_lexical", "results": results}
