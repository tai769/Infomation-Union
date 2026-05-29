-- Signal chains: connecting multiple signals into conclusions

CREATE TABLE IF NOT EXISTS signal_chains (
    id              TEXT PRIMARY KEY,
    topic           TEXT NOT NULL,       -- e.g., "Anthropic崛起", "AI编程格局变化"
    conclusion      TEXT NOT NULL,       -- Final conclusion from combining signals
    confidence      INTEGER,             -- 0-100 overall confidence
    signal_count    INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL,
    week_start      TEXT,
    status          TEXT DEFAULT 'active' -- active/superseded/confirmed
);

CREATE TABLE IF NOT EXISTS signal_chain_items (
    chain_id        TEXT REFERENCES signal_chains(id) ON DELETE CASCADE,
    item_id         TEXT REFERENCES items(id) ON DELETE CASCADE,
    signal_role     TEXT,              -- "supporting", "contradicting", "context"
    signal_weight   INTEGER,           -- 0-100 how important this signal is
    PRIMARY KEY (chain_id, item_id)
);

CREATE TABLE IF NOT EXISTS company_tracking (
    id              TEXT PRIMARY KEY,
    company_id      TEXT REFERENCES companies(id),
    period_start    TEXT NOT NULL,
    period_end      TEXT NOT NULL,
    summary         TEXT,              -- What happened to this company this period
    key_events      TEXT,              -- JSON array of event summaries
    sentiment       TEXT,              -- positive/negative/neutral
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS company_tracking_items (
    tracking_id     TEXT REFERENCES company_tracking(id) ON DELETE CASCADE,
    item_id         TEXT REFERENCES items(id) ON DELETE CASCADE,
    PRIMARY KEY (tracking_id, item_id)
);

CREATE TABLE IF NOT EXISTS industry_heatmap (
    id              TEXT PRIMARY KEY,
    sector          TEXT NOT NULL,      -- e.g., "AI编程", "AI Agent", "AI芯片"
    heat_score      INTEGER,            -- 0-100
    trend           TEXT,               -- rising/falling/stable
    week_start      TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    key_drivers     TEXT,               -- JSON array of what's driving the heat
    companies       TEXT                -- JSON array of company_ids in this sector
);

CREATE TABLE IF NOT EXISTS person_viewpoints (
    id              TEXT PRIMARY KEY,
    person_id       TEXT NOT NULL,
    topic           TEXT NOT NULL,       -- e.g., "AI Agent", "AI安全"
    viewpoint       TEXT NOT NULL,       -- What they said/think
    sentiment       TEXT,                -- optimistic/cautious/pessimistic
    source_item_id  TEXT REFERENCES items(id),
    recorded_at     TEXT NOT NULL,
    previous_id     TEXT REFERENCES person_viewpoints(id)  -- Link to previous viewpoint on same topic
);

CREATE TABLE IF NOT EXISTS competitive_groups (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,       -- e.g., "AI编程工具", "大模型"
    description     TEXT,
    companies       TEXT                 -- JSON array of company_ids
);

CREATE INDEX IF NOT EXISTS idx_signal_chain_week ON signal_chains(week_start);
CREATE INDEX IF NOT EXISTS idx_company_track_company ON company_tracking(company_id);
CREATE INDEX IF NOT EXISTS idx_heatmap_week ON industry_heatmap(week_start);
CREATE INDEX IF NOT EXISTS idx_viewpoint_person ON person_viewpoints(person_id);
CREATE INDEX IF NOT EXISTS idx_viewpoint_topic ON person_viewpoints(topic);
