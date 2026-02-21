"""
FastAPI REST API routes for the BD Pipeline dashboard.
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_
from typing import Optional
from datetime import datetime, timedelta
from backend.db.database import get_session
from backend.db.models import Lead, LeadStatus, ScrapeRun, SourceType
from pydantic import BaseModel

router = APIRouter(prefix="/api")


# ──────────────────────────────────────────────
# Pydantic schemas
# ──────────────────────────────────────────────

class LeadResponse(BaseModel):
    id: int
    created_at: datetime
    org_name: str
    org_type: Optional[str]
    title: str
    summary: Optional[str]
    source_url: Optional[str]
    source_type: str
    source_name: Optional[str]
    confidence_score: Optional[float]
    relevance_reasoning: Optional[str]
    service_matches: Optional[list]
    intent_signals: Optional[list]
    status: str
    notes: Optional[str]

    class Config:
        from_attributes = True


class LeadListResponse(BaseModel):
    leads: list[LeadResponse]
    total: int
    page: int
    page_size: int


class LeadUpdateRequest(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


class DashboardStats(BaseModel):
    total_leads: int
    new_leads: int
    qualified_leads: int
    avg_confidence: Optional[float]
    leads_this_week: int
    top_services: list[dict]
    source_breakdown: list[dict]
    recent_runs: list[dict]


class ScrapeRunResponse(BaseModel):
    id: int
    started_at: datetime
    completed_at: Optional[datetime]
    source_name: Optional[str]
    items_found: int
    items_new: int
    items_qualified: int
    status: str


# ──────────────────────────────────────────────
# Dashboard endpoints
# ──────────────────────────────────────────────

@router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(session: AsyncSession = Depends(get_session)):
    """Aggregate stats for the dashboard overview."""
    # Total leads
    total = (await session.execute(select(func.count(Lead.id)))).scalar() or 0

    # New leads
    new = (await session.execute(
        select(func.count(Lead.id)).where(Lead.status == LeadStatus.NEW)
    )).scalar() or 0

    # Qualified leads
    qualified = (await session.execute(
        select(func.count(Lead.id)).where(Lead.status == LeadStatus.QUALIFIED)
    )).scalar() or 0

    # Average confidence
    avg_conf = (await session.execute(
        select(func.avg(Lead.confidence_score)).where(Lead.confidence_score.isnot(None))
    )).scalar()

    # Leads this week
    week_ago = datetime.utcnow() - timedelta(days=7)
    this_week = (await session.execute(
        select(func.count(Lead.id)).where(Lead.created_at >= week_ago)
    )).scalar() or 0

    # Top service matches (flatten JSON arrays and count)
    all_leads = (await session.execute(
        select(Lead.service_matches).where(Lead.service_matches.isnot(None))
    )).scalars().all()

    service_counts = {}
    for matches in all_leads:
        if isinstance(matches, list):
            for svc in matches:
                service_counts[svc] = service_counts.get(svc, 0) + 1

    top_services = sorted(
        [{"service": k, "count": v} for k, v in service_counts.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:5]

    # Source breakdown
    source_rows = (await session.execute(
        select(Lead.source_name, func.count(Lead.id))
        .group_by(Lead.source_name)
        .order_by(desc(func.count(Lead.id)))
    )).all()
    source_breakdown = [{"source": r[0] or "Unknown", "count": r[1]} for r in source_rows]

    # Recent scrape runs
    runs = (await session.execute(
        select(ScrapeRun)
        .order_by(desc(ScrapeRun.started_at))
        .limit(10)
    )).scalars().all()
    recent_runs = [
        {
            "id": r.id,
            "source": r.source_name,
            "started": r.started_at.isoformat() if r.started_at else None,
            "items_found": r.items_found,
            "items_new": r.items_new,
            "status": r.status,
        }
        for r in runs
    ]

    return DashboardStats(
        total_leads=total,
        new_leads=new,
        qualified_leads=qualified,
        avg_confidence=round(avg_conf, 2) if avg_conf else None,
        leads_this_week=this_week,
        top_services=top_services,
        source_breakdown=source_breakdown,
        recent_runs=recent_runs,
    )


# ──────────────────────────────────────────────
# Lead CRUD endpoints
# ──────────────────────────────────────────────

@router.get("/leads", response_model=LeadListResponse)
async def list_leads(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    source_type: Optional[str] = None,
    min_confidence: Optional[float] = None,
    search: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    session: AsyncSession = Depends(get_session),
):
    """List leads with filtering, search, and pagination."""
    query = select(Lead)

    # Filters
    conditions = []
    if status:
        conditions.append(Lead.status == status)
    if source_type:
        conditions.append(Lead.source_type == source_type)
    if min_confidence is not None:
        conditions.append(Lead.confidence_score >= min_confidence)
    if search:
        search_term = f"%{search}%"
        conditions.append(
            Lead.title.ilike(search_term)
            | Lead.org_name.ilike(search_term)
            | Lead.summary.ilike(search_term)
        )

    # Exclude government leads by default
    conditions.append(Lead.is_government == False)

    if conditions:
        query = query.where(and_(*conditions))

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_query)).scalar() or 0

    # Sort
    sort_col = getattr(Lead, sort_by, Lead.created_at)
    query = query.order_by(desc(sort_col) if sort_order == "desc" else sort_col)

    # Paginate
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = (await session.execute(query)).scalars().all()

    return LeadListResponse(
        leads=[LeadResponse.model_validate(lead) for lead in result],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/leads/{lead_id}", response_model=LeadResponse)
async def get_lead(lead_id: int, session: AsyncSession = Depends(get_session)):
    """Get a single lead by ID."""
    lead = await session.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return LeadResponse.model_validate(lead)


@router.patch("/leads/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: int,
    update: LeadUpdateRequest,
    session: AsyncSession = Depends(get_session),
):
    """Update lead status or notes."""
    lead = await session.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if update.status is not None:
        lead.status = update.status
    if update.notes is not None:
        lead.notes = update.notes

    await session.commit()
    await session.refresh(lead)
    return LeadResponse.model_validate(lead)


# ──────────────────────────────────────────────
# Scraper control endpoints
# ──────────────────────────────────────────────

@router.post("/scrape/run")
async def trigger_scrape(session: AsyncSession = Depends(get_session)):
    """Manually trigger a full scrape cycle."""
    # Import here to avoid circular imports
    from backend.main import run_scrape_cycle
    result = await run_scrape_cycle(session)
    return {"message": "Scrape cycle completed", "results": result}


@router.get("/scrape/history", response_model=list[ScrapeRunResponse])
async def scrape_history(
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """Get scrape run history."""
    runs = (await session.execute(
        select(ScrapeRun)
        .order_by(desc(ScrapeRun.started_at))
        .limit(limit)
    )).scalars().all()
    return [ScrapeRunResponse.model_validate(r) for r in runs]
