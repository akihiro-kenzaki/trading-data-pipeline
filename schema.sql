CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE symbols (
    id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code     TEXT NOT NULL UNIQUE,
    name     TEXT,
    market   TEXT NOT NULL,              -- listing market (TSE); NOT the execution venue
    currency TEXT NOT NULL DEFAULT 'JPY'
);

CREATE TABLE bars (
    symbol_id BIGINT NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    ts        TIMESTAMPTZ NOT NULL,
    timeframe TEXT NOT NULL,
    open      NUMERIC(15, 4) NOT NULL,
    high      NUMERIC(15, 4) NOT NULL,
    low       NUMERIC(15, 4) NOT NULL,
    close     NUMERIC(15, 4) NOT NULL,
    volume    NUMERIC NOT NULL,
    UNIQUE (symbol_id, ts, timeframe)
);

-- chunk_time_interval: 30 days is deliberate for this workload (hourly bars,
-- a small symbol set -> low volume per week). 7-day chunks would create many tiny
-- chunks; monthly keeps chunk count low. Revisit if data volume grows a lot.
SELECT create_hypertable(
    'bars',
    'ts',
    chunk_time_interval => INTERVAL '30 days',
    if_not_exists => TRUE
);

CREATE INDEX bars_ts_idx ON bars (ts DESC);

-- bars_daily continuous aggregate (1h -> 1d): NOT YET CREATED.
-- plot_trades.py / the Streamlit app compute daily bars on-the-fly via
-- time_bucket. Add the materialized continuous aggregate here if/when built.

CREATE TABLE trades (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    symbol_id  BIGINT NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    ts         TIMESTAMPTZ NOT NULL,
    side       TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    qty        NUMERIC NOT NULL,
    price      NUMERIC(15, 4) NOT NULL,
    fees       NUMERIC(15, 4) NOT NULL DEFAULT 0,
    -- Broker order reference normalized to int: no '#' prefix, no leading zeros.
    source_ref BIGINT NOT NULL UNIQUE,
    raw_fills  TEXT                     -- CSV multi-fill string
);