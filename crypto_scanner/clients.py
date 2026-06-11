from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import pandas as pd

try:
    import requests
except ImportError:  # pragma: no cover - production installs requests.
    requests = None

from .config import SETTINGS
from .models import CoinMarketData, DefiLlamaContext


def cg_headers() -> dict[str, str]:
    headers = {"accept": "application/json"}
    if SETTINGS.coingecko_api_key:
        headers["x-cg-demo-api-key"] = SETTINGS.coingecko_api_key
    return headers


def safe_get_json(
    url: str,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    retries: int = 2,
    pause: float = 5,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> Any | None:
    for attempt in range(retries + 1):
        try:
            if requests is None:
                return None
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=SETTINGS.request_timeout,
            )
            if response.status_code == 429 and attempt < retries:
                sleep_fn(max(pause, 30))
                continue
            if 500 <= response.status_code < 600 and attempt < retries:
                sleep_fn(pause)
                continue
            if response.status_code != 200:
                return None
            return response.json()
        except (requests.RequestException if requests is not None else Exception, ValueError):
            if attempt >= retries:
                return None
            sleep_fn(pause)
    return None


def get_top_coins(limit: int, sleep_fn: Callable[[float], None] = time.sleep) -> list[CoinMarketData]:
    url = "https://api.coingecko.com/api/v3/coins/markets"
    coins: list[CoinMarketData] = []
    seen_ids: set[str] = set()
    page = 1
    per_page = 250

    while len(coins) < limit:
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": per_page,
            "page": page,
        }
        data = safe_get_json(url, headers=cg_headers(), params=params, sleep_fn=sleep_fn)
        if not isinstance(data, list) or not data:
            break
        for raw in data:
            if not isinstance(raw, dict):
                continue
            coin = CoinMarketData.from_coingecko(raw)
            if not coin.coin_id or coin.coin_id in seen_ids:
                continue
            seen_ids.add(coin.coin_id)
            coins.append(coin)
            if len(coins) >= limit:
                break
        if len(data) < per_page:
            break
        page += 1
        sleep_fn(1)

    if not coins:
        raise RuntimeError(f"CoinGecko top-{limit} request failed.")
    return coins[:limit]


def normalize_ohlc_frame(data: Any, columns: list[str], timestamp_unit: str = "ms") -> pd.DataFrame | None:
    if not data or isinstance(data, dict):
        return None
    try:
        df = pd.DataFrame(data, columns=columns)
        df["datetime"] = pd.to_datetime(df["timestamp"].astype(float), unit=timestamp_unit, utc=True)
        df.set_index("datetime", inplace=True)
        df = df[["open", "high", "low", "close"]].astype(float)
        df = df.dropna().sort_index()
    except (ValueError, KeyError, TypeError):
        return None
    if df.empty:
        return None
    return df


def get_binance_data(symbol: str) -> pd.DataFrame | None:
    url = "https://data-api.binance.vision/api/v3/klines"
    params = {"symbol": f"{symbol}USDT", "interval": "1d", "limit": SETTINGS.daily_limit}
    data = safe_get_json(url, params=params)
    return normalize_ohlc_frame(
        data,
        [
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "qav",
            "num_trades",
            "tbbav",
            "tbqav",
            "ignore",
        ],
    )


def get_mexc_data(symbol: str) -> pd.DataFrame | None:
    url = "https://api.mexc.com/api/v3/klines"
    params = {"symbol": f"{symbol}USDT", "interval": "1d", "limit": SETTINGS.daily_limit}
    data = safe_get_json(url, params=params)
    return normalize_ohlc_frame(
        data,
        ["timestamp", "open", "high", "low", "close", "volume", "close_time", "qav"],
    )


def get_kucoin_data(symbol: str) -> pd.DataFrame | None:
    url = "https://api.kucoin.com/api/v1/market/candles"
    params = {"symbol": f"{symbol}-USDT", "type": "1day"}
    data = safe_get_json(url, params=params)
    rows = data.get("data") if isinstance(data, dict) else None
    df = normalize_ohlc_frame(
        rows,
        ["timestamp", "open", "close", "high", "low", "volume", "turnover"],
        timestamp_unit="s",
    )
    return df.tail(SETTINGS.daily_limit) if df is not None else None


