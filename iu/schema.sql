-- Information Union SQLite Schema

CREATE TABLE IF NOT EXISTS persons (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    twitter     TEXT,
    youtube     TEXT,
    reddit      TEXT,
    tags        TEXT DEFAULT '[]',   -- JSON array
    active      INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS products (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    company     TEXT,
    tags        TEXT DEFAULT '[]',   -- JSON array
    active      INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS items (
    id              TEXT PRIMARY KEY,
    source          TEXT NOT NULL,
    source_url      TEXT NOT NULL,
    author          TEXT,
    author_handle   TEXT,
    title           TEXT,
    content         TEXT,
    published_at    TEXT,
    collected_at    TEXT NOT NULL,
    media_urls      TEXT DEFAULT '[]',   -- JSON array
    metadata        TEXT DEFAULT '{}',   -- JSON object
    person_id       TEXT REFERENCES persons(id),
    product_id      TEXT REFERENCES products(id),
    content_hash    TEXT NOT NULL,
    UNIQUE(content_hash)
);

CREATE TABLE IF NOT EXISTS item_mentions (
    item_id     TEXT REFERENCES items(id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL,
    entity_id   TEXT NOT NULL,
    PRIMARY KEY (item_id, entity_type, entity_id)
);

CREATE TABLE IF NOT EXISTS analyses (
    id              TEXT PRIMARY KEY,
    item_id         TEXT,
    created_at      TEXT NOT NULL,
    method          TEXT NOT NULL,
    model           TEXT,
    summary         TEXT,
    positive        TEXT,
    negative        TEXT,
    probability     TEXT,   -- JSON
    cross_validation TEXT,
    raw_response    TEXT
);

CREATE TABLE IF NOT EXISTS reports (
    id              TEXT PRIMARY KEY,
    week_start      TEXT NOT NULL,
    week_end        TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    summary         TEXT,
    item_ids        TEXT DEFAULT '[]',   -- JSON array
    analysis_ids    TEXT DEFAULT '[]',   -- JSON array
    delivered_email INTEGER DEFAULT 0,
    delivered_at    TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(
    title, content, author,
    content='items', content_rowid='rowid'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS items_ai AFTER INSERT ON items BEGIN
    INSERT INTO items_fts(rowid, title, content, author)
    VALUES (new.rowid, new.title, new.content, new.author);
END;

CREATE TRIGGER IF NOT EXISTS items_ad AFTER DELETE ON items BEGIN
    INSERT INTO items_fts(items_fts, rowid, title, content, author)
    VALUES ('delete', old.rowid, old.title, old.content, old.author);
END;

CREATE TRIGGER IF NOT EXISTS items_au AFTER UPDATE ON items BEGIN
    INSERT INTO items_fts(items_fts, rowid, title, content, author)
    VALUES ('delete', old.rowid, old.title, old.content, old.author);
    INSERT INTO items_fts(rowid, title, content, author)
    VALUES (new.rowid, new.title, new.content, new.author);
END;

CREATE INDEX IF NOT EXISTS idx_items_source ON items(source);
CREATE INDEX IF NOT EXISTS idx_items_published ON items(published_at);
CREATE INDEX IF NOT EXISTS idx_items_person ON items(person_id);
CREATE INDEX IF NOT EXISTS idx_items_product ON items(product_id);
CREATE INDEX IF NOT EXISTS idx_mentions_entity ON item_mentions(entity_type, entity_id);
