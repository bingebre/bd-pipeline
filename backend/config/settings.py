"""Application settings — loaded from environment variables."""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Supabase Postgres (use port 6543 for Transaction Mode pooling)
    database_url: str = "postgresql+asyncpg://postgres:password@db.xxx.supabase.co:6543/postgres"

    # Anthropic
    anthropic_api_key: Optional[str] = None

    # CORS — set to your Vercel frontend URL
    allowed_origins: str = "http://localhost:3000"

    # Grants.gov API
    grants_gov_base_url: str = "https://api.grants.gov/v1/api"

    # ProPublica API
    propublica_base_url: str = "https://projects.propublica.org/nonprofits/api/v2"

    # Scraper Settings
    scrape_interval_minutes: int = 360
    max_results_per_source: int = 50

    # LLM Settings
    llm_model: str = "claude-sonnet-4-5-20250929"
    llm_max_tokens: int = 1024

    # Intent signal keywords
    intent_keywords: list[str] = [
        "data silo", "fragmented system", "digital transformation",
        "knowledge management", "modernization", "interactive dashboard",
        "custom application", "custom tool", "website redesign",
        "digital strategy", "data management", "content management",
        "information architecture", "digital storytelling",
        "data visualization", "user experience", "UX",
        "technology upgrade", "system integration",
        "RFP", "RFI", "request for proposal",
    ]

    # Government exclusion keywords
    gov_exclusion_keywords: list[str] = [
        "federal agency", "government agency", "state agency",
        "city of ", "county of ", "department of ",
        "bureau of ", "office of the ",
    ]

    # Sector keywords for filtering
    sector_keywords: list[str] = [
        "nonprofit", "non-profit", "NGO", "foundation",
        "association", "advocacy", "educational",
        "professional association", "law firm", "legal",
    ]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