def get_okx_data(symbol: str) -> pd.DataFrame | None:
    url = "https://www.okx.com/api/v5/market/candles"
    params = {"instId": f"{symbol}-USDT", "bar": "1Dutc", "limit": str(SETTINGS.daily_limit)}
    data = safe_get_json(url, params=params)
    rows = data.get("data") if isinstance(data, dict) else None
    return normalize_ohlc_frame(
        rows,
        [
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "volume_ccy",
            "volume_quote",
            "confirm",
        ],
    )


def get_bybit_data(symbol: str) -> pd.DataFrame | None:
    url = "https://api.bybit.com/v5/market/kline"
    params = {
        "category": "spot",
        "symbol": f"{symbol}USDT",
        "interval": "D",
        "limit": str(SETTINGS.daily_limit),
    }
    data = safe_get_json(url, params=params)
    rows = data.get("result", {}).get("list") if isinstance(data, dict) else None
    return normalize_ohlc_frame(
        rows,
        ["timestamp", "open", "high", "low", "close", "volume", "turnover"],
    )


def get_coingecko_ohlc_data(coin_id: str) -> pd.DataFrame | None:
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"
    params = {"vs_currency": "usd", "days": "180"}
    data = safe_get_json(url, headers=cg_headers(), params=params, retries=1)
    return normalize_ohlc_frame(data, ["timestamp", "open", "high", "low", "close"])


def get_waterfall_data(coin_id: str, symbol: str) -> tuple[pd.DataFrame | None, str]:
    for source_name, getter in (
        ("Binance", lambda: get_binance_data(symbol)),
        ("MEXC", lambda: get_mexc_data(symbol)),
        ("KuCoin", lambda: get_kucoin_data(symbol)),
        ("OKX", lambda: get_okx_data(symbol)),
        ("Bybit", lambda: get_bybit_data(symbol)),
        ("CoinGecko OHLC", lambda: get_coingecko_ohlc_data(coin_id)),
    ):
        df = getter()
        if df is not None and len(df) >= 30:
            return df, source_name
    return None, "Failed"


def get_defillama_context() -> DefiLlamaContext:
    context = DefiLlamaContext(data_quality="Unavailable")
    protocols = safe_get_json("https://api.llama.fi/protocols", retries=1)
    fees = safe_get_json("https://api.llama.fi/overview/fees", retries=1)
    dexs = safe_get_json("https://api.llama.fi/overview/dexs", retries=1)
    stablecoins = safe_get_json("https://stablecoins.llama.fi/stablecoincharts/all", retries=1)

    if isinstance(protocols, list):
        for protocol in protocols:
            if not isinstance(protocol, dict):
                continue
            symbol = str(protocol.get("symbol") or "").upper()
            name = str(protocol.get("name") or "").lower()
            if symbol:
                context.protocol_by_symbol[symbol] = protocol
            if name:
                context.protocol_by_symbol[name.upper()] = protocol
        context.data_quality = "Partial"

    if isinstance(fees, dict):
        for item in fees.get("protocols", []) or []:
            if isinstance(item, dict) and item.get("name"):
                context.fees_by_name[str(item["name"]).lower()] = item
        context.data_quality = "Partial"

    if isinstance(dexs, dict):
        for item in dexs.get("protocols", []) or []:
            if isinstance(item, dict) and item.get("name"):
                context.dex_by_name[str(item["name"]).lower()] = item
        context.data_quality = "Partial"

    if isinstance(stablecoins, list) and len(stablecoins) >= 31:
        recent = [float(row.get("totalCirculatingUSD", {}).get("peggedUSD", 0) or 0) for row in stablecoins[-31:]]
        if recent[-1] > recent[0] * 1.01:
            context.stablecoin_regime = "Expanding"
        elif recent[-1] < recent[0] * 0.99:
            context.stablecoin_regime = "Contracting"
        else:
            context.stablecoin_regime = "Neutral"
        context.data_quality = "Partial"

    return context
