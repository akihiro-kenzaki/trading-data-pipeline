import pandas as pd
import pytest
from analysis.plot_trades import build_markers


@pytest.fixture
def hourly_two_bar_data():
    bar_index = pd.date_range(
        "2026-01-28 09:00",
        periods=2,
        freq="h",
        tz="Asia/Tokyo",
    )
    df = pd.DataFrame(index=bar_index)
    return bar_index, df


def test_build_markers_no_trade_return_empty_marker(hourly_two_bar_data):
    bar_index, df = hourly_two_bar_data
    df_trades = pd.DataFrame(columns=["ts", "side", "price"])
    buy_markers, sell_markers = build_markers(df, df_trades, "1h")
    assert buy_markers.shape == (2,)
    assert sell_markers.shape == (2,)
    assert buy_markers.index.equals(bar_index)
    assert sell_markers.index.equals(bar_index)
    assert buy_markers.isna().all()
    assert sell_markers.isna().all()


def test_build_markers_has_trade_return_buy_marker(hourly_two_bar_data):
    bar_index, df = hourly_two_bar_data
    data = [{"ts": "2026-01-28 09:00+09:00", "side": "buy", "price": 1500}]
    df_trades = pd.DataFrame(data=data, columns=["ts", "side", "price"])

    buy_markers, sell_markers = build_markers(df, df_trades, "1h")
    assert buy_markers.loc[bar_index[0]] == data[0]["price"]
    assert buy_markers.isna().loc[bar_index[1]]
    assert sell_markers.isna().all()


def test_build_markers_has_trade_return_sell_marker(hourly_two_bar_data):
    bar_index, df = hourly_two_bar_data
    data = [{"ts": "2026-01-28 10:00+09:00", "side": "sell", "price": 1475.0}]
    df_trades = pd.DataFrame(data=data, columns=["ts", "side", "price"])

    buy_markers, sell_markers = build_markers(df, df_trades, "1h")
    assert sell_markers.loc[bar_index[1]] == data[0]["price"]
    assert sell_markers.isna().loc[bar_index[0]]
    assert buy_markers.isna().all()


def test_build_markers_aligns_trade_to_hour(hourly_two_bar_data):
    bar_index, df = hourly_two_bar_data
    data = [{"ts": "2026-01-28 09:37+09:00", "side": "buy", "price": 1501.0}]
    df_trades = pd.DataFrame(data=data, columns=["ts", "side", "price"])

    buy_markers, sell_markers = build_markers(df, df_trades, "1h")
    assert buy_markers.loc[bar_index[0]] == data[0]["price"]
    assert buy_markers.isna().loc[bar_index[1]]
    assert sell_markers.isna().all()


def test_build_markers_ignores_trade_outside_bar_range(hourly_two_bar_data):
    _, df = hourly_two_bar_data
    data = [{"ts": "2026-01-28 08:37+09:00", "side": "buy", "price": 1490.0}]
    df_trades = pd.DataFrame(data=data, columns=["ts", "side", "price"])

    buy_markers, sell_markers = build_markers(df, df_trades, "1h")
    assert buy_markers.isna().all()
    assert sell_markers.isna().all()
