"""FastAPI live operations dashboard."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import re

from fastapi import FastAPI, Request, Header, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from database.models import init_db
from database.repository import (
    add_do_not_contact,
    get_dashboard_stats,
    get_leads,
    get_recent_logs,
    get_verified_leads_with_email,
    mark_outreach_opted_out,
    mark_outreach_replied,
    log_outreach,
)
from config.settings import DASHBOARD_API_KEY
from database.repository import get_listing
from outreach.email_sender import EmailSender
from config.settings import SENDGRID_API_KEY, WHATSAPP_API_TOKEN, AT_API_KEY
from dashboard.control import get_agent_status, execute_control, handle_chat
import csv
import io
from fastapi.responses import StreamingResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Kenya Outreach Agent", version="1.0.0", lifespan=lifespan)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

static_dir = BASE_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


class OptOutRequest(BaseModel):
    contact: str
    reason: str = "manual_opt_out"


class InboundMessage(BaseModel):
    channel: str
    from_contact: str
    message: str | None = None
    event: str | None = None


def _is_opt_out(message: str | None, event: str | None) -> bool:
    if event and event.strip().lower() in {"opt_out", "unsubscribe", "stop", "cancel", "end"}:
        return True
    if not message:
        return False
    return bool(re.search(r"\b(stop|unsubscribe|cancel|end|quit|opt out|no more)\b", message, re.IGNORECASE))


@app.post("/api/inbound")
async def api_inbound(body: InboundMessage):
    if _is_opt_out(body.message, body.event):
        marked = mark_outreach_opted_out(body.from_contact, reason="user_reply")
        return JSONResponse(
            {"status": "opted_out", "recipient": body.from_contact, "updated": marked}
        )

    if body.message:
        marked = mark_outreach_replied(body.from_contact)
        return JSONResponse(
            {"status": "replied", "recipient": body.from_contact, "updated": marked}
        )

    return JSONResponse({"status": "ignored", "reason": "no_message"})


def require_dashboard_auth(x_api_key: str | None = Header(None)):
    if not DASHBOARD_API_KEY:
        return True
    if x_api_key == DASHBOARD_API_KEY:
        return True
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, _auth: bool = Depends(require_dashboard_auth)):
    stats = get_dashboard_stats()
    logs = get_recent_logs(limit=20)
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "stats": stats, "logs": logs},
    )


@app.get("/api/stats")
async def api_stats(_auth: bool = Depends(require_dashboard_auth)):
    return get_dashboard_stats()


@app.get("/api/leads")
async def api_leads(
    page: int = 1,
    per_page: int = 50,
    priority: str | None = None,
    has_contact: str | None = None,
    q: str | None = None,
    min_score: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    _auth: bool = Depends(require_dashboard_auth),
):
    return get_leads(page=page, per_page=per_page, priority=priority, has_contact=has_contact, q=q, min_score=min_score, start_date=start_date, end_date=end_date)


@app.get("/api/logs")
async def api_logs(limit: int = 50, _auth: bool = Depends(require_dashboard_auth)):
    return get_recent_logs(limit=limit)


@app.get("/api/leads/export")
async def api_leads_export(
    page: int = 1,
    per_page: int = 10000,
    priority: str | None = None,
    has_contact: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    q: str | None = None,
    _auth: bool = Depends(require_dashboard_auth),
):
    # export current filter selection as CSV
    data = get_leads(page=page, per_page=per_page, priority=priority, has_contact=has_contact, q=q, start_date=start_date, end_date=end_date)
    items = data.get("items", [])

    def iter_csv():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["id", "name", "address", "county", "category", "phone", "email", "website_url", "website_status", "phone_verified", "email_verified", "created_at", "score", "priority"])
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)
        for it in items:
            writer.writerow([
                it.get("id"),
                it.get("name"),
                it.get("address"),
                it.get("county"),
                it.get("category"),
                it.get("phone"),
                it.get("email"),
                it.get("website_url"),
                it.get("website_status"),
                it.get("phone_verified"),
                it.get("email_verified"),
                it.get("created_at"),
                it.get("score"),
                it.get("priority"),
            ])
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)

    return StreamingResponse(iter_csv(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=leads_export.csv"})


class SendTestEmailRequest(BaseModel):
    listing_id: str


class WhatsAppTestRequest(BaseModel):
    phone_number: str
    template_name: str | None = None


@app.post("/api/leads/send_test_email")
async def api_send_test_email(body: SendTestEmailRequest, _auth: bool = Depends(require_dashboard_auth)):
    listing = get_listing(body.listing_id)
    if not listing:
        return JSONResponse({"status": "error", "message": "listing not found"}, status_code=404)

    # send to listing.email if available, else error
    to = listing.get("email")
    if not to:
        return JSONResponse({"status": "error", "message": "listing has no email"}, status_code=400)

    sender = EmailSender(api_key=SENDGRID_API_KEY)
    try:
        result = await sender.send(to, listing)
        return JSONResponse({"status": "ok", "result": result})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/whatsapp_test")
async def api_whatsapp_test(body: WhatsAppTestRequest, _auth: bool = Depends(require_dashboard_auth)):
    from outreach.whatsapp_sender import WhatsAppSender
    from config.templates import WHATSAPP_TEMPLATES, select_whatsapp_template, render_template

    if not body.phone_number:
        return JSONResponse({"status": "error", "message": "phone_number is required"}, status_code=400)

    sender = WhatsAppSender()
    template_name = body.template_name or list(WHATSAPP_TEMPLATES.values())[0]["name"]
    template_body = None
    for template in WHATSAPP_TEMPLATES.values():
        if template["name"] == template_name:
            template_body = template["body"]
            break

    if not template_body:
        return JSONResponse({"status": "error", "message": "template_name not found"}, status_code=400)

    message = render_template(template_body, business_name="Test Business")
    try:
        result = await sender.send_text(body.phone_number, message)
        return JSONResponse({"status": "ok", "result": result})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/api/health")
async def api_health():
    try:
        get_dashboard_stats()
        db_ok = True
    except Exception:
        db_ok = False

    redis_ok = False
    try:
        import redis as sync_redis
        from config.settings import REDIS_URL
        r = sync_redis.from_url(REDIS_URL, socket_connect_timeout=2)
        r.ping()
        redis_ok = True
    except Exception:
        pass

    return {
        "db": db_ok,
        "redis": redis_ok,
        "sendgrid": bool(SENDGRID_API_KEY),
        "whatsapp": bool(WHATSAPP_API_TOKEN),
        "africas_talking": bool(AT_API_KEY),
    }


@app.post("/api/opt-out")
async def api_opt_out(body: OptOutRequest, _auth: bool = Depends(require_dashboard_auth)):
    add_do_not_contact(body.contact, body.reason)
    return JSONResponse({"status": "ok", "contact": body.contact})


# ---------------------------------------------------------------------------
# Agent Control Panel + AI Chat
# ---------------------------------------------------------------------------
class ControlRequest(BaseModel):
    action: str
    params: dict = {}


class ChatRequest(BaseModel):
    message: str


class BatchTestRequest(BaseModel):
    limit: int = 10
    channel: str = "email"


@app.get("/api/agent/status")
async def api_agent_status(_auth: bool = Depends(require_dashboard_auth)):
    try:
        return get_agent_status()
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/agent/control")
async def api_agent_control(body: ControlRequest, _auth: bool = Depends(require_dashboard_auth)):
    try:
        result = execute_control(body.action, body.params or {})
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/agent/chat")
async def api_agent_chat(body: ChatRequest, _auth: bool = Depends(require_dashboard_auth)):
    try:
        result = await handle_chat(body.message)
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/leads/batch_test")
async def api_batch_test(body: BatchTestRequest, _auth: bool = Depends(require_dashboard_auth)):
    """Send a controlled batch test email to leads with an email address."""
    from config.settings import DRY_RUN as _DRY

    limit = max(1, min(body.limit, 200))
    leads = get_verified_leads_with_email(limit=limit)

    sent = 0
    failed = 0
    errors = []
    sender = EmailSender(api_key=SENDGRID_API_KEY)
    for lead in leads:
        email = lead.get("email")
        if not email:
            continue
        try:
            result = await sender.send(email, lead)
            log_outreach(
                lead.get("id", ""),
                "email",
                "batch_test",
                email,
                result.get("status", "sent"),
                result.get("error_message"),
            )
            if result.get("status") in ("sent", "delivered") or (result.get("status_code") in (200, 202)):
                sent += 1
            else:
                failed += 1
                errors.append(f"{lead.get('name')}: {result.get('status')}")
        except Exception as e:
            failed += 1
            errors.append(f"{lead.get('name')}: {e}")
            log_outreach(lead.get("id", ""), "email", "batch_test", email, "failed", str(e))
        await asyncio.sleep(1)  # gentle pacing

    return JSONResponse({
        "status": "ok",
        "selected": len(leads),
        "sent": sent,
        "failed": failed,
        "dry_run": _DRY,
        "errors": errors[:20],
    })
