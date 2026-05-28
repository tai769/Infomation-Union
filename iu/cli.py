from __future__ import annotations

import sys
from pathlib import Path

import click

from iu.config import AppConfig, load_config, save_config, CONFIG_PATH
from iu.db import get_db, init_db, insert_person, insert_product, DB_PATH


@click.group()
def main():
    """Information Union — AI intelligence gathering & analysis."""
    pass


@main.command()
def init():
    """Initialize config.yaml and database."""
    # Create config
    if CONFIG_PATH.exists():
        click.echo(f"Config already exists at {CONFIG_PATH}")
    else:
        config = _default_config()
        save_config(config)
        click.echo(f"Created config at {CONFIG_PATH}")

    # Init database
    conn = get_db()
    init_db(conn)
    click.echo(f"Database initialized at {DB_PATH}")

    # Seed persons and products from config
    config = load_config()
    _seed_entities(conn, config)
    click.echo("Seeded persons and products.")
    conn.close()
    click.echo("Done. Edit config.yaml to add your API key and preferences.")


@main.command()
@click.option("--source", type=click.Choice(["rss", "twitter", "youtube", "reddit", "news"]),
              help="Run only this collector")
def collect(source):
    """Run data collectors."""
    import asyncio
    config = load_config()
    conn = get_db()
    init_db(conn)

    if source:
        collectors = [_get_collector(source, config, conn)]
    else:
        collectors = [
            _get_collector(s, config, conn)
            for s in ["rss", "twitter", "youtube", "reddit", "news"]
            if _is_source_enabled(s, config)
        ]

    async def run():
        total = 0
        for c in collectors:
            click.echo(f"Running {c.__class__.__name__}...")
            try:
                count = await c.run()
                click.echo(f"  -> {count} new items")
                total += count
            except Exception as e:
                click.echo(f"  -> ERROR: {e}", err=True)
        click.echo(f"\nTotal: {total} new items collected.")

    asyncio.run(run())
    conn.close()


@main.command()
@click.option("--week", is_flag=True, help="Export current week's data")
@click.option("--output", "-o", default="export.md", help="Output file")
def export(week, output):
    """Export collected data for analysis."""
    from iu.analysis.export import export_week, export_all
    conn = get_db()
    init_db(conn)

    if week:
        content = export_week(conn)
    else:
        content = export_all(conn)

    Path(output).write_text(content)
    click.echo(f"Exported to {output}")
    conn.close()


@main.command()
@click.option("--file", "-f", required=True, help="Analysis file to import")
def import_analysis(file):
    """Import analysis results from a file."""
    click.echo(f"Importing analysis from {file}...")
    # TODO: parse structured analysis and store in analyses table
    click.echo("Not yet implemented.")


@main.command()
def report():
    """Generate weekly report."""
    from iu.analysis.engine import generate_report
    import asyncio
    config = load_config()
    conn = get_db()
    init_db(conn)
    asyncio.run(generate_report(conn, config))
    conn.close()


@main.command()
def email():
    """Send latest report via email."""
    from iu.delivery.email_report import send_report
    import asyncio
    config = load_config()
    conn = get_db()
    asyncio.run(send_report(conn, config))
    conn.close()


@main.command()
@click.option("--port", default=None, type=int, help="Port to serve on")
def serve(port):
    """Start web UI."""
    import uvicorn
    config = load_config()
    p = port or config.web.port
    uvicorn.run("iu.web.app:app", host=config.web.host, port=p, reload=True)


@main.command()
def analyze():
    """Run AI analysis on collected data (requires API key)."""
    from iu.analysis.engine import run_analysis
    import asyncio
    config = load_config()

    if not config.analysis.api_key:
        click.echo("No API key configured. Set analysis.api_key in config.yaml")
        click.echo("Or use: iu export --week  to export data for manual Claude Code analysis.")
        sys.exit(1)

    conn = get_db()
    init_db(conn)
    asyncio.run(run_analysis(conn, config))
    conn.close()


@main.command()
@click.option("--limit", default=20, help="Max videos to summarize")
def summarize(limit):
    """Summarize YouTube video transcripts."""
    from iu.analysis.summarize import summarize_youtube
    import asyncio
    config = load_config()

    if not config.analysis.api_key:
        click.echo("No API key configured. Set analysis.api_key in config.yaml")
        sys.exit(1)

    conn = get_db()
    init_db(conn)
    count = asyncio.run(summarize_youtube(conn, config, limit))
    click.echo(f"Summarized {count} videos.")
    conn.close()


