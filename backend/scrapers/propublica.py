"""
ProPublica Nonprofit Explorer API Client.

Free API — no authentication required.
Used to enrich leads with financial data from Form 990 filings.
"""
import httpx
from backend.scrapers.base import BaseScraper, RawLead
from backend.config.settings import settings
import logging

logger = logging.getLogger(__name__)


class ProPublicaScraper(BaseScraper):
    """
    ProPublica is used primarily for ENRICHMENT, not discovery.
    Given an org name from another source, look up their 990 data.
    """

    def __init__(self):
        super().__init__(name="ProPublica Nonprofit Explorer", source_type="propublica")
        self.base_url = settings.propublica_base_url

    async def scrape(self) -> list[RawLead]:
        """
        ProPublica isn't a discovery source — it's called on-demand
        to enrich leads found by other scrapers.
        Returns empty list; use enrich_org() instead.
        """
        return []

    async def search_org(self, query: str) -> list[dict]:
        """Search for an organization by name."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self.base_url}/search.json",
                params={"q": query},
            )
            response.raise_for_status()
            data = response.json()
            return data.get("organizations", [])

    async def get_org_by_ein(self, ein: str) -> dict | None:
        """Fetch detailed org data by EIN."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/organizations/{ein}.json"
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return None
                raise

    async def enrich_org(self, org_name: str) -> dict | None:
        """
        Given an org name, search ProPublica and return enrichment data.
        Returns a dict with financial info, or None if not found.
        """
        try:
            results = await self.search_org(org_name)
            if not results:
                return None

            # Take the best match (first result)
            org = results[0]
            ein = str(org.get("ein", ""))
            if not ein:
                return None

            # Fetch full details
            detail = await self.get_org_by_ein(ein)
            if not detail:
                return None

            org_data = detail.get("organization", {})
            filings = detail.get("filings_with_data", [])

            # Extract key financial data from most recent filing
            latest_filing = filings[0] if filings else {}

            return {
                "ein": ein,
                "name": org_data.get("name", ""),
                "city": org_data.get("city", ""),
                "state": org_data.get("state", ""),
                "ntee_code": org_data.get("ntee_code", ""),
                "subsection_code": org_data.get("subsection_code", ""),
                "total_revenue": latest_filing.get("totrevenue"),
                "total_expenses": latest_filing.get("totfuncexpns"),
                "total_assets": latest_filing.get("totassetsend"),
                "tax_year": latest_filing.get("tax_prd_yr"),
                "num_filings": len(filings),
            }

        except Exception as e:
            logger.error(f"ProPublica enrichment error for '{org_name}': {e}")
            return None


if __name__ == "__main__":
    import asyncio

    async def main():
        pp = ProPublicaScraper()
        # Test with a well-known nonprofit
        result = await pp.enrich_org("American Red Cross")
        if result:
            print(f"\nOrg: {result['name']}")
            print(f"EIN: {result['ein']}")
            print(f"Location: {result['city']}, {result['state']}")
            print(f"Revenue: ${result['total_revenue']:,.0f}" if result['total_revenue'] else "Revenue: N/A")
            print(f"Tax Year: {result['tax_year']}")
        else:
            print("Not found")

    asyncio.run(main())
