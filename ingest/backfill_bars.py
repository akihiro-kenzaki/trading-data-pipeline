import os
import psycopg
import yfinance as yf

from common import upsert_bars

# Connect to DB -> Iterate the `symbols` for code
#               -> Fetch and backfill each code's historical data into `bars`


def backfill_all(conn, period="2y", on_progress=None) -> int:
    """
    Backfill 2y hourly bars for every symbol. Returns rows affected.

    Commits per symbol by design: this is a long job, and partial progress
    must survive a later failure. Callers must not assume all-or-nothing.

    on_progress: optional callable(message: str) for progress reporting.
                 CLI passes print; Streamlit passes a UI updater.
    """

    def report(msg):
        if on_progress is not None:
            on_progress(msg)

    with conn.cursor() as cur:
        # ========= iterate the `symbols` for code ========= #
        cur.execute("SELECT id, code FROM symbols")
        symbols = cur.fetchall()

        count = 0
        for symbol_id, code in symbols:
            report(f"Backfilling bars for {code} (id: {symbol_id})...")

            # ========= fetch historical data ========= #
            df = yf.download(code, period=period, interval="1h", auto_adjust=False)
            # NOTE: some tickers have limited yfinance history -
            # data-source limit, not a bug.

            if df.empty:
                report(f"Warning: no data found for {code}")
                continue

            if df.columns.nlevels > 1:
                df.columns = df.columns.droplevel(1)

            df = df.dropna()

            # ========= upsert into `bars` (shared logic) ========= #
            count += upsert_bars(cur, symbol_id, df, "1h")
            conn.commit()  # per-symbol commit: see docstring

    return count


if __name__ == "__main__":
    # read environment Variable
    host = os.environ["POSTGRES_HOST"]
    port = os.environ["POSTGRES_PORT"]
    dbname = os.environ["POSTGRES_DB"]
    user = os.environ["POSTGRES_USER"]
    password = os.environ["POSTGRES_PASSWORD"]
    with psycopg.connect(
        host=host, port=port, dbname=dbname, user=user, password=password
    ) as conn:
        n = backfill_all(conn, on_progress=print)
        print(f"inserted/updated {n} rows")
