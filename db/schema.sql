-- Resale arbitrage schema

CREATE TABLE IF NOT EXISTS sources (
    id          SERIAL PRIMARY KEY,
    name        TEXT UNIQUE NOT NULL,          -- 'bdroppy', 'mercari_jp', 'ebay', 'vestiaire'
    side        TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    base_url    TEXT
);

INSERT INTO sources (name, side, base_url) VALUES
    ('bdroppy', 'buy', 'https://www.bdroppy.com'),
    ('mercari_jp', 'buy', 'https://jp.mercari.com'),
    ('ebay', 'sell', 'https://www.ebay.com'),
    ('vestiaire', 'sell', 'https://www.vestiairecollective.com')
ON CONFLICT (name) DO NOTHING;

CREATE TABLE IF NOT EXISTS listings (
    id           SERIAL PRIMARY KEY,
    source_id    INT REFERENCES sources(id),
    external_id  TEXT NOT NULL,
    title        TEXT,
    brand        TEXT,
    model        TEXT,
    condition    TEXT,
    price_amount NUMERIC(12, 2),
    currency     TEXT,
    url          TEXT,
    status       TEXT DEFAULT 'active',         -- active / sold / removed
    first_seen   TIMESTAMPTZ DEFAULT now(),
    last_seen    TIMESTAMPTZ DEFAULT now(),
    raw          JSONB,
    UNIQUE (source_id, external_id)
);

CREATE TABLE IF NOT EXISTS price_snapshots (
    id            SERIAL PRIMARY KEY,
    listing_id    INT REFERENCES listings(id),
    observed_at   TIMESTAMPTZ DEFAULT now(),
    price_amount  NUMERIC(12, 2),
    currency      TEXT,
    status        TEXT
);

CREATE TABLE IF NOT EXISTS item_matches (
    id                SERIAL PRIMARY KEY,
    brand             TEXT,
    model             TEXT,
    condition_bucket  TEXT,
    created_at        TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS item_match_members (
    match_id    INT REFERENCES item_matches(id),
    listing_id  INT REFERENCES listings(id),
    PRIMARY KEY (match_id, listing_id)
);

CREATE TABLE IF NOT EXISTS opportunities (
    id                    SERIAL PRIMARY KEY,
    match_id              INT REFERENCES item_matches(id),
    buy_listing_id        INT REFERENCES listings(id),
    suggested_buy_max     NUMERIC(12, 2),
    suggested_sell_price  NUMERIC(12, 2),
    target_sell_source    TEXT,
    estimated_profit      NUMERIC(12, 2),
    estimated_margin_pct  NUMERIC(6, 2),
    sell_through_note     TEXT,
    created_at            TIMESTAMPTZ DEFAULT now(),
    notified              BOOLEAN DEFAULT FALSE
);
