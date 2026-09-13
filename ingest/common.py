import pandas as pd
import psycopg


def resolve_or_create_symbol(
    cur: psycopg.Cursor,
    code: str,
    name: str,
    market: str = "TSE",
    currency: str = "JPY",
) -> tuple[int, bool]:
    """
    Resolve a symbol id by code. Returns (symbol_id, created):
      - created=False if the symbol already existed,
      - created=True if a new row was inserted.
    The `created` flag lets callers decide whether to backfill bars.
    """
    cur.execute("SELECT id FROM symbols WHERE code = %s", (code,))
    symbol_row = cur.fetchone()

    if symbol_row is not None:
        return symbol_row[0], False

    print(f"warning: {code} does not have this stock yet")
    cur.execute(
        "INSERT INTO symbols (code, name, market, currency) VALUES (%s, %s, %s, %s) RETURNING id",
        (code, name, market, currency),
    )
    return cur.fetchone()[0], True


def upsert_bars(cur: psycopg.Cursor, symbol_id: int, df: pd.DataFrame, tf: str) -> int:
    """
    Receives a flattened and cleaned (dropna) yfinance DataFrame,
    batch upserts price bars into `bars` table, and returns the cumulative affected row count.
    """
    count = 0
    for bar_ts, bar_row in df.iterrows():
        cur.execute(
            """
            INSERT INTO bars (symbol_id, ts, timeframe, open, high, low, close, volume)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (symbol_id, ts, timeframe)
            DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume
            """,
            (
                symbol_id,
                bar_ts,
                tf,
                float(bar_row["Open"]),
                float(bar_row["High"]),
                float(bar_row["Low"]),
                float(bar_row["Close"]),
                int(bar_row["Volume"]),
            ),
        )
        count += cur.rowcount
    return count


def upsert_trade(
    cur: psycopg.Cursor,
    symbol_id: int,
    ts: pd.Timestamp,
    side: str,
    qty: float,
    price: float,
    fees: float,
    source_ref: int,
    raw_fills: str,
) -> int:
    """
    Inserts a trade record into `trades` table with conflict resolution (DO NOTHING) on `source_ref` for deduplication.
    Returns the affected row count.
    """
    cur.execute(
        """
        INSERT INTO trades (symbol_id, ts, side, qty, price, fees, source_ref, raw_fills)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_ref) DO NOTHING
        """,
        (symbol_id, ts, side, qty, price, fees, source_ref, raw_fills),
    )
    return cur.rowcount


def normalize_order_ref(raw) -> int:
    """
    Convert "#348" / "0348" / "348" to int 348.
    Handles int or str input safely.
    """
    if raw is None:
        raise ValueError("order_ref raw value is None")

    if isinstance(raw, int):
        return raw

    clean_str = str(raw).strip("# ")
    return int(clean_str)
