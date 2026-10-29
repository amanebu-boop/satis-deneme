from contextlib import asynccontextmanager
from pathlib import Path
import ipaddress
from datetime import datetime, timezone
from decimal import Decimal
import hmac
import logging
import os
import time
from threading import Lock
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field, field_validator

from app import db
from app import session_store
from app.pricing import QuoteLine, calculate_quote
from app.documents import render_quotation_html
from app import template_documents
from app.quote_excel import render_quote_excel


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    yield


app = FastAPI(
    title="Sales AI Platform API",
    version="0.3.0",
    description=(
        "Prototype with SQLite persistence and an environment-configured shared API key. "
        "Per-user authorization, tenant isolation, and production hardening are not implemented."
    ),
    lifespan=lifespan,
)


PROTECTED_PREFIXES = ("/companies", "/meetings", "/products", "/quotes")
security_logger = logging.getLogger("sales_api.security")


@app.middleware("http")
async def require_api_key(request: Request, call_next):
    # Server-generated IDs correlate client reports with logs.
    # Never log API keys, request bodies, query strings, or customer notes.
    request_id = str(uuid4())
    protected = request.url.path.startswith(PROTECTED_PREFIXES)
    auth_result = "not_required"
    response = None

    if protected:
        expected = os.environ.get("SALES_API_TOKEN", "")
        if not expected:
            auth_result = "not_configured"
            response = JSONResponse(
                status_code=503,
                content={"detail": "API authentication is not configured"},
            )
        else:
            supplied = request.headers.get("X-API-Key", "")
            if not hmac.compare_digest(supplied, expected):
                auth_result = "rejected"
                response = JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or missing API key"},
                )
            else:
                auth_result = "accepted"

    if response is None:
        try:
            response = await call_next(request)
        except Exception:
            security_logger.exception(
                "request_failed request_id=%s method=%s path=%s auth=%s",
                request_id, request.method, request.url.path, auth_result,
            )
            raise

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if protected or request.url.path.startswith("/api/"):
        # Business records and authentication responses must not be stored by caches.
        response.headers["Cache-Control"] = "no-store, private"
        response.headers["Pragma"] = "no-cache"
    security_logger.info(
        "request_complete request_id=%s method=%s path=%s status=%s auth=%s",
        request_id, request.method, request.url.path, response.status_code, auth_result,
    )
    return response


SESSION_COOKIE = "sales_session"
CSRF_COOKIE = "sales_csrf"
SESSION_TTL_SECONDS = 3600
LOGIN_FAILURE_WINDOW_SECONDS = 300
LOGIN_FAILURE_LIMIT = 5
_login_failures: dict[str, list[float]] = {}
_login_failures_lock = Lock()


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=1024)


def _same_origin(request: Request) -> bool:
    origin = request.headers.get("origin")
    if not origin:
        return False
    return hmac.compare_digest(origin.rstrip("/"), str(request.base_url).rstrip("/"))


def _local_or_https(request: Request) -> bool:
    host = (request.url.hostname or "").lower()
    if request.url.scheme == "https" or host in {"localhost", "127.0.0.1", "::1"}:
        return True
    # Development-only phone testing over a trusted private Wi-Fi network.
    # HTTP cookies are not Secure here; never expose this prototype to public networks.
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_private and not address.is_loopback and not address.is_link_local


def _request_session(request: Request) -> dict[str, str | int] | None:
    return session_store.get_session(request.cookies.get(SESSION_COOKIE))


def _require_browser_session(request: Request) -> dict[str, str | int]:
    session = _request_session(request)
    if session is None:
        raise HTTPException(status_code=401, detail="Login required")
    return session


def _require_csrf(request: Request, session: dict[str, str | int]) -> None:
    if not _same_origin(request):
        raise HTTPException(status_code=403, detail="Same-origin request required")
    token = request.headers.get("X-CSRF-Token")
    if not session_store.verify_csrf(session, token):
        raise HTTPException(status_code=403, detail="CSRF validation failed")


