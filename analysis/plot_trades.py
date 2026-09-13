import os
import matplotlib

matplotlib.use("Agg")
import mplfinance as mpf
import psycopg
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Render a static candlestick PNG for one symbol, with own buy/sell
# trades overlaid as markers. Reads bars + trades from TimescaleDB.
# Data-loading functions are import-safe for reuse by the Streamlit dashboard.


# Connect to DB -> Load bars data for target code
#               -> Load trade records (buy/sell) within [start, end]
#               -> Convert trades into mplfinance markers for plotting
def load_bars(
    cur: psycopg.Cursor,
    symbol_id: int,
    start: datetime,
    end: datetime,
    timeframe: str = "1h",
) -> pd.DataFrame:
    """Load bars data for target code"""
    if timeframe == "1d":
        sql = """
            SELECT time_bucket('1 day', ts, 'Asia/Tokyo') AS ts,
                   first(open, ts)  AS open,
                   max(high)        AS high,
                   min(low)         AS low,
                   last(close, ts)  AS close,
                   sum(volume)      AS volume
            FROM bars
            WHERE symbol_id = %s AND ts >= %s AND ts <= %s AND timeframe = '1h'
            GROUP BY 1
            ORDER BY 1
        """
    else:
        sql = """
            SELECT ts, open, high, low, close, volume
            FROM bars
            WHERE symbol_id = %s AND ts >= %s AND ts <= %s AND timeframe = '1h'
            ORDER BY ts
        """
    cur.execute(sql, (symbol_id, start, end))
    rows = cur.fetchall()  # Get row data (table body)
    colnames = [desc[0] for desc in cur.description]  # Get column headers (table head)
    df = pd.DataFrame(
        rows, columns=colnames
    )  # Assemble body and headers into DataFrame

    if not df.empty:
        # bars stored as TIMESTAMPTZ (UTC internally); convert to JST for display
        df["ts"] = pd.to_datetime(df["ts"]).dt.tz_convert("Asia/Tokyo")
    df = df.set_index("ts")  # Set ts column as DataFrame row index
    df = df.rename(
        columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        }
    )  # Ensure column names are TitleCase / capitalized (required by mplfinance)
    df = df.astype(
        float
    )  # Convert OHLCV columns from Decimal to float (required by mplfinance)
    return df


def load_trades(
    cur: psycopg.Cursor, symbol_id: int, start: datetime, end: datetime
) -> pd.DataFrame:
    """Load trade records (buy/sell) within [start, end]"""
    cur.execute(
        """
        SELECT ts, side, price FROM trades
        WHERE symbol_id = %s AND ts >= %s AND ts <= %s
        ORDER BY ts
        """,
        (symbol_id, start, end),
    )

    rows_trades = cur.fetchall()
    colnames_trades = [desc[0] for desc in cur.description]
    df_trades = pd.DataFrame(rows_trades, columns=colnames_trades)
    return df_trades


def resolve_symbol(cur: psycopg.Cursor, code) -> int:
    """Fetch symbol_id for the given stock code"""
    cur.execute("SELECT id FROM symbols WHERE code = %s", (code,))
    symbol_row = cur.fetchone()
    if symbol_row is None:
        print("warning: TABLE symbols does not have this stock yet")
        raise SystemExit(1)
    return symbol_row[0]


def build_markers(df, df_trades, timeframe) -> tuple[pd.Series, pd.Series]:
    """Time Alignment & Convert Data"""
    # always aligned to bars index; stay all-NaN if there are no trades
    buy_markers = pd.Series(np.nan, index=df.index)
    sell_markers = pd.Series(np.nan, index=df.index)

    if df_trades.empty:
        return buy_markers, sell_markers

    df_trades["ts"] = pd.to_datetime(df_trades["ts"]).dt.tz_convert("Asia/Tokyo")

    # NOTE: If higher-precision bar data (e.g., 1-minute bars) becomes available, this flooring step will no longer be needed.
    freq = "D" if timeframe == "1d" else "h"
    df_trades["ts_floored"] = df_trades["ts"].dt.floor(freq)

    # Iterate through trades and map buy/sell prices to the aligned hourly index
    for trade in df_trades.itertuples():
        aligned_ts = trade.ts_floored
        if (
            aligned_ts in df.index
        ):  # a trade can fall outside the loaded bar window, or on a missing bar.skip rather than crash.
            if trade.side == "buy":
                buy_markers[aligned_ts] = float(trade.price)  # Decimal -> float
            else:
                sell_markers[aligned_ts] = float(trade.price)
    return buy_markers, sell_markers