def _get_collector(source: str, config: AppConfig, conn):
    from iu.collectors.rss import RSSCollector
    from iu.collectors.twitter import TwitterCollector
    from iu.collectors.youtube import YouTubeCollector
    from iu.collectors.reddit import RedditCollector
    from iu.collectors.news import NewsCollector

    mapping = {
        "rss": RSSCollector,
        "twitter": TwitterCollector,
        "youtube": YouTubeCollector,
        "reddit": RedditCollector,
        "news": NewsCollector,
    }
    return mapping[source](config, conn)


def _is_source_enabled(source: str, config: AppConfig) -> bool:
    mapping = {
        "rss": config.rss.enabled,
        "twitter": config.twitter.enabled,
        "youtube": config.youtube.enabled,
        "reddit": config.reddit.enabled,
        "news": config.news.enabled,
    }
    return mapping.get(source, False)


def _seed_entities(conn, config: AppConfig) -> None:
    for p in config.persons:
        insert_person(conn, p.id, p.name, p.twitter, p.youtube_channel, p.reddit, p.tags)
    for p in config.products:
        insert_product(conn, p.id, p.name, p.company, p.tags)


def _default_config() -> AppConfig:
    from iu.config import PersonConfig, ProductConfig

    config = AppConfig()
    config.persons = [
        PersonConfig(id="karpathy", name="Andrej Karpathy", twitter="karpathy",
                     youtube_channel="UCXUPKJO5MZQN11PqgIvyuvQ",
                     tags=["ai-researcher", "tesla", "openai"]),
        PersonConfig(id="sam-altman", name="Sam Altman", twitter="sama",
                     tags=["openai", "ceo"]),
        PersonConfig(id="dario-amodei", name="Dario Amodei", twitter="DarioAmodei",
                     tags=["anthropic", "ceo", "safety"]),
        PersonConfig(id="jensen-huang", name="Jensen Huang", twitter="nvidia",
                     tags=["nvidia", "hardware", "ceo"]),
        PersonConfig(id="ilya-sutskever", name="Ilya Sutskever", twitter="ilyasut",
                     tags=["ssi", "safety", "openai"]),
        PersonConfig(id="logan-kilpatrick", name="Logan Kilpatrick", twitter="OfficialLoganK",
                     tags=["google", "ai-studio"]),
        PersonConfig(id="harrison-chase", name="Harrison Chase", twitter="hwchase17",
                     tags=["langchain", "agent"]),
        PersonConfig(id="guillermo-rauch", name="Guillermo Rauch", twitter="raaboratory",
                     tags=["vercel", "v0", "frontend"]),
        PersonConfig(id="amjad-masad", name="Amjad Masad", twitter="amasad",
                     tags=["replit", "coding-agent"]),
        PersonConfig(id="theo-browne", name="Theo Browne", twitter="t3dotgg",
                     tags=["t3", "tech-commentary"]),
        PersonConfig(id="lex-fridman", name="Lex Fridman", twitter="lexfridman",
                     youtube_channel="UCSHZKJJfhK61IS3o3Q1GhZg",
                     tags=["podcast", "interviews"]),
        PersonConfig(id="ben-thompson", name="Ben Thompson", twitter="benthompson",
                     tags=["stratechery", "analysis"]),
        PersonConfig(id="matt-wolfe", name="Matt Wolfe", twitter="maboreinw",
                     youtube_channel="UCj_bMKA2c0LoO5MILjFgL9g",
                     tags=["ai-tools", "youtube"]),
        PersonConfig(id="ai-jason", name="AI Jason", twitter="aiaboratoryJason",
                     tags=["ai-agent", "tools"]),
    ]
    config.products = [
        ProductConfig(id="claude-code", name="Claude Code", company="Anthropic",
                      tags=["coding-agent", "ide"]),
        ProductConfig(id="codex", name="Codex", company="OpenAI",
                      tags=["coding-agent"]),
        ProductConfig(id="cursor", name="Cursor", company="Anysphere",
                      tags=["ide", "coding-agent"]),
        ProductConfig(id="copilot", name="GitHub Copilot", company="Microsoft",
                      tags=["coding-agent"]),
        ProductConfig(id="langchain", name="LangChain", company="LangChain",
                      tags=["agent-framework"]),
        ProductConfig(id="crewai", name="CrewAI", company="CrewAI",
                      tags=["agent-framework"]),
        ProductConfig(id="autogen", name="AutoGen", company="Microsoft",
                      tags=["agent-framework"]),
        ProductConfig(id="chatgpt", name="ChatGPT", company="OpenAI",
                      tags=["llm", "chat"]),
        ProductConfig(id="claude", name="Claude", company="Anthropic",
                      tags=["llm", "chat"]),
        ProductConfig(id="gemini", name="Gemini", company="Google",
                      tags=["llm", "chat"]),
        ProductConfig(id="nvidia", name="NVIDIA", company="NVIDIA",
                      tags=["hardware", "gpu", "infrastructure"]),
    ]
    return config