@app.post("/api/login")
def browser_login(payload: LoginRequest, request: Request):
    if not _local_or_https(request):
        raise HTTPException(status_code=403, detail="Login is available only on localhost, private-network IPs, or HTTPS")
    if not _same_origin(request):
        raise HTTPException(status_code=403, detail="Same-origin request required")
    expected = os.environ.get("SALES_LOGIN_PASSWORD", "")
    if len(expected) < 12:
        raise HTTPException(status_code=503, detail="Local login is not configured securely")
    client_key = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with _login_failures_lock:
        attempts = [stamp for stamp in _login_failures.get(client_key, []) if now - stamp < LOGIN_FAILURE_WINDOW_SECONDS]
        _login_failures[client_key] = attempts
        if len(attempts) >= LOGIN_FAILURE_LIMIT:
            raise HTTPException(status_code=429, detail="Too many login attempts; try again later")
    if not hmac.compare_digest(payload.password, expected):
        with _login_failures_lock:
            _login_failures.setdefault(client_key, []).append(now)
            if len(_login_failures) > 1024:
                expired_before = now - LOGIN_FAILURE_WINDOW_SECONDS
                for key in list(_login_failures):
                    _login_failures[key] = [stamp for stamp in _login_failures[key] if stamp >= expired_before]
                    if not _login_failures[key]:
                        _login_failures.pop(key, None)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    with _login_failures_lock:
        _login_failures.pop(client_key, None)

    created = session_store.create_session("local-single-user", ttl_seconds=SESSION_TTL_SECONDS)
    secure_cookie = request.url.scheme == "https"
    response = JSONResponse({"authenticated": True, "csrf_token": created["csrf_token"]})
    response.set_cookie(
        SESSION_COOKIE, str(created["token"]), max_age=SESSION_TTL_SECONDS,
        httponly=True, secure=secure_cookie, samesite="lax", path="/api",
    )
    response.set_cookie(
        CSRF_COOKIE, str(created["csrf_token"]), max_age=SESSION_TTL_SECONDS,
        httponly=False, secure=secure_cookie, samesite="lax", path="/api",
    )
    response.headers["Cache-Control"] = "no-store, private"
    return response


@app.post("/api/logout")
def browser_logout(request: Request):
    session = _require_browser_session(request)
    _require_csrf(request, session)
    session_store.revoke_session(request.cookies.get(SESSION_COOKIE))
    response = JSONResponse({"authenticated": False})
    secure_cookie = request.url.scheme == "https"
    response.delete_cookie(SESSION_COOKIE, path="/api", httponly=True, secure=secure_cookie, samesite="lax")
    response.delete_cookie(CSRF_COOKIE, path="/api", httponly=False, secure=secure_cookie, samesite="lax")
    response.headers["Cache-Control"] = "no-store, private"
    return response


@app.get("/api/csrf")
def browser_csrf(request: Request):
    session = _require_browser_session(request)
    token = request.cookies.get(CSRF_COOKIE)
    if not session_store.verify_csrf(session, token):
        raise HTTPException(status_code=403, detail="CSRF validation failed")
    response = JSONResponse({"csrf_token": token})
    response.headers["Cache-Control"] = "no-store, private"
    return response


@app.get("/api/session")
def browser_session(request: Request):
    session = _request_session(request)
    response = JSONResponse({"authenticated": session is not None})
    response.headers["Cache-Control"] = "no-store, private"
    return response


@app.get("/api/companies")
def browser_list_companies(
    request: Request,
    q: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1),
    offset: int = Query(default=0, ge=0, le=100000),
):
    _require_browser_session(request)
    if q is not None and len(q) > 200:
        raise HTTPException(status_code=400, detail="Search query is too long")
    return db.list_companies_page(q, limit=min(limit, 50), offset=offset)


