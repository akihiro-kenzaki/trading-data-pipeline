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

-- chunk_time_interval = 30 days: hourly bars for a small symbol set are low
-- volume, so 7-day chunks would be many tiny ones.
-- If switching to minute bars (~60x rows), revisit: likely 7 days or less.
-- Also auto-creates index bars_ts_idx ON bars (ts DESC); do NOT create it
-- manually (name collision -> error).
SELECT create_hypertable(
    'bars',
    'ts',
    chunk_time_interval => INTERVAL '30 days',
    if_not_exists => TRUE
);

-- bars_daily continuous aggregate (1h -> 1d): NOT YET CREATED.
-- plot_trades.py / the Streamlit app compute daily bars on-the-fly via
-- time_bucket. Add the materialized continuous aggregate here if/when built.

CREATE TABLE trades (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    -- RESTRICT: never silently delete trade history when a symbol is removed.
    symbol_id  BIGINT NOT NULL REFERENCES symbols(id) ON DELETE RESTRICT,
    ts         TIMESTAMPTZ NOT NULL,
    side       TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    qty        NUMERIC NOT NULL,
    price      NUMERIC(15, 4) NOT NULL,
    fees       NUMERIC(15, 4) NOT NULL DEFAULT 0,
    -- Broker order reference normalized to int: no '#' prefix, no leading zeros.
    -- Single broker assumed (UNIQUE would collide across brokers).
    source_ref BIGINT NOT NULL UNIQUE,
    raw_fills  TEXT                     -- CSV multi-fill string
);