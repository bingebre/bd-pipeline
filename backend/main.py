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
from sqlalchemy import select, text, cast, String
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


# Hardcoded RSS feed URLs as fallback (in case source_configs query fails)
FALLBACK_RSS_FEEDS = [
    "https://philanthropynewsdigest.org/rfps/feed",
    "https://www.rfpmart.com/it-services-computer-maintenance-and-technical-services-rfp-bids.xml",
    "https://www.rfpmart.com/professional-consulting-administrative-or-management-support-services-rfp-bids.xml",
    "https://www.rfpmart.com/data-entry-scanning-records-and-document-related-services-rfp-bids.xml",
    "https://nonprofitquarterly.org/feed",
    "https://blog.techsoup.org/posts/rss.xml",
    "https://nptechforgood.com/feed",
]


# ──────────────────────────────────────────────
# Core scrape pipeline
# ──────────────────────────────────────────────

async def run_scrape_cycle(session: AsyncSession) -> dict:
    """
    Execute a full scrape → filter → qualify cycle.
    """
    results = {"scrapers": {}, "total_found": 0, "total_new": 0, "total_qualified": 0}

    # Load RSS feed URLs from source_configs table
    # Use raw SQL to avoid any enum casting issues
    try:
        rss_result = await session.execute(
            text("""
                SELECT url FROM source_configs 
                WHERE is_active = true 
                AND source_type IN ('rss_rfp', 'rss_news')
            """)
        )
        feed_urls = [row[0] for row in rss_result.fetchall()]
        logger.info(f"Loaded {len(feed_urls)} RSS feed URLs from source_configs")
    except Exception as e:
        logger.warning(f"Failed to load source_configs, using fallback feeds: {e}")
        feed_urls = FALLBACK_RSS_FEEDS

    # If no feeds from DB, use fallback
    if not feed_urls:
        logger.info("No feeds in source_configs, using fallback RSS feeds")
        feed_urls = FALLBACK_RSS_FEEDS

    for url in feed_urls:
        logger.info(f"  Feed: {url}")

    scrapers = [
        RSSFeedScraper(feed_urls=feed_urls),
        GrantsGovScraper(),
    ]
    qualifier = LeadQualifier()
    propublica = ProPublicaScraper()

    for scraper in scrapers:
        # Create ScrapeRun record using raw SQL to avoid enum issues
        await session.execute(
            text("""
                INSERT INTO scrape_runs (source_type, source_name, status)
                VALUES (:source_type, :source_name, 'running')
            """),
            {"source_type": scraper.source_type, "source_name": scraper.name}
        )
        await session.flush()

        # Get the run ID
        run_id_result = await session.execute(
            text("SELECT id FROM scrape_runs ORDER BY id DESC LIMIT 1")
        )
        run_id = run_id_result.scalar()

        try:
            # Step 1: Scrape
            raw_leads = await scraper.scrape()
            items_found = len(raw_leads)
            results["total_found"] += items_found
            logger.info(f"[{scraper.name}] Found {items_found} raw items")

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

            logger.info(f"[{scraper.name}] {len(new_leads)} are new (not in DB)")

            # Step 4: Qualify with LLM (if API key is configured)
            qualified_count = 0
            skipped_gov = 0
            skipped_low = 0
            skipped_fail = 0
            if settings.anthropic_api_key and new_leads:
                for lead in new_leads:
                    try:
                        qualification = await qualifier.qualify_lead(lead)
                    except Exception as e:
                        logger.error(f"LLM qualification failed for '{lead.title}': {e}")
                        qualification = None

                    if not qualification:
                        skipped_fail += 1
                        logger.info(f"  SKIP (no qualification): {lead.title}")
                        continue

                    # Skip government entities
                    if qualification.get("is_government", False):
                        skipped_gov += 1
                        logger.info(f"  SKIP (government): {lead.title}")
                        continue

                    # Skip low-confidence leads
                    confidence = qualification.get("confidence_score", 0)
                    if confidence is None:
                        confidence = 0
                    confidence = float(confidence)
                    if confidence < 0.1:
                        skipped_low += 1
                        logger.info(f"  SKIP (low confidence {confidence}): {lead.title}")
                        continue

                    logger.info(f"  QUALIFIED ({confidence}): {lead.title}")

                    # Attempt ProPublica enrichment
                    enrichment = None
                    org_name = qualification.get("org_name") or lead.org_name
                    if org_name:
                        try:
                            enrichment = await propublica.enrich_org(org_name)
                        except Exception as e:
                            logger.warning(f"ProPublica enrichment failed for '{org_name}': {e}")

                    # Store the lead using raw SQL to avoid enum issues
                    try:
                        import json as json_mod
                        await session.execute(
                            text("""
                                INSERT INTO leads (
                                    org_name, org_type, org_url, title, summary, raw_text,
                                    source_url, source_type, source_name, confidence_score,
                                    relevance_reasoning, service_matches, intent_signals,
                                    is_government, content_hash, scrape_run_id,
                                    org_ein, org_revenue, org_assets, org_city, org_state
                                ) VALUES (
                                    :org_name, :org_type, :org_url, :title, :summary, :raw_text,
                                    :source_url, :source_type, :source_name, :confidence_score,
                                    :relevance_reasoning, :service_matches::jsonb, :intent_signals::jsonb,
                                    :is_government, :content_hash, :scrape_run_id,
                                    :org_ein, :org_revenue, :org_assets, :org_city, :org_state
                                )
                            """),
                            {
                                "org_name": qualification.get("org_name", lead.org_name or "Unknown"),
                                "org_type": qualification.get("org_type"),
                                "org_url": lead.org_url,
                                "title": lead.title,
                                "summary": qualification.get("summary"),
                                "raw_text": lead.raw_text[:5000] if lead.raw_text else None,
                                "source_url": lead.source_url,
                                "source_type": lead.source_type,
                                "source_name": lead.source_name,
                                "confidence_score": confidence,
                                "relevance_reasoning": qualification.get("relevance_reasoning"),
                                "service_matches": json_mod.dumps(qualification.get("service_matches", [])),
                                "intent_signals": json_mod.dumps(qualification.get("intent_signals", [])),
                                "is_government": qualification.get("is_government", False),
                                "content_hash": lead.content_hash,
                                "scrape_run_id": run_id,
                                "org_ein": enrichment.get("ein") if enrichment else None,
                                "org_revenue": enrichment.get("revenue") if enrichment else None,
                                "org_assets": enrichment.get("assets") if enrichment else None,
                                "org_city": enrichment.get("city") if enrichment else None,
                                "org_state": enrichment.get("state") if enrichment else None,
                            }
                        )
                        qualified_count += 1
                        logger.info(f"  SAVED to DB: {lead.title}")
                    except Exception as e:
                        logger.error(f"  DB INSERT FAILED for '{lead.title}': {e}")
                        await session.rollback()
                        # Re-create the scrape run context after rollback
                        await session.execute(
                            text("SELECT 1")  # Reset transaction state
                        )
            else:
                # No API key — store all new leads without qualification
                logger.info("No API key — storing all leads without LLM qualification")
                for lead in new_leads:
                    await session.execute(
                        text("""
                            INSERT INTO leads (
                                org_name, title, raw_text, source_url, source_type,
                                source_name, content_hash, scrape_run_id
                            ) VALUES (
                                :org_name, :title, :raw_text, :source_url, :source_type,
                                :source_name, :content_hash, :scrape_run_id
                            )
                        """),
                        {
                            "org_name": lead.org_name or "Unknown",
                            "title": lead.title,
                            "raw_text": lead.raw_text[:5000] if lead.raw_text else None,
                            "source_url": lead.source_url,
                            "source_type": lead.source_type,
                            "source_name": lead.source_name,
                            "content_hash": lead.content_hash,
                            "scrape_run_id": run_id,
                        }
                    )
                    qualified_count += 1

            logger.info(f"[{scraper.name}] Summary: {qualified_count} qualified, {skipped_gov if 'skipped_gov' in dir() else '?'} gov, {skipped_low if 'skipped_low' in dir() else '?'} low-conf, {skipped_fail if 'skipped_fail' in dir() else '?'} failed")

            # Update the scrape run
            await session.execute(
                text("""
                    UPDATE scrape_runs 
                    SET items_found = :found, items_new = :new, items_qualified = :qualified,
                        status = 'completed', completed_at = NOW()
                    WHERE id = :id
                """),
                {"found": items_found, "new": len(new_leads), "qualified": qualified_count, "id": run_id}
            )
            results["total_qualified"] += qualified_count
            results["total_new"] += len(new_leads)
            results["scrapers"][scraper.name] = {
                "found": items_found,
                "new": len(new_leads),
                "qualified": qualified_count,
            }

        except Exception as e:
            logger.error(f"[{scraper.name}] Scrape failed: {e}", exc_info=True)
            await session.execute(
                text("""
                    UPDATE scrape_runs 
                    SET status = 'failed', errors = :error, completed_at = NOW()
                    WHERE id = :id
                """),
                {"error": str(e), "id": run_id}
            )
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
