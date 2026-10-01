import pandas as pd
import pytest
from analysis.plot_trades import build_markers


@pytest.fixture
def daily_two_bar_data():
    bar_index = pd.date_range(
        "2026-01-28",
        periods=2,
        freq="D",
        tz="Asia/Tokyo",
    )
    df = pd.DataFrame(index=bar_index)
    return bar_index, df


def test_build_markers_no_trade_return_empty_marker(daily_two_bar_data):
    bar_index, df = daily_two_bar_data
    df_trades = pd.DataFrame(columns=["ts", "side", "price"])
    buy_markers, sell_markers = build_markers(df, df_trades, "1d")
    assert buy_markers.shape == (2,)
    assert sell_markers.shape == (2,)
    assert buy_markers.index.equals(bar_index)
    assert sell_markers.index.equals(bar_index)
    assert buy_markers.isna().all()
    assert sell_markers.isna().all()


def test_build_markers_daily_buy(daily_two_bar_data):
    bar_index, df = daily_two_bar_data
    data = [{"ts": "2026-01-28 09:37+09:00", "side": "buy", "price": 1500.0}]
    df_trades = pd.DataFrame(data=data, columns=["ts", "side", "price"])

    buy_markers, sell_markers = build_markers(df, df_trades, "1d")
    assert buy_markers.loc[bar_index[0]] == data[0]["price"]
    assert buy_markers.isna().loc[bar_index[1]]
    assert sell_markers.isna().all()


def test_build_markers_daily_sell(daily_two_bar_data):
    bar_index, df = daily_two_bar_data
    data = [{"ts": "2026-01-28 14:00+09:00", "side": "sell", "price": 1475.0}]
    df_trades = pd.DataFrame(data=data, columns=["ts", "side", "price"])

    buy_markers, sell_markers = build_markers(df, df_trades, "1d")
    assert sell_markers.loc[bar_index[0]] == data[0]["price"]
    assert sell_markers.isna().loc[bar_index[1]]
    assert buy_markers.isna().all()


def test_build_markers_daily_ignores_outside(daily_two_bar_data):
    bar_index, df = daily_two_bar_data
    data = [{"ts": "2026-01-27 23:59+09:00", "side": "buy", "price": 1490.0}]
    df_trades = pd.DataFrame(data=data, columns=["ts", "side", "price"])

    buy_markers, sell_markers = build_markers(df, df_trades, "1d")

    assert buy_markers.isna().all()
    assert sell_markers.isna().all()
