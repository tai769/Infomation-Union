from __future__ import annotations

import json
import logging
import smtplib
import sqlite3
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from jinja2 import Template

from iu.config import AppConfig
from iu.db import get_items_by_date, get_active_persons, get_active_products, get_latest_report, get_topics, get_top_items

logger = logging.getLogger(__name__)

EMAIL_TEMPLATE = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><style>
body { font-family: -apple-system, 'Segoe UI', sans-serif; color: #333; max-width: 700px; margin: 0 auto; padding: 20px; background: #f5f5f5; }
.container { background: white; border-radius: 12px; padding: 32px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
h1 { color: #1a1a2e; font-size: 22px; margin: 0 0 4px; }
.subtitle { color: #999; font-size: 13px; margin-bottom: 24px; }
.summary-box { background: #f0f4ff; border-radius: 8px; padding: 16px; margin-bottom: 24px; border-left: 4px solid #1a1a2e; }
.summary-box .label { font-size: 12px; color: #666; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px; }
.summary-box .text { font-size: 15px; line-height: 1.6; }
h2 { color: #1a1a2e; font-size: 16px; margin: 28px 0 12px; padding-bottom: 6px; border-bottom: 1px solid #eee; }
.top-item { background: #fff; border: 1px solid #e8e8e8; border-radius: 8px; padding: 14px; margin-bottom: 10px; }
.top-item .rank { display: inline-block; background: #1a1a2e; color: white; width: 24px; height: 24px; border-radius: 50%; text-align: center; line-height: 24px; font-size: 12px; font-weight: 600; margin-right: 8px; }
.top-item .score { float: right; background: #e8f5e9; color: #2e7d32; padding: 2px 8px; border-radius: 4px; font-size: 11px; }
.top-item .title { font-weight: 600; font-size: 14px; }
.top-item .title a { color: #1565c0; text-decoration: none; }
.top-item .meta { font-size: 12px; color: #999; margin-top: 4px; }
.topic-card { background: #fff; border: 1px solid #e8e8e8; border-radius: 8px; padding: 14px; margin-bottom: 10px; }
.topic-card .topic-name { font-weight: 600; font-size: 14px; }
.topic-card .trend { display: inline-block; padding: 2px 6px; border-radius: 3px; font-size: 11px; margin-left: 6px; }
.trend-rising { background: #e8f5e9; color: #2e7d32; }
.trend-stable { background: #fff3e0; color: #e65100; }
.trend-falling { background: #fce4ec; color: #c62828; }
.topic-card .summary { font-size: 13px; color: #555; margin-top: 6px; line-height: 1.5; }
.topic-card .count { font-size: 11px; color: #999; margin-top: 4px; }
.person-section { margin-bottom: 16px; }
.person-name { font-weight: 600; font-size: 14px; color: #1a1a2e; margin-bottom: 6px; }
.person-item { font-size: 13px; color: #555; padding: 4px 0; border-bottom: 1px solid #f5f5f5; }
.person-item a { color: #1565c0; text-decoration: none; }
.stats { display: flex; gap: 16px; margin-bottom: 24px; }
.stat { text-align: center; flex: 1; }
.stat .num { font-size: 28px; font-weight: 700; color: #1a1a2e; }
.stat .label { font-size: 12px; color: #999; }
.footer { margin-top: 32px; padding-top: 16px; border-top: 1px solid #eee; font-size: 12px; color: #999; text-align: center; }
</style></head>
<body>
<div class="container">

<h1>AI Intelligence Report</h1>
<div class="subtitle">{{ week_start }} ~ {{ week_end }} · {{ total }} items from {{ source_count }} sources</div>

<div class="stats">
    <div class="stat"><div class="num">{{ total }}</div><div class="label">Items</div></div>
    <div class="stat"><div class="num">{{ persons|length }}</div><div class="label">Persons</div></div>
    <div class="stat"><div class="num">{{ topics|length }}</div><div class="label">Topics</div></div>
</div>

{% if week_summary %}
<div class="summary-box">
    <div class="label">This Week in AI</div>
    <div class="text">{{ week_summary }}</div>
</div>
{% endif %}

<h2>Top {{ top_items|length }} Most Important</h2>
{% for item in top_items %}
<div class="top-item">
    <span class="rank">{{ loop.index }}</span>
    <span class="score">{{ item.importance }}/100</span>
    <div class="title"><a href="{{ item.source_url }}">{{ item.title or '(no title)' }}</a></div>
    <div class="meta">{{ item.source }} · {{ item.author or '' }} · {{ item.published_at[:10] if item.published_at else '' }}</div>
</div>
{% endfor %}

{% if topics %}
<h2>Topics This Week</h2>
{% for topic in topics %}
<div class="topic-card">
    <span class="topic-name">{{ topic.name }}</span>
    <span class="trend trend-{{ topic.trend }}">{{ topic.trend }}</span>
    <div class="summary">{{ topic.summary }}</div>
    <div class="count">{{ topic.item_count }} related items</div>
</div>
{% endfor %}
{% endif %}

<h2>By Person</h2>
{% for person_name, person_items in persons.items() %}
<div class="person-section">
    <div class="person-name">{{ person_name }} ({{ person_items|length }})</div>
    {% for item in person_items[:3] %}
    <div class="person-item">
        <a href="{{ item.source_url }}">{{ item.title or '(no title)' }}</a>
    </div>
    {% endfor %}
    {% if person_items|length > 3 %}
    <div class="person-item" style="color: #999;">+{{ person_items|length - 3 }} more</div>
    {% endif %}
</div>
{% endfor %}

<div class="footer">
    Information Union · AI Intelligence System · {{ generated_at }}
</div>

</div>
</body></html>"""


async def send_report(conn: sqlite3.Connection, config: AppConfig) -> None:
    """Send the latest report via email."""
    if not config.email.enabled:
        logger.info("Email is disabled in config.")
        return

    # Get this week's data
    today = datetime.utcnow()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    start_str = week_start.strftime("%Y-%m-%d")
    end_str = week_end.strftime("%Y-%m-%dT23:59:59")

    items = get_items_by_date(conn, start_str, end_str)
    if not items:
        logger.info("No items to report.")
        return

    # Get top items by importance
    top_items = get_top_items(conn, limit=10, week_start=start_str)

    # Get topics
    topics = get_topics(conn, week_start=start_str)

    # Get week summary from latest report
    report = get_latest_report(conn)
    week_summary = report.get("summary", "") if report else ""

    # Count unique sources
    sources = set(item.get("source", "") for item in items)

    # Group items by person
    persons_map = {p["id"]: p["name"] for p in get_active_persons(conn)}
    by_person: dict[str, list] = {}

    for item in items:
        pid = item.get("person_id")
        if pid and pid in persons_map:
            by_person.setdefault(persons_map[pid], []).append(item)

    # Render email
    html = Template(EMAIL_TEMPLATE).render(
        week_start=start_str,
        week_end=week_end.strftime("%Y-%m-%d"),
        total=len(items),
        source_count=len(sources),
        top_items=top_items,
        topics=topics,
        week_summary=week_summary,
        persons=by_person,
        generated_at=datetime.utcnow().isoformat(),
    )

    # Send
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"AI Intelligence Report — {start_str}"
    msg["From"] = config.email.from_addr
    msg["To"] = ", ".join(config.email.to_addrs)
    msg.attach(MIMEText(html, "html"))

    try:
        if config.email.smtp_port == 465:
            with smtplib.SMTP_SSL(config.email.smtp_host, config.email.smtp_port) as server:
                server.login(config.email.smtp_user, config.email.smtp_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(config.email.smtp_host, config.email.smtp_port) as server:
                server.starttls()
                server.login(config.email.smtp_user, config.email.smtp_password)
                server.send_message(msg)
        logger.info(f"Email sent to {config.email.to_addrs}")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        raise