@app.get("/api/companies/{company_id}")
def browser_get_company(company_id: str, request: Request):
    _require_browser_session(request)
    row = db.get_company(company_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return row


class CompanyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    authorized_people: list[str] = Field(default_factory=list, max_length=50)
    phone_numbers: list[str] = Field(default_factory=list, max_length=50)
    address: str | None = Field(default=None, max_length=3000)
    website: str | None = Field(default=None, max_length=300)
    email: str | None = Field(default=None, max_length=320)
    tax_office: str | None = Field(default=None, max_length=200)
    tax_number: str | None = Field(default=None, max_length=50)
    mersis_number: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator("name")
    @classmethod
    def clean_company_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Firma unvanı boş olamaz")
        return value

    @field_validator("authorized_people", "phone_numbers")
    @classmethod
    def clean_repeated_values(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value and value.strip()]


@app.post("/api/companies", status_code=201)
def browser_create_company(payload: CompanyCreate, request: Request) -> dict:
    session = _require_browser_session(request)
    _require_csrf(request, session)
    record = {"id": str(uuid4()), **payload.model_dump()}
    return db.create_company(record)


@app.put("/api/companies/{company_id}")
def browser_update_company(company_id: str, payload: CompanyCreate, request: Request) -> dict:
    session = _require_browser_session(request)
    _require_csrf(request, session)
    record = db.update_company(company_id, payload.model_dump())
    if record is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return record


class ContactCreate(BaseModel):
    company_id: str
    name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=5000)


class MeetingCreate(BaseModel):
    company_id: str
    meeting_date: str = Field(min_length=1, max_length=40)
    notes: str = Field(min_length=1, max_length=10000)
    meeting_type: str = Field(default="phone", pattern=r"^(phone|visit)$")
    topic: str = Field(default="Genel görüşme", min_length=1, max_length=200)

    @field_validator("meeting_date")
    @classmethod
    def validate_iso_datetime(cls, value: str) -> str:
        from datetime import date, datetime

        try:
            if "T" in value or " " in value:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
            else:
                date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("meeting_date must be an ISO date or datetime") from exc
        return value


@app.get("/api/meetings")
def browser_list_meetings(request: Request) -> list[dict]:
    _require_browser_session(request)
    return db.list_meetings()


@app.post("/api/meetings", status_code=201)
def browser_create_meeting(payload: MeetingCreate, request: Request) -> dict:
    session = _require_browser_session(request)
    _require_csrf(request, session)
    if not db.company_exists(payload.company_id):
        raise HTTPException(status_code=404, detail="Company not found; meeting was not saved")
    record = {"id": str(uuid4()), **payload.model_dump()}
    saved = db.create_meeting(record)
    company = db.get_company(payload.company_id)
    return {**saved, "company_name": company["name"] if company else "Firma bulunamadı"}


@app.put("/api/meetings/{meeting_id}")
def browser_update_meeting(meeting_id: str, payload: MeetingCreate, request: Request) -> dict:
    session = _require_browser_session(request)
    _require_csrf(request, session)
    if not db.company_exists(payload.company_id):
        raise HTTPException(status_code=404, detail="Company not found; meeting was not updated")
    updated = db.update_meeting(meeting_id, payload.model_dump())
    if updated is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return updated


class FollowUpCreate(BaseModel):
    company_id: str
    title: str = Field(min_length=1, max_length=300)
    due_date: str = Field(min_length=1, max_length=40)

    @field_validator("due_date")
    @classmethod
    def validate_due_date(cls, value: str) -> str:
        from datetime import date, datetime
        try:
            if "T" in value or " " in value:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
            else:
                date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("due_date must be an ISO date or datetime") from exc
        return value


@app.get("/api/follow-ups")
def browser_list_follow_ups(request: Request) -> list[dict]:
    _require_browser_session(request)
    return db.list_follow_ups()


@app.post("/api/follow-ups", status_code=201)
def browser_create_follow_up(payload: FollowUpCreate, request: Request) -> dict:
    session = _require_browser_session(request)
    _require_csrf(request, session)
    if not db.company_exists(payload.company_id):
        raise HTTPException(status_code=404, detail="Company not found; follow-up was not saved")
    record = {"id": str(uuid4()), **payload.model_dump(), "status": "open",
              "created_at": datetime.now(timezone.utc).isoformat()}
    return db.create_follow_up(record)


