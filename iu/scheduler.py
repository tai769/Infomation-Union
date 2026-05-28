from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from iu.config import AppConfig

logger = logging.getLogger(__name__)


def run_weekly_pipeline(config: AppConfig):
    """Run the full weekly pipeline: collect → summarize → analyze → email."""
    from iu.db import get_db, init_db
    from iu.cli import _get_collector, _is_source_enabled
    from iu.analysis.summarize import summarize_youtube
    from iu.analysis.engine import run_analysis
    from iu.delivery.email_report import send_report

    logger.info(f"[Scheduler] Weekly pipeline started at {datetime.utcnow().isoformat()}")

    conn = get_db()
    init_db(conn)

    # 1. Collect
    sources = ["rss", "twitter", "youtube", "reddit", "news", "github", "trend", "newsletter", "arxiv", "producthunt", "substack"]
    for source in sources:
        if _is_source_enabled(source, config):
            try:
                collector = _get_collector(source, config, conn)
                count = asyncio.get_event_loop().run_until_complete(collector.run())
                logger.info(f"[Scheduler] {source}: {count} new items")
            except Exception as e:
                logger.warning(f"[Scheduler] {source} failed: {e}")

    # 2. Summarize YouTube
    try:
        count = asyncio.get_event_loop().run_until_complete(summarize_youtube(conn, config))
        logger.info(f"[Scheduler] Summarized {count} videos")
    except Exception as e:
        logger.warning(f"[Scheduler] Summarize failed: {e}")

    # 3. Analyze
    if config.analysis.api_key:
        try:
            asyncio.get_event_loop().run_until_complete(run_analysis(conn, config))
            logger.info("[Scheduler] Analysis complete")
        except Exception as e:
            logger.warning(f"[Scheduler] Analysis failed: {e}")

    # 4. Email
    if config.email.enabled:
        try:
            asyncio.get_event_loop().run_until_complete(send_report(conn, config))
            logger.info("[Scheduler] Email sent")
        except Exception as e:
            logger.warning(f"[Scheduler] Email failed: {e}")

    conn.close()
    logger.info("[Scheduler] Weekly pipeline completed")


def start_scheduler(config: AppConfig) -> AsyncIOScheduler:
    """Start the APScheduler with weekly pipeline job."""
    scheduler = AsyncIOScheduler()

    # Run every Monday at 8:00 AM
    scheduler.add_job(
        run_weekly_pipeline,
        trigger=CronTrigger(day_of_week="mon", hour=8, minute=0),
        args=[config],
        id="weekly_pipeline",
        name="Weekly AI Intelligence Pipeline",
        replace_existing=True,
    )

    # Also run a quick collect every day at 9:00 AM (lighter, just data collection)
    scheduler.add_job(
        _daily_collect,
        trigger=CronTrigger(hour=9, minute=0),
        args=[config],
        id="daily_collect",
        name="Daily Data Collection",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("[Scheduler] Started - Weekly pipeline: Monday 8AM, Daily collect: 9AM")
    return scheduler


def _daily_collect(config: AppConfig):
    """Lightweight daily collection (no analysis/email)."""
    from iu.db import get_db, init_db
    from iu.cli import _get_collector, _is_source_enabled

    logger.info(f"[Scheduler] Daily collect started at {datetime.utcnow().isoformat()}")

    conn = get_db()
    init_db(conn)

    sources = ["rss", "youtube", "reddit", "news", "github", "newsletter", "arxiv", "producthunt", "substack"]
    total = 0
    for source in sources:
        if _is_source_enabled(source, config):
            try:
                collector = _get_collector(source, config, conn)
                count = asyncio.get_event_loop().run_until_complete(collector.run())
                total += count
                logger.info(f"[Scheduler] {source}: {count} new items")
            except Exception as e:
                logger.warning(f"[Scheduler] {source} failed: {e}")

    conn.close()
    logger.info(f"[Scheduler] Daily collect completed: {total} new items")
