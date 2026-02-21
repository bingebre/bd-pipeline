"""
RSS Feed Scraper — ingests RFP portals and sector news feeds.

Sources:
  - Philanthropy News Digest (Candid) RFPs
  - RFPdb feeds
  - RFPMart (IT Services, Professional Consulting, Data/Records)
  - Nonprofit Quarterly, TechSoup, NP Tech for Good (news signals)
"""
import feedparser
import httpx
from datetime import datetime
from typing import Optional
from backend.scrapers.base import BaseScraper, RawLead
from backend.config.settings import settings
import logging

logger = logging.getLogger(__name__)


class RSSFeedScraper(BaseScraper):
    """Scrapes configured RSS feeds for RFPs and sector news."""

    def __init__(self, feed_urls: list[str] | None = None):
        super().__init__(name="RSS Feeds", source_type="rss_rfp")
        self.feed_urls = feed_urls or settings.rss_feeds if hasattr(settings, 'rss_feeds') else []

    async def scrape(self) -> list[RawLead]:
        """Fetch all configured RSS feeds and extract leads."""
        all_leads = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            for feed_url in self.feed_urls:
                try:
                    leads = await self._scrape_feed(client, feed_url)
                    all_leads.extend(leads)
                    logger.info(f"Scraped {len(leads)} items from {feed_url}")
                except Exception as e:
                    logger.error(f"Error scraping {feed_url}: {e}")

        return all_leads

    async def _scrape_feed(self, client: httpx.AsyncClient, feed_url: str) -> list[RawLead]:
        """Fetch and parse a single RSS feed."""
        response = await client.get(feed_url, follow_redirects=True)
        response.raise_for_status()

        feed = feedparser.parse(response.text)
        leads = []

        source_name = self._classify_source(feed_url)
        source_type = "rss_rfp" if "rfp" in feed_url.lower() or "rfpmart" in feed_url.lower() else "rss_news"

        for entry in feed.entries[:settings.max_results_per_source]:
            # Extract content — prefer full content, fall back to summary
            raw_text = ""
            if hasattr(entry, "content") and entry.content:
                raw_text = entry.content[0].get("value", "")
            elif hasattr(entry, "summary"):
                raw_text = entry.summary or ""
            elif hasattr(entry, "description"):
                raw_text = entry.description or ""

            # Strip HTML tags for clean text
            raw_text = self._strip_html(raw_text)

            # Parse published date
            published = self._parse_date(entry)

            # Extract org name from title or content
            org_name = self._extract_org_name(entry.get("title", ""), raw_text)

            lead = RawLead(
                title=entry.get("title", "Untitled"),
                raw_text=raw_text[:5000],  # Cap at 5k chars
                source_url=entry.get("link", feed_url),
                source_type=source_type,
                source_name=source_name,
                org_name=org_name,
                published_at=published,
                extra={
                    "feed_url": feed_url,
                    "categories": [
                        tag.get("term", "") for tag in entry.get("tags", [])
                    ],
                },
            )
            leads.append(lead)

        return leads

    def _classify_source(self, url: str) -> str:
        """Map feed URL to a human-readable source name."""
        url_lower = url.lower()
        if "philanthropynewsdigest" in url_lower or "candid" in url_lower:
            return "Philanthropy News Digest"
        elif "rfpdb" in url_lower:
            return "RFPdb"
        elif "rfpmart" in url_lower:
            if "it-services" in url_lower:
                return "RFPMart — IT Services"
            elif "professional-consulting" in url_lower:
                return "RFPMart — Professional Consulting"
            elif "data-entry" in url_lower:
                return "RFPMart — Data/Records"
            return "RFPMart"
        elif "nonprofitquarterly" in url_lower:
            return "Nonprofit Quarterly"
        elif "techsoup" in url_lower:
            return "TechSoup"
        elif "nptechforgood" in url_lower:
            return "NP Tech for Good"
        return "RSS Feed"

    def _strip_html(self, text: str) -> str:
        """Remove HTML tags from text."""
        from html.parser import HTMLParser
        from io import StringIO

        class _Stripper(HTMLParser):
            def __init__(self):
                super().__init__()
                self.fed = []

            def handle_data(self, d):
                self.fed.append(d)

            def get_data(self):
                return " ".join(self.fed)

        s = _Stripper()
        s.feed(text)
        return s.get_data().strip()

    def _parse_date(self, entry) -> Optional[datetime]:
        """Parse publication date from various feed formats."""
        for attr in ("published_parsed", "updated_parsed"):
            parsed = getattr(entry, attr, None)
            if parsed:
                try:
                    from time import mktime
                    return datetime.fromtimestamp(mktime(parsed))
                except (ValueError, OverflowError):
                    pass
        return None

    def _extract_org_name(self, title: str, text: str) -> str:
        """
        Simple heuristic to extract org name from RFP title.
        LLM will refine this later.
        """
        # Common patterns: "Org Name: RFP Title" or "Org Name - RFP Title"
        for sep in [":", " - ", " — ", " | "]:
            if sep in title:
                candidate = title.split(sep)[0].strip()
                if len(candidate) > 3 and len(candidate) < 100:
                    return candidate
        return ""


# Allow standalone execution for testing
if __name__ == "__main__":
    import asyncio

    async def main():
        scraper = RSSFeedScraper()
        leads = await scraper.scrape()
        for lead in leads[:5]:
            print(f"\n{'='*60}")
            print(f"Title: {lead.title}")
            print(f"Org: {lead.org_name}")
            print(f"Source: {lead.source_name}")
            print(f"URL: {lead.source_url}")
            print(f"Text: {lead.raw_text[:200]}...")
            print(f"Hash: {lead.content_hash}")
            print(f"Pre-filter pass: {scraper.pre_filter(lead)}")

    asyncio.run(main())
