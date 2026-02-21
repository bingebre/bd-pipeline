"""
Abstract base class for all scrapers.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import hashlib


@dataclass
class RawLead:
    """Standardized lead data from any scraper."""
    title: str
    raw_text: str
    source_url: str
    source_type: str
    source_name: str
    org_name: str = ""
    org_type: str = ""
    org_url: str = ""
    published_at: Optional[datetime] = None
    extra: dict = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        """Generate a dedup hash from title + source URL."""
        key = f"{self.title.strip().lower()}|{self.source_url.strip().lower()}"
        return hashlib.sha256(key.encode()).hexdigest()


class BaseScraper(ABC):
    """Abstract interface for all data source scrapers."""

    def __init__(self, name: str, source_type: str):
        self.name = name
        self.source_type = source_type

    @abstractmethod
    async def scrape(self) -> list[RawLead]:
        """Execute the scrape and return standardized leads."""
        ...

    def pre_filter(self, lead: RawLead) -> bool:
        """
        Quick keyword-based pre-filter before LLM qualification.
        Returns True if the lead should proceed to LLM scoring.
        """
        from backend.config.settings import settings

        text = f"{lead.title} {lead.raw_text}".lower()

        # Exclude government sources
        for kw in settings.gov_exclusion_keywords:
            if kw.lower() in text:
                return False

        # Check for at least one intent signal OR sector keyword
        has_intent = any(kw.lower() in text for kw in settings.intent_keywords)
        has_sector = any(kw.lower() in text for kw in settings.sector_keywords)

        return has_intent or has_sector
