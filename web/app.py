import sys

# Add custom library paths to sys.path
sys.path.insert(0, "/app/ingest")
sys.path.insert(0, "/app/analysis")
import os
import psycopg
import streamlit as st
import mplfinance as mpf
import matplotlib.pyplot as plt
import pandas as pd
import io
import zipfile

# These imports are the risk point: they must NOT execute side effects.
from backfill_bars import backfill_all
from plot_trades import load_bars, load_trades, build_markers, build_style
from datetime import datetime, timedelta


# ==============================================================================
# Helper Functions & Cached Utilities
# ==============================================================================
@st.cache_data(show_spinner="building ZIP...")
def export_all_bars_zip(_db_kwargs, timeframe, start_date, end_date) -> bytes:
    """
    Export bar data for all traded symbols into a single ZIP archive containing per-symbol CSVs.
    Note: Cached function. Must execute `st.cache_data.clear()` after running data backfills.
    """
    buf = io.BytesIO()
    with psycopg.connect(**_db_kwargs) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT s.id, s.code
                FROM trades t JOIN symbols s ON s.id = t.symbol_id
                ORDER BY s.code
                """)
            targets = cur.fetchall()

            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for sid, scode in targets:
                    bars = load_bars(cur, sid, start_date, end_date, timeframe)
                    if bars.empty:
                        continue
                    out = bars.reset_index()
                    out = out.rename(columns={out.columns[0]: "ts"})
                    zf.writestr(
                        f"{scode}_{timeframe}_bars.csv",
                        out.to_csv(index=False).encode("utf-8-sig"),
                    )
    return buf.getvalue()


# ==============================================================================
# Database Configuration & Initialization
# ==============================================================================
host = os.environ["POSTGRES_HOST"]
port = os.environ["POSTGRES_PORT"]
dbname = os.environ["POSTGRES_DB"]
user = os.environ["POSTGRES_USER"]
password = os.environ["POSTGRES_PASSWORD"]
db_kwargs = dict(host=host, port=port, dbname=dbname, user=user, password=password)

st.title("Trading Data Pipeline")

with psycopg.connect(**db_kwargs) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT s.id, s.code, s.name
            FROM trades t JOIN symbols s ON s.id = t.symbol_id
            ORDER BY s.code
            """)
        symbols = cur.fetchall()

# ==============================================================================
# Sidebar Controls & Data Actions
# ==============================================================================
st.sidebar.header("Data Actions")

if st.sidebar.button("Update recent (5d)"):
    with st.spinner("fetching recent bars..."):
        with psycopg.connect(**db_kwargs) as conn:
            n = backfill_all(conn, period="5d")  # commits per symbol internally
    st.sidebar.success(f"{n} bar rows")
    st.cache_data.clear()

if st.sidebar.button("Full backfill (2y, slow)"):
    with st.spinner("fetching 2y history — this takes a while..."):
        with psycopg.connect(**db_kwargs) as conn:
            n = backfill_all(conn, period="2y")
    st.sidebar.success(f"{n} bar rows")
    st.cache_data.clear()

# Guard clause: stop execution early if no symbols are returned
if not symbols:
    st.warning("No trade symbols found in the database.")
    st.stop()

st.sidebar.header("Traded symbols")
labels = [f"{code}  {name}" for _, code, name in symbols]
choice = st.sidebar.radio("Select", labels)

st.write("Selected:", choice)
st.write(f"{len(symbols)} symbols with trades")

# ==============================================================================
# Chart Rendering (Candlestick & Trade Overlay)
# ==============================================================================
symbol_id = [sid for sid, code, name in symbols if f"{code}  {name}" == choice][0]
code = choice.split()[0]

end_date = datetime.now()
start_date = end_date - timedelta(days=6 * 30)
timeframe = "1d"

with psycopg.connect(**db_kwargs) as conn:
    with conn.cursor() as cur:
        df = load_bars(cur, symbol_id, start_date, end_date, timeframe)
        df_trades = load_trades(cur, symbol_id, start_date, end_date)

if df.empty:
    st.warning(f"No bar data for {code} in this window.")
else:
    buy_markers, sell_markers = build_markers(df, df_trades, timeframe)
    style, buy_c, sell_c = build_style("us")

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

    fig, axes = mpf.plot(
        df,
        type="candle",
        volume=True,
        addplot=addplots,
        style=style,
        panel_ratios=(4, 1),
        returnfig=True,
    )
    st.pyplot(fig)
    plt.close(fig)

    export_bars_df = df.reset_index()
    if export_bars_df.columns[0] != "ts":
        export_bars_df = export_bars_df.rename(
            columns={export_bars_df.columns[0]: "ts"}
        )

    st.download_button(
        f"Export {code} bars CSV",
        export_bars_df.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"{code}_{timeframe}_bars.csv",
        mime="text/csv",
        key=f"export-bars-{symbol_id}-{timeframe}",
    )

# ==============================================================================
# Data Export Section (Global Exports)
# ==============================================================================
with psycopg.connect(**db_kwargs) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT s.code, s.name, t.ts AT TIME ZONE 'Asia/Tokyo' AS ts_jst,
                   t.side, t.qty, t.price, t.fees, t.source_ref
            FROM trades t JOIN symbols s ON s.id = t.symbol_id
            ORDER BY s.code, t.ts
            """)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]

export_df = pd.DataFrame(rows, columns=cols)

st.download_button(
    "Export trades CSV",
    export_df.to_csv(index=False).encode("utf-8-sig"),
    file_name="trades.csv",
    mime="text/csv",
)

st.download_button(
    f"Export all {timeframe} bars ZIP",
    export_all_bars_zip(db_kwargs, timeframe, start_date, end_date),
    file_name=f"all_{timeframe}_bars.zip",
    mime="application/zip",
)
