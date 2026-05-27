from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from iu.db import (
    get_db, init_db, get_recent_items, get_active_persons, get_active_products,
    get_items_by_person, get_items_by_product, search_items, get_item_count,
    get_person_item_counts, get_latest_report,
)

app = FastAPI(title="Information Union", docs_url="/docs")

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
