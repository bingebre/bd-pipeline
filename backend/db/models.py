"""
Database models for the BD Pipeline.
"""
from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, Boolean,
    ForeignKey, JSON, Enum as SAEnum, func
)
from sqlalchemy.orm import DeclarativeBase, relationship
import enum
from datetime import datetime


class Base(DeclarativeBase):
    pass


class LeadStatus(str, enum.Enum):
    NEW = "new"
    REVIEWING = "reviewing"
    QUALIFIED = "qualified"
    DISQUALIFIED = "disqualified"
    CONTACTED = "contacted"
    ARCHIVED = "archived"


class SourceType(str, enum.Enum):
    RSS_RFP = "rss_rfp"
    RSS_NEWS = "rss_news"
    GRANTS_GOV = "grants_gov"
    PROPUBLICA = "propublica"
    WEB_SCRAPE = "web_scrape"


class ServiceMatch(str, enum.Enum):
    KNOWLEDGE_SYSTEMS = "knowledge_systems"
    DIGITAL_TOOLS = "digital_tools"
    INTERACTIVE_TOOLS = "interactive_tools"
    DIGITAL_STORYTELLING = "digital_storytelling"
    CUSTOM_APPLICATIONS = "custom_applications"


# Reference the Postgres enum types created in schema.sql by their exact names
lead_status_enum = SAEnum(
    LeadStatus,
    name="lead_status",        # Must match the CREATE TYPE name in schema.sql
    create_type=False,         # Don't try to create it — it already exists in Supabase
)

source_type_enum = SAEnum(
    SourceType,
    name="source_type",        # Must match the CREATE TYPE name in schema.sql
    create_type=False,
)


class Lead(Base):
    """A discovered BD opportunity."""
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Organization info
    org_name = Column(String(500), nullable=False)
    org_type = Column(String(100))  # NGO, association, foundation, etc.
    org_url = Column(String(1000))

    # Opportunity details
    title = Column(String(1000), nullable=False)
    summary = Column(Text)  # LLM-generated summary of the opportunity
    raw_text = Column(Text)  # Original scraped text for citation
    source_url = Column(String(2000))  # Link back to original source
    source_type = Column(source_type_enum, nullable=False)
    source_name = Column(String(200))  # e.g., "PND RFPs", "Grants.gov"

    # LLM Qualification
    confidence_score = Column(Float)  # 0.0 - 1.0
    relevance_reasoning = Column(Text)  # LLM's explanation
    service_matches = Column(JSON)  # List of matched CC services
    intent_signals = Column(JSON)  # Detected intent signals
    is_government = Column(Boolean, default=False)  # For exclusion filtering

    # Pipeline status
    status = Column(lead_status_enum, default=LeadStatus.NEW)
    notes = Column(Text)  # BD team notes

    # Deduplication
    content_hash = Column(String(64), unique=True)  # SHA-256 of key content

    # ProPublica enrichment
    org_ein = Column(String(20))
    org_revenue = Column(Integer)
    org_assets = Column(Integer)
    org_city = Column(String(100))
    org_state = Column(String(50))

    # Relationships
    scrape_run_id = Column(Integer, ForeignKey("scrape_runs.id"))
    scrape_run = relationship("ScrapeRun", back_populates="leads")


class ScrapeRun(Base):
    """Record of a scraper execution cycle."""
    __tablename__ = "scrape_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    started_at = Column(DateTime, default=func.now(), nullable=False)
    completed_at = Column(DateTime)
    source_type = Column(source_type_enum, nullable=False)
    source_name = Column(String(200))
    items_found = Column(Integer, default=0)
    items_new = Column(Integer, default=0)
    items_qualified = Column(Integer, default=0)
    errors = Column(Text)
    status = Column(String(50), default="running")  # running, completed, failed

    # Relationships
    leads = relationship("Lead", back_populates="scrape_run")


class SourceConfig(Base):
    """Configuration for each data source."""
    __tablename__ = "source_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), unique=True, nullable=False)
    source_type = Column(source_type_enum, nullable=False)
    url = Column(String(2000), nullable=False)
    is_active = Column(Boolean, default=True)
    last_scraped_at = Column(DateTime)
    scrape_frequency_minutes = Column(Integer, default=360)
    config_json = Column(JSON)  # Source-specific configuration
