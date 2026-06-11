import pandas as pd

from crypto_scanner.models import CoinMarketData, DefiLlamaContext, IctSignal, ScannerResult
from crypto_scanner.risk_overlay import build_clusters, evaluate_results, safe_beta, safe_corr


def make_ohlc(multiplier=1.0, periods=120):
    idx = pd.date_range("2026-01-01", periods=periods, freq="D", tz="UTC")
    close = pd.Series([(100 + i) * multiplier for i in range(periods)], index=idx)
    return pd.DataFrame(
        {
            "open": close * 0.99,
            "high": close * 1.02,
            "low": close * 0.98,
            "close": close,
        },
        index=idx,
    )


def coin(symbol, volume=200_000_000, market_cap=1_000_000_000):
    return CoinMarketData(
        coin_id=symbol.lower(),
        symbol=symbol,
        name=symbol,
        current_price=100,
        market_cap_rank=1,
        market_cap=market_cap,
        fdv=market_cap * 1.2,
        volume_24h=volume,
        circulating_supply=None,
        total_supply=None,
    )


def result(symbol, grade="A-Tier (Sniper)", ohlc=None):
    return ScannerResult(
        timestamp="2026-06-01",
        coin=coin(symbol),
        exchange="Binance",
        resolution="Monthly",
        price_usd=100,
        signal=IctSignal(True, "Bullish Liquidity Sweep", "Discount", grade),
        daily_ohlc=ohlc if ohlc is not None else make_ohlc(),
    )


def test_corr_and_beta_use_aligned_returns():
    btc = make_ohlc()["close"].pct_change().dropna()
    asset = (make_ohlc(2.0)["close"].pct_change().dropna())
    assert safe_corr(asset, btc) > 0.99
    assert safe_beta(asset, btc) is not None


def test_cluster_assignment_threshold():
    clusters = build_clusters({("AAA", "BBB"): 0.7, ("CCC", "DDD"): 0.2}, ["AAA", "BBB", "CCC", "DDD"])
    assert clusters["AAA"] == clusters["BBB"]
    assert clusters["CCC"] != clusters["DDD"]


def test_shariah_review_caps_action():
    review = result("AAVE")
    rows = evaluate_results([review], make_ohlc(), DefiLlamaContext(data_quality="Unavailable"))
    assert rows[0].fields["Shariah Status"] == "Review"
    assert rows[0].fields["Action"] == "ESCALATE_SHARIAH_REVIEW"
    assert rows[0].fields["Max Allocation %"] == 0


def test_hard_shariah_fail_blocks():
    blocked = result("ONDO")
    rows = evaluate_results([blocked], make_ohlc(), DefiLlamaContext(data_quality="Unavailable"))
    assert rows[0].fields["Shariah Status"] == "Fail"
    assert rows[0].fields["Action"] == "BLOCK"
    assert rows[0].fields["Candidate Score"] == 0


def test_c_tier_is_visible_but_position_capped():
    c_tier = result("SOL", grade="C-Tier (Ignore)")
    rows = evaluate_results([c_tier], make_ohlc(), DefiLlamaContext(data_quality="Unavailable"))
    assert rows[0].fields["Candidate Score"] <= 100
    assert rows[0].base.signal.grade == "C-Tier (Ignore)"
