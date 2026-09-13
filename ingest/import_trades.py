import csv
import os
import psycopg
import pandas as pd
import yfinance as yf

from common import (
    resolve_or_create_symbol,
    upsert_bars,
    upsert_trade,
    normalize_order_ref,
)


def main():
    # read environment Variable
    host = os.environ["POSTGRES_HOST"]
    port = os.environ["POSTGRES_PORT"]
    dbname = os.environ["POSTGRES_DB"]
    user = os.environ["POSTGRES_USER"]
    password = os.environ["POSTGRES_PASSWORD"]
    path = os.environ["TRADE_CSV_PATH"]

    # Connect to DB -> Read and clean the CSV
    #               -> Resolve (or create + backfill bars for) the symbol
    #               -> Insert cleaned CSV data into `trades`

    with psycopg.connect(
        host=host, port=port, dbname=dbname, user=user, password=password
    ) as conn:
        with conn.cursor() as cur:
            with open(path, encoding="cp932") as f:
                reader = csv.reader(f)
                header = next(reader)
                count = 0
                for row in reader:
                    if len(row) <= 15:
                        raise ValueError(
                            f"CSV row has fewer than 16 columns: got {len(row)}"
                        )
                    # NOTE: The CSV format may change. Validate that each row conforms to the expected schema before processing.
                    # ===== clean the CSV row (source-specific parsing) =====
                    raw_ts = row[1]  # Raw string, may contain '|', kept for raw_fills
                    ts = pd.to_datetime(raw_ts.split("|")[0].strip()).tz_localize(
                        "Asia/Tokyo"
                    )  # Split by '|', take index 0, trim -> primary timestamp
                    total = 0  # Accumulator for breakdown fill quantities
                    for x in row[2].split("|"):
                        total += float(x.strip())  # After loop, total should equal qty

                    code = row[5] + ".T"  # 1234 -> 1234.T
                    name = row[6]  # used only if the symbol must be created
                    side = row[10].strip()
                    if side in ["買付", "買埋"]:
                        side = "buy"
                    elif side in ["売付", "売埋"]:
                        side = "sell"
                    else:
                        raise ValueError("Invalid side")
                    qty = float(row[13].replace(",", ""))
                    price = float(row[14].replace(",", ""))

                    # NOTE: Using float equality check (`total != qty`) is fine for integer shares (JP stocks),
                    # but could trigger precision errors if handling fractional shares in the future.
                    if total != qty:
                        raise ValueError("Breakdown total mismatch")

                    source_ref = normalize_order_ref(row[3])
                    raw_fills = raw_ts + "  ||  " + row[2]  # merge the raw ts and qty
                    fees = float(row[15].replace(",", ""))

                    # ===== resolve the symbol; if new, create it and backfill its bars =====
                    symbol_id, created = resolve_or_create_symbol(cur, code, name)
                    if created:
                        # New symbol: backfill 2 years of hourly bars.
                        df = yf.download(
                            code, period="2y", interval="1h", auto_adjust=False
                        )
                        if df.empty:
                            print(f"Warning: no data found for {code}")
                        else:
                            if df.columns.nlevels > 1:
                                df.columns = df.columns.droplevel(1)
                            df = df.dropna()
                            count += upsert_bars(cur, symbol_id, df, "1h")

                    # ===== insert the trade (shared logic; idempotent on source_ref) =====
                    count += upsert_trade(
                        cur,
                        symbol_id,
                        ts,
                        side,
                        qty,
                        price,
                        fees,
                        source_ref,
                        raw_fills,
                    )

                conn.commit()
                print(f"inserted/updated {count} rows")


if __name__ == "__main__":
    main()
