-- Industry chain companies and impact analysis

CREATE TABLE IF NOT EXISTS companies (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    ticker      TEXT,           -- Stock ticker (e.g., NVDA, MSFT)
    layer       TEXT NOT NULL,  -- infrastructure/chip/cloud/model/framework/application
    sub_layer   TEXT,           -- e.g., "gpu", "memory", "datacenter" for chip layer
    country     TEXT,           -- US, CN, TW, etc.
    description TEXT,
    keywords    TEXT,           -- JSON array of related keywords
    active      INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS impact_chains (
    id              TEXT PRIMARY KEY,
    item_id         TEXT,           -- Source item that triggered this analysis
    event_summary   TEXT NOT NULL,  -- What happened
    affected_layers TEXT,           -- JSON array of affected layers
    created_at      TEXT NOT NULL,
    week_start      TEXT
);

CREATE TABLE IF NOT EXISTS impact_details (
    id              TEXT PRIMARY KEY,
    chain_id        TEXT REFERENCES impact_chains(id) ON DELETE CASCADE,
    company_id      TEXT REFERENCES companies(id),
    impact_type     TEXT NOT NULL,  -- positive/negative/neutral
    probability     INTEGER,        -- 0-100
    timeline        TEXT,           -- "immediate", "1-3 months", "3-6 months", "6-12 months"
    reasoning       TEXT,           -- Why this company is affected
    key_driver      TEXT            -- The main driver of impact
);

CREATE TABLE IF NOT EXISTS tech_breakthroughs (
    id              TEXT PRIMARY KEY,
    company_id      TEXT REFERENCES companies(id),
    title           TEXT NOT NULL,
    description     TEXT,
    source_url      TEXT,
    discovered_at   TEXT NOT NULL,
    significance    TEXT,           -- "high", "medium", "low"
    layer           TEXT
);

CREATE INDEX IF NOT EXISTS idx_companies_layer ON companies(layer);
CREATE INDEX IF NOT EXISTS idx_impact_chain_item ON impact_chains(item_id);
CREATE INDEX IF NOT EXISTS idx_impact_detail_chain ON impact_details(chain_id);
CREATE INDEX IF NOT EXISTS idx_impact_detail_company ON impact_details(company_id);
