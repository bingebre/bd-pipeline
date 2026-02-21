# Citizen Codex BD Pipeline

Automated opportunity discovery for the Services division. Scans RFP portals, grant databases, and sector news to identify and qualify BD leads.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     BD Pipeline — Filter 1                       │
│                     Broad Market Scan                             │
├───────────────────┬────────────────────┬─────────────────────────┤
│   VERCEL           │   RAILWAY          │   SUPABASE              │
│   Next.js Frontend │   FastAPI Backend  │   Postgres + Auth       │
│                    │                    │                         │
│   • Dashboard UI   │   • RSS Scrapers   │   • leads table         │
│   • Lead cards     │   • Grants.gov API │   • scrape_runs table   │
│   • Filters/search │   • ProPublica API │   • source_configs      │
│   • Status mgmt    │   • LLM Qualifier  │   • Row-level security  │
│   • Service charts │   • APScheduler    │   • Connection pooling  │
│                    │   • REST API       │                         │
│   Connects to →    │   Connects to →    │   ← Both connect here   │
│   Railway API      │   Supabase DB      │                         │
└───────────────────┴────────────────────┴─────────────────────────┘
```

## Repo Structure

```
bd-pipeline/
├── backend/                    # → Deploy to Railway
│   ├── main.py                 # FastAPI app
│   ├── config/settings.py      # Env config
│   ├── db/
│   │   ├── database.py         # Async Supabase Postgres connection
│   │   ├── models.py           # SQLAlchemy models
│   │   └── migrate.py          # Schema migration script
│   ├── scrapers/
│   │   ├── base.py             # Abstract scraper
│   │   ├── rss_scraper.py      # RSS feeds (PND, RFPdb, RFPMart)
│   │   ├── grants_gov.py       # Grants.gov API
│   │   └── propublica.py       # ProPublica enrichment
│   ├── reasoning/
│   │   ├── qualifier.py        # Claude lead scoring
│   │   └── prompts.py          # System prompts
│   ├── api/routes.py           # REST endpoints
│   ├── requirements.txt
│   ├── Dockerfile              # Railway deployment
│   └── railway.toml
│
├── frontend/                   # → Deploy to Vercel
│   ├── app/                    # Next.js App Router
│   │   ├── layout.jsx
│   │   ├── page.jsx            # Dashboard
│   │   └── globals.css
│   ├── components/             # React components
│   ├── lib/api.js              # Backend API client
│   ├── next.config.mjs
│   ├── package.json
│   ├── tailwind.config.js
│   └── vercel.json
│
├── supabase/                   # → Supabase project config
│   └── schema.sql              # Database schema
│
└── README.md
```

## Setup Guide

### 1. Supabase (Database)

1. Create project at [supabase.com](https://supabase.com)
2. Run `supabase/schema.sql` in the SQL Editor
3. Copy your connection string from Settings → Database → Connection string (URI)
   - Use **port 6543** (Transaction Mode) for Railway

### 2. Railway (Backend)

1. Connect your GitHub repo to [Railway](https://railway.app)
2. Set root directory to `backend/`
3. Add environment variables:
   ```
   DATABASE_URL=postgresql+asyncpg://postgres:[password]@db.[ref].supabase.co:6543/postgres
   ANTHROPIC_API_KEY=sk-ant-...
   ALLOWED_ORIGINS=https://your-app.vercel.app
   ```
4. Railway auto-detects the Dockerfile and deploys

### 3. Vercel (Frontend)

1. Connect your GitHub repo to [Vercel](https://vercel.com)
2. Set root directory to `frontend/`
3. Add environment variable:
   ```
   NEXT_PUBLIC_API_URL=https://your-backend.up.railway.app
   ```
4. Deploy

## Environment Variables

### Backend (Railway)
| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Supabase Postgres connection string (port 6543) |
| `ANTHROPIC_API_KEY` | Claude API key for lead qualification |
| `ALLOWED_ORIGINS` | Vercel frontend URL for CORS |
| `SCRAPE_INTERVAL_MINUTES` | How often to run scrapers (default: 360) |

### Frontend (Vercel)
| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Railway backend URL |
