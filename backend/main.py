"""
BD Pipeline — FastAPI Application Entry Point.

Initializes the database, mounts API routes, and configures
the scraper scheduler for automated opportunity discovery.
"""
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import init_db, async_session
from backend.db.models import Lead, ScrapeRun, SourceType, SourceConfig
from backend.api.routes import router
from backend.scrapers.rss_scraper import RSSFeedScraper
from backend.scrapers.grants_gov import GrantsGovScraper
from backend.scrapers.propublica import ProPublicaScraper
from backend.reasoning.qualifier import LeadQualifier
from backend.config.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Core scrape pipeline
# ──────────────────────────────────────────────

async def run_scrape_cycle(session: AsyncSession) -> dict:
    """
    Execute a full scrape → filter → qualify cycle.

    Pipeline:
    1. Run all scrapers to collect raw leads
    2. Pre-filter with keyword matching (fast, no LLM cost)
    3. Deduplicate against existing leads
    4. Qualify remaining leads with LLM
    5. Store qualified leads in database
    """
    results = {"scrapers": {}, "total_found": 0, "total_new": 0, "total_qualified": 0}

    # Initialize components — load RSS feed URLs from source_configs table
    rss_result = await session.execute(
        select(SourceConfig).where(
            SourceConfig.is_active == True,
            SourceConfig.source_type.in_([SourceType.RSS_RFP, SourceType.RSS_NEWS]),
        )
    )
    rss_configs = rss_result.scalars().all()
    feed_urls = [c.url for c in rss_configs]

    scrapers = [
        RSSFeedScraper(feed_urls=feed_urls),
        GrantsGovScraper(),
    ]
    qualifier = LeadQualifier()
    propublica = ProPublicaScraper()

    for scraper in scrapers:
        run = ScrapeRun(
            source_type=SourceType(scraper.source_type) if scraper.source_type in [e.value for e in SourceType] else SourceType.RSS_RFP,
            source_name=scraper.name,
            status="running",
        )
        session.add(run)
        await session.flush()

        try:
            # Step 1: Scrape
            raw_leads = await scraper.scrape()
            run.items_found = len(raw_leads)
            results["total_found"] += len(raw_leads)
            logger.info(f"[{scraper.name}] Found {len(raw_leads)} raw items")

            # Step 2: Pre-filter (keyword-based, free)
            filtered = [lead for lead in raw_leads if scraper.pre_filter(lead)]
            logger.info(f"[{scraper.name}] {len(filtered)} passed pre-filter")

            # Step 3: Deduplicate
            new_leads = []
            for lead in filtered:
                existing = (await session.execute(
                    select(Lead).where(Lead.content_hash == lead.content_hash)
                )).scalar_one_or_none()
                if not existing:
                    new_leads.append(lead)

            run.items_new = len(new_leads)
            results["total_new"] += len(new_leads)
            logger.info(f"[{scraper.name}] {len(new_leads)} are new (not in DB)")

            # Step 4: Qualify with LLM (if API key is configured)
            qualified_count = 0
            if settings.anthropic_api_key and new_leads:
                for lead in new_leads:
                    qualification = await qualifier.qualify_lead(lead)

                    if qualification:
                        # Skip government entities
                        if qualification.get("is_government", False):
                            logger.debug(f"Skipping government entity: {lead.title}")
                            continue

                        # Skip low-confidence leads
                        confidence = qualification.get("confidence_score", 0)
                        if confidence < 0.2:
                            continue

                        # Attempt ProPublica enrichment for the org
                        enrichment = None
                        org_name = qualification.get("org_name") or lead.org_name
                        if org_name:
                            enrichment = await propublica.enrich_org(org_name)

                        # Store the lead
                        db_lead = Lead(
                            org_name=qualification.get("org_name", lead.org_name or "Unknown"),
                            org_type=qualification.get("org_type"),
                            org_url=lead.org_url,
                            title=lead.title,
                            summary=qualification.get("summary"),
                            raw_text=lead.raw_text,
                            source_url=lead.source_url,
                            source_type=SourceType(lead.source_type) if lead.source_type in [e.value for e in SourceType] else SourceType.RSS_RFP,
                            source_name=lead.source_name,
                            confidence_score=confidence,
                            relevance_reasoning=qualification.get("relevance_reasoning"),
                            service_matches=qualification.get("service_matches", []),
                            intent_signals=qualification.get("intent_signals", []),
                            is_government=qualification.get("is_government", False),
                            content_hash=lead.content_hash,
                            scrape_run_id=run.id,
                        )
                        session.add(db_lead)
                        qualified_count += 1
            else:
                # No API key — store all new leads without qualification
                for lead in new_leads:
                    db_lead = Lead(
                        org_name=lead.org_name or "Unknown",
                        title=lead.title,
                        raw_text=lead.raw_text,
                        source_url=lead.source_url,
                        source_type=SourceType(lead.source_type) if lead.source_type in [e.value for e in SourceType] else SourceType.RSS_RFP,
                        source_name=lead.source_name,
                        content_hash=lead.content_hash,
                        scrape_run_id=run.id,
                    )
                    session.add(db_lead)
                    qualified_count += 1

            run.items_qualified = qualified_count
            run.status = "completed"
            run.completed_at = datetime.utcnow()
            results["total_qualified"] += qualified_count
            results["scrapers"][scraper.name] = {
                "found": run.items_found,
                "new": run.items_new,
                "qualified": qualified_count,
            }

        except Exception as e:
            logger.error(f"[{scraper.name}] Scrape failed: {e}")
            run.status = "failed"
            run.errors = str(e)
            run.completed_at = datetime.utcnow()
            results["scrapers"][scraper.name] = {"error": str(e)}

        await session.commit()

    return results


# ──────────────────────────────────────────────
# App lifecycle
# ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    logger.info("Initializing BD Pipeline...")
    await init_db()
    logger.info("Database initialized.")

    # Optional: schedule recurring scrapes
    # from apscheduler.schedulers.asyncio import AsyncIOScheduler
    # scheduler = AsyncIOScheduler()
    # scheduler.add_job(
    #     scheduled_scrape, "interval",
    #     minutes=settings.scrape_interval_minutes,
    # )
    # scheduler.start()
    # logger.info(f"Scheduler started (every {settings.scrape_interval_minutes} min)")

    yield

    logger.info("Shutting down BD Pipeline.")


# ──────────────────────────────────────────────
# FastAPI app
# ──────────────────────────────────────────────

app = FastAPI(
    title="Citizen Codex BD Pipeline",
    description="Automated opportunity discovery for the Services division",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allows Vercel frontend + local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.allowed_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "bd-pipeline", "version": "0.1.0"}
