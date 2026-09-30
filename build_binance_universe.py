"""Build the trading universe from Binance top USDT pairs by 24h volume.

Uses data-api.binance.vision (the public Binance Vision data endpoint) because
api.binance.com geo-blocks some regions with HTTP 451. Returns the top N USDT
spot pairs by 24h USDT quote volume.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass

import requests

VISION = "https://data-api.binance.vision/api/v3"


@dataclass(frozen=True)
class BinancePair:
    symbol: str
    base: str
    quote: str
    spot: bool
    quote_volume_24h: float


def _get_exchange_info() -> list[dict]:
    url = f"{VISION}/exchangeInfo"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.json().get("symbols", [])


def _get_24h_ticker() -> dict[str, float]:
    url = f"{VISION}/ticker/24hr"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return {t["symbol"]: float(t.get("quoteVolume", 0.0) or 0.0) for t in r.json()}


def get_binance_universe(limit: int = 350) -> list[BinancePair]:
    """Return top `limit` USDT spot pairs ranked by 24h USDT volume."""
    pairs: list[BinancePair] = []
    ticker = _get_24h_ticker()
    for info in _get_exchange_info():
        if info.get("status") != "TRADING":
            continue
        if not info.get("isSpotTradingAllowed"):
            continue
        quote = info.get("quoteAsset")
        if quote != "USDT":
            continue
        symbol = info.get("symbol")
        base = info.get("baseAsset")
        if not symbol or not base:
            continue
        vol = ticker.get(symbol, 0.0)
        pairs.append(
            BinancePair(
                symbol=symbol,
                base=base,
                quote=quote,
                spot=True,
                quote_volume_24h=vol,
            )
        )
    pairs.sort(key=lambda p: p.quote_volume_24h, reverse=True)
    return pairs[:limit]


if __name__ == "__main__":
    limit = int(os.getenv("UNIVERSE_LIMIT", "350"))
    top = get_binance_universe(limit=limit)
    print(f"Top {len(top)} Binance USDT spot pairs by 24h USDT volume:")
    for i, p in enumerate(top, start=1):
        print(f"{i:>4}  {p.base:<12}  {p.symbol:<16}  vol24h={p.quote_volume_24h:>20,.0f} USDT")
