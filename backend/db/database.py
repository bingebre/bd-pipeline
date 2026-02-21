"""
Async database connection to Supabase Postgres.
Uses NullPool since Supabase Supavisor handles connection pooling.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import text
import logging
from backend.config.settings import settings


engine = create_async_engine(
    settings.database_url,
    poolclass=NullPool,
    connect_args={
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    },
    echo=False,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """Verify database connection. Schema is managed via Supabase SQL Editor."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    logging.getLogger(__name__).info("Database connection verified.")


async def get_session() -> AsyncSession:
    """Dependency for FastAPI route injection."""
    async with async_session() as session:
        yield session
