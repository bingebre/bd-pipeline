"""
Grants.gov REST API Scraper.

Uses the public search2 endpoint (no auth required).
"""
import httpx
import json
from datetime import datetime
from backend.scrapers.base import BaseScraper, RawLead
from backend.config.settings import settings
import logging

logger = logging.getLogger(__name__)

# Broader search keywords to get more results
SEARCH_QUERIES = [
    "data management",
    "digital",
    "knowledge management",
    "technology",
    "dashboard",
    "information system",
    "nonprofit",
    "storytelling",
    "visualization",
    "modernization",
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
            "oppStatuses": "posted",
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

        # Log the response structure to debug
        logger.info(f"Grants.gov response keys for '{keyword}': {list(data.keys())}, totalCount={data.get('totalCount', 'N/A')}")
        
        # The API returns results under different keys depending on version
        leads = []
        opportunities = data.get("oppHits", [])
        if not opportunities:
            opportunities = data.get("data", [])
            if isinstance(opportunities, dict):
                opportunities = opportunities.get("oppHits", [])
        if not opportunities:
            # Log first 500 chars of response to understand the format
            import json
            logger.info(f"Grants.gov full response for '{keyword}': {json.dumps(data)[:500]}")

        leads = []
        opportunities = data.get("oppHits", [])

        for opp in opportunities:
            opp_id = str(opp.get("id", ""))
            if opp_id in seen_ids:
                continue
            seen_ids.add(opp_id)

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

            published = None
            if open_date:
                for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y"):
                    try:
                        published = datetime.strptime(open_date[:10], fmt)
                        break
                    except (ValueError, IndexError):
                        continue

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
