"""
Grants.gov REST API Scraper.

Uses the public search2 and fetchOpportunity endpoints (no auth required).
Filters for grants relevant to digital tools, knowledge management,
and technology modernization — excluding direct government operations.
"""
import httpx
from datetime import datetime
from backend.scrapers.base import BaseScraper, RawLead
from backend.config.settings import settings
import logging

logger = logging.getLogger(__name__)

# Search keywords aligned with CC service offerings
SEARCH_QUERIES = [
    "knowledge management system",
    "digital transformation nonprofit",
    "interactive dashboard",
    "data management tool",
    "website redesign nonprofit",
    "custom application development",
    "digital storytelling",
    "information architecture",
    "data visualization platform",
    "technology modernization",
]


class GrantsGovScraper(BaseScraper):
    """Scrapes Grants.gov for relevant funding opportunities."""

    def __init__(self):
        super().__init__(name="Grants.gov", source_type="grants_gov")
        self.base_url = settings.grants_gov_base_url

    async def scrape(self) -> list[RawLead]:
        """Search Grants.gov across multiple keyword queries."""
        all_leads = []
        seen_ids = set()

        async with httpx.AsyncClient(timeout=30.0) as client:
            for query in SEARCH_QUERIES:
                try:
                    leads = await self._search(client, query, seen_ids)
                    all_leads.extend(leads)
                    logger.info(f"Grants.gov '{query}': {len(leads)} results")
                except Exception as e:
                    logger.error(f"Grants.gov search error for '{query}': {e}")

        return all_leads

    async def _search(
        self, client: httpx.AsyncClient, keyword: str, seen_ids: set
    ) -> list[RawLead]:
        """Execute a single search query against the Grants.gov API."""
        payload = {
            "keyword": keyword,
            "oppStatuses": "posted",  # Only open opportunities
            "rows": 25,
            "sortBy": "openDate|desc",
        }

        response = await client.post(
            f"{self.base_url}/search2",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        data = response.json()

        leads = []
        opportunities = data.get("oppHits", [])

        for opp in opportunities:
            opp_id = opp.get("id", "")
            if opp_id in seen_ids:
                continue
            seen_ids.add(opp_id)

            # Build descriptive text from available fields
            title = opp.get("title", "Untitled")
            agency = opp.get("agencyCode", "")
            opp_number = opp.get("number", "")
            close_date = opp.get("closeDate", "")
            open_date = opp.get("openDate", "")
            description = opp.get("description", "")

            raw_text = (
                f"Opportunity: {title}\n"
                f"Agency: {agency}\n"
                f"Number: {opp_number}\n"
                f"Open: {open_date} | Close: {close_date}\n"
                f"Description: {description}"
            )

            # Parse dates
            published = None
            if open_date:
                try:
                    published = datetime.strptime(open_date[:10], "%m/%d/%Y")
                except (ValueError, IndexError):
                    pass

            lead = RawLead(
                title=title,
                raw_text=raw_text[:5000],
                source_url=f"https://www.grants.gov/search-results-detail/{opp_id}",
                source_type="grants_gov",
                source_name="Grants.gov",
                org_name=agency,
                published_at=published,
                extra={
                    "opportunity_id": opp_id,
                    "opportunity_number": opp_number,
                    "close_date": close_date,
                    "search_keyword": keyword,
                },
            )
            leads.append(lead)

        return leads

    async def fetch_opportunity_detail(
        self, client: httpx.AsyncClient, opp_id: str
    ) -> dict:
        """Fetch full details for a specific opportunity (for enrichment)."""
        response = await client.get(
            f"{self.base_url}/fetchOpportunity",
            params={"oppId": opp_id},
        )
        response.raise_for_status()
        return response.json()


if __name__ == "__main__":
    import asyncio

    async def main():
        scraper = GrantsGovScraper()
        leads = await scraper.scrape()
        print(f"\nTotal leads: {len(leads)}")
        for lead in leads[:5]:
            print(f"\n{'='*60}")
            print(f"Title: {lead.title}")
            print(f"Agency: {lead.org_name}")
            print(f"URL: {lead.source_url}")
            print(f"Pre-filter: {scraper.pre_filter(lead)}")

    asyncio.run(main())
