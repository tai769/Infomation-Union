from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from iu.config import load_config
from iu.db import (
    get_db, init_db, get_recent_items, get_active_persons, get_active_products,
    get_items_by_person, get_items_by_product, search_items, get_item_count,
    get_person_item_counts, get_latest_report,
)

logger = logging.getLogger(__name__)

app = FastAPI(title="Information Union", docs_url="/docs")

# Start scheduler on app startup
@app.on_event("startup")
async def startup_event():
    from iu.scheduler import start_scheduler
    config = load_config()
    app.state.scheduler = start_scheduler(config)
    logger.info("Scheduler started with web server")

@app.on_event("shutdown")
async def shutdown_event():
    if hasattr(app.state, "scheduler"):
        app.state.scheduler.shutdown()
        logger.info("Scheduler stopped")

STATIC_DIR = Path(__file__).parent / "static"
TEMPLATES_DIR = Path(__file__).parent / "templates"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _get_conn():
    conn = get_db()
    init_db(conn)
    return conn


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    conn = _get_conn()
    items = get_recent_items(conn, 20)
    persons = get_person_item_counts(conn)
    total = get_item_count(conn)
    report = get_latest_report(conn)
    conn.close()
    return templates.TemplateResponse(
        request=request, name="index.html",
        context={"items": items, "persons": persons, "total": total, "report": report}
    )


@app.get("/items", response_class=HTMLResponse)
async def items_list(
    request: Request,
    person: str = Query("", description="Filter by person ID"),
    product: str = Query("", description="Filter by product ID"),
    source: str = Query("", description="Filter by source"),
    q: str = Query("", description="Search query"),
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=100),
):
    conn = _get_conn()
    offset = (page - 1) * per_page

    if q:
        items = search_items(conn, q, limit=per_page)
    elif person:
        items = get_items_by_person(conn, person)
        items = items[offset:offset + per_page]
    elif product:
        items = get_items_by_product(conn, product)
        items = items[offset:offset + per_page]
    else:
        items = get_recent_items(conn, per_page)

    for item in items:
        item["media_urls"] = json.loads(item.get("media_urls", "[]") or "[]")
        item["metadata"] = json.loads(item.get("metadata", "{}") or "{}")

    persons = get_active_persons(conn)
    products = get_active_products(conn)
    conn.close()

    return templates.TemplateResponse(
        request=request, name="items.html",
        context={
            "items": items, "persons": persons, "products": products,
            "current_person": person, "current_product": product,
            "current_source": source, "query": q, "page": page,
        }
    )


@app.get("/persons", response_class=HTMLResponse)
async def persons_list(request: Request):
    conn = _get_conn()
    persons = get_person_item_counts(conn)
    conn.close()
    return templates.TemplateResponse(
        request=request, name="persons.html", context={"persons": persons}
    )


@app.get("/persons/{person_id}", response_class=HTMLResponse)
async def person_detail(request: Request, person_id: str):
    conn = _get_conn()
    items = get_items_by_person(conn, person_id)
    persons = get_active_persons(conn)
    person = next((p for p in persons if p["id"] == person_id), None)
    conn.close()
    return templates.TemplateResponse(
        request=request, name="person.html",
        context={"person": person, "items": items}
    )


@app.get("/products", response_class=HTMLResponse)
async def products_list(request: Request):
    conn = _get_conn()
    products = get_active_products(conn)
    conn.close()
    return templates.TemplateResponse(
        request=request, name="products.html", context={"products": products}
    )


@app.get("/products/{product_id}", response_class=HTMLResponse)
async def product_detail(request: Request, product_id: str):
    conn = _get_conn()
    items = get_items_by_product(conn, product_id)
    products = get_active_products(conn)
    product = next((p for p in products if p["id"] == product_id), None)
    conn.close()
    return templates.TemplateResponse(
        request=request, name="product.html",
        context={"product": product, "items": items}
    )


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    config = load_config()
    return templates.TemplateResponse(
        request=request, name="settings.html",
        context={"config": config}
    )


@app.post("/api/settings/email")
async def update_email_settings(request: Request):
    from iu.config import save_config
    config = load_config()

    data = await request.json()
    config.email.enabled = data.get("enabled", False)
    config.email.smtp_host = data.get("smtp_host", "")
    config.email.smtp_port = int(data.get("smtp_port", 587))
    config.email.smtp_user = data.get("smtp_user", "")
    config.email.smtp_password = data.get("smtp_password", "")
    config.email.from_addr = data.get("from_addr", "")
    config.email.to_addrs = [a.strip() for a in data.get("to_addrs", []) if a.strip()]

    save_config(config)
    return {"status": "ok", "message": "Email settings saved"}


@app.post("/api/settings/email/test")
async def test_email(request: Request):
    from iu.delivery.email_report import send_report
    config = load_config()

    if not config.email.enabled:
        return {"status": "error", "message": "Email is not enabled"}

    try:
        conn = _get_conn()
        await send_report(conn, config)
        conn.close()
        return {"status": "ok", "message": f"Test email sent to {config.email.to_addrs}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/settings/email/add-recipient")
async def add_recipient(request: Request):
    from iu.config import save_config
    config = load_config()

    data = await request.json()
    email = data.get("email", "").strip()
    if email and email not in config.email.to_addrs:
        config.email.to_addrs.append(email)
        save_config(config)

    return {"status": "ok", "recipients": config.email.to_addrs}


@app.post("/api/settings/email/remove-recipient")
async def remove_recipient(request: Request):
    from iu.config import save_config
    config = load_config()

    data = await request.json()
    email = data.get("email", "").strip()
    if email in config.email.to_addrs:
        config.email.to_addrs.remove(email)
        save_config(config)

    return {"status": "ok", "recipients": config.email.to_addrs}


@app.get("/api/items")
async def api_items(
    person: str = "",
    product: str = "",
    source: str = "",
    q: str = "",
    limit: int = Query(50, ge=1, le=200),
):
    conn = _get_conn()
    if q:
        items = search_items(conn, q, limit)
    elif person:
        items = get_items_by_person(conn, person)[:limit]
    elif product:
        items = get_items_by_product(conn, product)[:limit]
    else:
        items = get_recent_items(conn, limit)

    for item in items:
        item["media_urls"] = json.loads(item.get("media_urls", "[]") or "[]")
        item["metadata"] = json.loads(item.get("metadata", "{}") or "{}")

    conn.close()
    return {"items": items, "count": len(items)}