@app.post("/api/follow-ups/{task_id}/complete")
def browser_complete_follow_up(task_id: str, request: Request) -> dict:
    session = _require_browser_session(request)
    _require_csrf(request, session)
    record = db.complete_follow_up(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Follow-up task not found")
    return record


@app.get("/api/meeting-report", response_class=HTMLResponse)
def browser_meeting_report(
    request: Request,
    date_from: str | None = Query(default=None, max_length=10),
    date_to: str | None = Query(default=None, max_length=10),
    meeting_type: str = Query(default="all", pattern=r"^(all|phone|visit)$"),
) -> HTMLResponse:
    _require_browser_session(request)
    records = db.list_meetings()
    if date_from:
        records = [r for r in records if str(r["meeting_date"])[:10] >= date_from]
    if date_to:
        records = [r for r in records if str(r["meeting_date"])[:10] <= date_to]
    if meeting_type != "all":
        records = [r for r in records if r.get("meeting_type", "phone") == meeting_type]
    import html
    rows = []
    for record in records:
        kind = "Telefon görüşmesi" if record.get("meeting_type") == "phone" else "Ziyaret"
        rows.append("<tr><td>" + html.escape(str(record.get("company_name") or "")) +
                    "</td><td>" + html.escape(str(record.get("meeting_date") or "")) +
                    "</td><td>" + kind + "</td><td>" +
                    html.escape(str(record.get("topic") or "Genel görüşme")) + "</td></tr>")
    table_rows = "".join(rows) or '<tr><td colspan="4">Seçilen filtrelerde görüşme bulunamadı.</td></tr>'
    page = """<!doctype html><html lang="tr"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
    <title>Görüşme Raporu</title><style>body{font:14px/1.5 system-ui,sans-serif;color:#172b45;margin:24px}
    h1{font-size:22px}p{color:#66758a}.actions{display:flex;gap:8px;margin:18px 0}
    button{padding:10px 14px;border:1px solid #ccd5e1;border-radius:8px;background:#fff;cursor:pointer}
    table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:10px;border-bottom:1px solid #e3e8ef}
    th{color:#66758a}@media print{.actions{display:none}body{margin:0}}</style>
    <h1>Görüşme Raporu</h1><p>Rapor yalnızca firma, tarih, görüşme şekli ve görüşme konusunu içerir. Görüşme notları dahil edilmez.</p>
    <div class="actions"><button onclick="window.print()">Yazdır / PDF kaydet</button><button onclick="window.close()">Kapat</button></div>
    <table><thead><tr><th>Firma</th><th>Tarih</th><th>Görüşme şekli</th><th>Görüşme konusu</th></tr></thead><tbody>""" + table_rows + """</tbody></table></html>"""
    response = HTMLResponse(page)
    response.headers["Cache-Control"] = "no-store, private"
    return response



class ProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    unit_price: int = Field(ge=0, le=99999999)


class QuoteRequest(BaseModel):
    company_id: str | None = None
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    lines: list[QuoteLine] = Field(min_length=1, max_length=100)


@app.get("/api/products")
def browser_list_products(request: Request) -> list[dict]:
    """List catalog items for the authenticated quotation editor."""
    _require_browser_session(request)
    return db.list_products()


@app.get("/api/quotes")
def browser_list_quotes(request: Request) -> list[dict]:
    _require_browser_session(request)
    records = db.list_quotations()
    companies = {row["id"]: row["name"] for row in db.list_companies()}
    return [
        {
            "id": row["id"],
            "company_id": row.get("company_id"),
            "company_name": companies.get(row.get("company_id"), "Firma belirtilmedi"),
            "currency": row["currency"],
            "total": row["total"],
            "status": row["status"],
            "created_at": row["created_at"],
        }
        for row in records
    ]


@app.post("/api/quotes", status_code=201)
def browser_create_quote(payload: QuoteRequest, request: Request) -> dict:
    session = _require_browser_session(request)
    _require_csrf(request, session)
    if payload.company_id and not db.company_exists(payload.company_id):
        raise HTTPException(status_code=404, detail="Company not found; quotation was not saved")
    calculated = calculate_quote(payload.lines, payload.currency)
    record = {
        "id": str(uuid4()),
        "company_id": payload.company_id,
        "currency": calculated["currency"],
        "subtotal": calculated["subtotal"],
        "tax_rate": calculated["tax_rate"],
        "tax_amount": calculated["tax_amount"],
        "total": calculated["total"],
        "status": "draft",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "lines": [
            {
                "id": str(uuid4()),
                "description": line.description,
                "quantity": str(line.quantity),
                "unit_price": str(line.unit_price),
                "line_total": calculated["lines"][index]["line_total"],
            }
            for index, line in enumerate(payload.lines)
        ],
    }
    return db.create_quotation(record)


@app.get("/api/quotes/{quotation_id}/excel")
def browser_quotation_excel(quotation_id: str, request: Request) -> Response:
    _require_browser_session(request)
    record = db.get_quotation(quotation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Quotation not found")
    company = db.get_company(record["company_id"]) if record.get("company_id") else None
    content = render_quote_excel(record, company)
    response = Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="Teklif_{quotation_id[:8].upper()}.xlsx"'},
    )
    response.headers["Cache-Control"] = "no-store, private"
    return response


@app.get("/api/quotes/{quotation_id}/document", response_class=HTMLResponse)
def browser_quotation_document(quotation_id: str, request: Request) -> HTMLResponse:
    _require_browser_session(request)
    record = db.get_quotation(quotation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Quotation not found")
    company = db.get_company(record["company_id"]) if record.get("company_id") else None
    response = HTMLResponse(render_quotation_html(record, company))
    response.headers["Content-Disposition"] = 'inline; filename="teklif-taslagi.html"'
    response.headers["Cache-Control"] = "no-store, private"
    return response


class TemplateGenerationRequest(BaseModel):
    values: dict[str, str] = Field(default_factory=dict, max_length=500)


@app.post("/api/templates", status_code=201)
async def browser_upload_template(request: Request, file: UploadFile = File(...)) -> dict:
    session = _require_browser_session(request)
    _require_csrf(request, session)
    try:
        return await template_documents.save_upload(file)
    finally:
        await file.close()


@app.get("/api/templates")
def browser_list_templates(request: Request) -> list[dict]:
    _require_browser_session(request)
    root = template_documents.storage_root()
    results = []
    for meta_path in root.glob("*.json"):
        try:
            record = __import__("json").loads(meta_path.read_text(encoding="utf-8"))
            if (root / f"{record.get('id', '')}.source").is_file():
                results.append({
                    "id": record["id"], "name": record["name"],
                    "format": record["format"], "fields": record["fields"],
                    "size": record["size"],
                })
        except (OSError, ValueError, KeyError):
            # Skip incomplete metadata; do not expose filesystem paths or raw errors.
            continue
    return sorted(results, key=lambda item: item["name"].casefold())


@app.get("/api/templates/{template_id}")
def browser_get_template(template_id: str, request: Request) -> dict:
    _require_browser_session(request)
    return template_documents.read_metadata(template_id)


@app.post("/api/templates/{template_id}/generate")
def browser_generate_template(
    template_id: str, payload: TemplateGenerationRequest, request: Request
):
    session = _require_browser_session(request)
    _require_csrf(request, session)
    metadata = template_documents.read_metadata(template_id)
    unknown = sorted(set(payload.values) - set(metadata["fields"]))
    if unknown:
        raise HTTPException(
            status_code=422,
            detail={"message": "Unknown template fields", "unknown_fields": unknown},
        )
    output, download_name, suffix = template_documents.generate_output(
        template_id, payload.values
    )
    media_types = {
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".pdf": "application/pdf",
    }
    response = FileResponse(
        output, media_type=media_types[suffix], filename=download_name
    )
    response.headers["Cache-Control"] = "no-store, private"
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "stage": "prototype", "storage": "sqlite"}


@app.get("/")
def root():
    return FileResponse(Path(__file__).resolve().parent.parent / "web" / "index.html")


@app.get("/api-info")
def api_info() -> dict[str, str]:
    return {"name": "Sales AI Platform API", "docs": "/docs", "status": "prototype"}


@app.post("/companies", status_code=201)
def create_company(payload: CompanyCreate) -> dict:
    record = {"id": str(uuid4()), **payload.model_dump()}
    return db.create_company(record)


@app.get("/companies")
def list_companies(search: str | None = Query(default=None, max_length=200)) -> list[dict]:
    """List persisted companies; optional search filters name and website."""
    return db.list_companies(search)


@app.post("/companies/{company_id}/contacts", status_code=201)
def create_contact(company_id: str, payload: ContactCreate) -> dict:
    if payload.company_id != company_id:
        raise HTTPException(status_code=400, detail="Path and payload company_id must match")
    if not db.company_exists(company_id):
        raise HTTPException(status_code=404, detail="Company not found; contact was not saved")
    record = {"id": str(uuid4()), **payload.model_dump()}
    return db.create_contact(record)


@app.get("/companies/{company_id}/contacts")
def list_company_contacts(company_id: str) -> list[dict]:
    if not db.company_exists(company_id):
        raise HTTPException(status_code=404, detail="Company not found")
    return db.list_company_contacts(company_id)


@app.post("/meetings", status_code=201)
def create_meeting(payload: MeetingCreate) -> dict:
    if not db.company_exists(payload.company_id):
        raise HTTPException(status_code=404, detail="Company not found; meeting was not saved")
    record = {"id": str(uuid4()), **payload.model_dump()}
    return db.create_meeting(record)


@app.get("/companies/{company_id}/meetings")
def list_company_meetings(company_id: str) -> list[dict]:
    if not db.company_exists(company_id):
        raise HTTPException(status_code=404, detail="Company not found")
    return db.list_company_meetings(company_id)


@app.post("/products", status_code=201)
def create_product(payload: ProductCreate) -> dict:
    record = {**payload.model_dump(), "id": str(uuid4()), "unit_price": str(payload.unit_price)}
    try:
        return db.create_product(record)
    except Exception as exc:
        # Avoid exposing database internals to clients; duplicate SKU is a client conflict.
        if "UNIQUE constraint failed: products.sku" in str(exc):
            raise HTTPException(status_code=409, detail="SKU already exists") from exc
        raise


@app.get("/products")
def list_products() -> list[dict]:
    return db.list_products()


@app.post("/quotes/calculate")
def quote_calculate(payload: QuoteRequest) -> dict:
    # Pure deterministic calculation. This endpoint does not save or approve a quotation.
    return calculate_quote(payload.lines, payload.currency)


@app.post("/quotes", status_code=201)
def create_quotation(payload: QuoteRequest) -> dict:
    # Persist the exact descriptions/prices used now, so later product price changes
    # cannot silently alter this draft. This is a draft only, never an approval.
    if payload.company_id and not db.company_exists(payload.company_id):
        raise HTTPException(status_code=404, detail="Company not found; quotation was not saved")
    calculated = calculate_quote(payload.lines, payload.currency)
    record = {
        "id": str(uuid4()),
        "company_id": payload.company_id,
        "currency": calculated["currency"],
        "subtotal": calculated["subtotal"],
        "tax_rate": calculated["tax_rate"],
        "tax_amount": calculated["tax_amount"],
        "total": calculated["total"],
        "status": "draft",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "lines": [
            {
                "id": str(uuid4()),
                "description": line.description,
                "quantity": str(line.quantity),
                "unit_price": str(line.unit_price),
                "line_total": calculated["lines"][index]["line_total"],
            }
            for index, line in enumerate(payload.lines)
        ],
    }
    return db.create_quotation(record)


@app.get("/quotes")
def list_quotations() -> list[dict]:
    return db.list_quotations()


@app.get("/quotes/{quotation_id}")
def get_quotation(quotation_id: str) -> dict:
    record = db.get_quotation(quotation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Quotation not found")
    return record


@app.get("/quotes/{quotation_id}/document", response_class=HTMLResponse)
def quotation_document(quotation_id: str) -> HTMLResponse:
    """Render a saved quotation draft as printable HTML; browser can save it as PDF."""
    record = db.get_quotation(quotation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Quotation not found")
    company = db.get_company(record["company_id"]) if record.get("company_id") else None
    response = HTMLResponse(render_quotation_html(record, company))
    response.headers["Content-Disposition"] = 'inline; filename="teklif-taslagi.html"'
    response.headers["Cache-Control"] = "no-store, private"
    return response