def build_style(scheme: str):
    if scheme == "jp":
        up, down = "#e53935", "#00acc1"  # JP Convention
        buy_c, sell_c = "#2e7d32", "#8e24aa"
    else:
        up, down = "#26a69a", "#ef5350"  # US/Western Convention
        buy_c, sell_c = "#1e88e5", "#ff8f00"
    mc = mpf.make_marketcolors(
        up=up,
        down=down,
        edge="inherit",
        wick="inherit",
        volume={"up": up, "down": down},
    )
    style = mpf.make_mpf_style(
        marketcolors=mc,
        gridstyle="-",
        gridcolor="#edf0f2",
        facecolor="#ffffff",
        y_on_right=False,
        rc={
            "axes.linewidth": 0.4,
            "axes.edgecolor": "#c9ced6",
            "axes.labelsize": 10,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "font.family": "DejaVu Sans",
        },
    )
    return style, buy_c, sell_c


def main():
    # read environment Variable
    host = os.environ["POSTGRES_HOST"]
    port = os.environ["POSTGRES_PORT"]
    dbname = os.environ["POSTGRES_DB"]
    user = os.environ["POSTGRES_USER"]
    password = os.environ["POSTGRES_PASSWORD"]

    # render
    scheme = "us"
    style, buy_c, sell_c = build_style(scheme)
    # timeframe
    timeframe = "1d"

    with psycopg.connect(
        host=host, port=port, dbname=dbname, user=user, password=password
    ) as conn:
        with conn.cursor() as cur:
            # Define the stock code and time range
            code = input("please input the stock code(e.g., 7203.T): ").strip()

            end_date = datetime.now()
            start_date = end_date - timedelta(days=6 * 30)

            symbol_id = resolve_symbol(cur, code)
            df = load_bars(cur, symbol_id, start_date, end_date, timeframe)
            if df.empty:
                print(f"No bar data for {code} in this window.")
                return
            df_trades = load_trades(cur, symbol_id, start_date, end_date)
            buy_markers, sell_markers = build_markers(
                df, df_trades, timeframe
            )  # compute

        # mplfinance raises on an all-NaN addplot. A symbol may have only buys or only sells in-window, so append each series only if it has real data.
        addplots = []
        if buy_markers.notna().any():
            addplots.append(
                mpf.make_addplot(
                    buy_markers,
                    type="scatter",
                    marker="^",
                    color=buy_c,
                    markersize=50,
                    alpha=0.75,
                )
            )
        if sell_markers.notna().any():
            addplots.append(
                mpf.make_addplot(
                    sell_markers,
                    type="scatter",
                    marker="v",
                    color=sell_c,
                    markersize=50,
                    alpha=0.75,
                )
            )
        safe_code = code.replace(".", "_")
        charts_dir = "/data/charts"
        os.makedirs(charts_dir, exist_ok=True)
        mpf.plot(
            df,
            type="candle",
            volume=True,
            addplot=addplots,
            style=style,
            panel_ratios=(4, 1),
            update_width_config={
                "volume_linewidth": 0.0,
                "volume_width": 0.8,
                "candle_linewidth": 0.6,
                "candle_width": 0.55,
            },
            savefig=dict(
                fname=f"{charts_dir}/{safe_code}_trades.png",
                dpi=300,
                bbox_inches="tight",
            ),
        )


# Run the interactive CLI only when this file is executed directly.
if __name__ == "__main__":
    main()