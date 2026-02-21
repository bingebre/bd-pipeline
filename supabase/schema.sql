-- ============================================
-- Citizen Codex BD Pipeline — Supabase Schema
-- Run this in the Supabase SQL Editor
-- ============================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─── ENUMS ───
CREATE TYPE lead_status AS ENUM (
  'new', 'reviewing', 'qualified', 'disqualified', 'contacted', 'archived'
);

CREATE TYPE source_type AS ENUM (
  'rss_rfp', 'rss_news', 'grants_gov', 'propublica', 'web_scrape'
);

-- ─── SCRAPE RUNS ───
CREATE TABLE scrape_runs (
  id            BIGSERIAL PRIMARY KEY,
  started_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at  TIMESTAMPTZ,
  source_type   source_type NOT NULL,
  source_name   VARCHAR(200),
  items_found   INTEGER DEFAULT 0,
  items_new     INTEGER DEFAULT 0,
  items_qualified INTEGER DEFAULT 0,
  errors        TEXT,
  status        VARCHAR(50) DEFAULT 'running'
);

-- ─── LEADS ───
CREATE TABLE leads (
  id                BIGSERIAL PRIMARY KEY,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at        TIMESTAMPTZ DEFAULT NOW(),

  -- Organization info
  org_name          VARCHAR(500) NOT NULL,
  org_type          VARCHAR(100),
  org_url           VARCHAR(1000),

  -- Opportunity details
  title             VARCHAR(1000) NOT NULL,
  summary           TEXT,
  raw_text          TEXT,
  source_url        VARCHAR(2000),
  source_type       source_type NOT NULL,
  source_name       VARCHAR(200),

  -- LLM Qualification
  confidence_score  FLOAT,
  relevance_reasoning TEXT,
  service_matches   JSONB DEFAULT '[]',
  intent_signals    JSONB DEFAULT '[]',
  is_government     BOOLEAN DEFAULT FALSE,

  -- Pipeline status
  status            lead_status DEFAULT 'new',
  notes             TEXT,

  -- Deduplication
  content_hash      VARCHAR(64) UNIQUE,

  -- Foreign key
  scrape_run_id     BIGINT REFERENCES scrape_runs(id),

  -- ProPublica enrichment
  org_ein           VARCHAR(20),
  org_revenue       BIGINT,
  org_assets        BIGINT,
  org_city          VARCHAR(100),
  org_state         VARCHAR(50)
);

-- ─── SOURCE CONFIGS ───
CREATE TABLE source_configs (
  id                    BIGSERIAL PRIMARY KEY,
  name                  VARCHAR(200) UNIQUE NOT NULL,
  source_type           source_type NOT NULL,
  url                   VARCHAR(2000) NOT NULL,
  is_active             BOOLEAN DEFAULT TRUE,
  last_scraped_at       TIMESTAMPTZ,
  scrape_frequency_minutes INTEGER DEFAULT 360,
  config_json           JSONB
);

-- ─── INDEXES ───
CREATE INDEX idx_leads_status ON leads(status);
CREATE INDEX idx_leads_confidence ON leads(confidence_score DESC NULLS LAST);
CREATE INDEX idx_leads_created ON leads(created_at DESC);
CREATE INDEX idx_leads_source_type ON leads(source_type);
CREATE INDEX idx_leads_content_hash ON leads(content_hash);
CREATE INDEX idx_leads_is_gov ON leads(is_government);
CREATE INDEX idx_leads_org_name ON leads(org_name);
CREATE INDEX idx_scrape_runs_started ON scrape_runs(started_at DESC);

-- Full-text search index on leads
CREATE INDEX idx_leads_search ON leads
  USING GIN (to_tsvector('english', coalesce(title, '') || ' ' || coalesce(org_name, '') || ' ' || coalesce(summary, '')));

-- ─── AUTO-UPDATE updated_at ───
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER leads_updated_at
  BEFORE UPDATE ON leads
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at();

-- ─── SEED SOURCE CONFIGS ───
INSERT INTO source_configs (name, source_type, url, is_active) VALUES
  ('Philanthropy News Digest', 'rss_rfp', 'https://philanthropynewsdigest.org/rfps/feed', TRUE),
  ('RFPMart — IT Services', 'rss_rfp', 'https://www.rfpmart.com/it-services-computer-maintenance-and-technical-services-rfp-bids.xml', TRUE),
  ('RFPMart — Professional Consulting', 'rss_rfp', 'https://www.rfpmart.com/professional-consulting-administrative-or-management-support-services-rfp-bids.xml', TRUE),
  ('RFPMart — Data/Records', 'rss_rfp', 'https://www.rfpmart.com/data-entry-scanning-records-and-document-related-services-rfp-bids.xml', TRUE),
  ('Nonprofit Quarterly', 'rss_news', 'https://nonprofitquarterly.org/feed', TRUE),
  ('TechSoup', 'rss_news', 'https://blog.techsoup.org/posts/rss.xml', TRUE),
  ('NP Tech for Good', 'rss_news', 'https://nptechforgood.com/feed', TRUE),
  ('Grants.gov', 'grants_gov', 'https://api.grants.gov/v1/api/search2', TRUE);
