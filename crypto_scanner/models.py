from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class CoinMarketData:
    coin_id: str
    symbol: str
    name: str
    current_price: float | None
    market_cap_rank: int | None
    market_cap: float | None
    fdv: float | None
    volume_24h: float | None
    circulating_supply: float | None
    total_supply: float | None

    @classmethod
    def from_coingecko(cls, raw: dict[str, Any]) -> "CoinMarketData":
        def as_float(value: Any) -> float | None:
            try:
                return float(value) if value is not None else None
            except (TypeError, ValueError):
                return None

        def as_int(value: Any) -> int | None:
            try:
                return int(value) if value is not None else None
            except (TypeError, ValueError):
                return None

        return cls(
            coin_id=str(raw.get("id", "")),
            symbol=str(raw.get("symbol", "")).upper(),
            name=str(raw.get("name", "")),
            current_price=as_float(raw.get("current_price")),
            market_cap_rank=as_int(raw.get("market_cap_rank")),
            market_cap=as_float(raw.get("market_cap")),
            fdv=as_float(raw.get("fully_diluted_valuation")),
            volume_24h=as_float(raw.get("total_volume")),
            circulating_supply=as_float(raw.get("circulating_supply")),
            total_supply=as_float(raw.get("total_supply")),
        )


@dataclass(frozen=True)
class IctSignal:
    qualified: bool
    bias: str
    valuation: str | None
    grade: str


@dataclass
class ScannerResult:
    timestamp: str
    coin: CoinMarketData
    exchange: str
    resolution: str
    price_usd: float | None
    signal: IctSignal
    daily_ohlc: pd.DataFrame

    def base_row(self) -> list[Any]:
        return [
            self.timestamp,
            self.coin.symbol,
            self.exchange,
            self.resolution,
            self.price_usd,
            self.signal.bias,
            self.signal.valuation,
            self.signal.grade,
        ]


@dataclass
class DefiLlamaContext:
    stablecoin_regime: str = "Unknown"
    protocol_by_symbol: dict[str, dict[str, Any]] = field(default_factory=dict)
    fees_by_name: dict[str, dict[str, Any]] = field(default_factory=dict)
    dex_by_name: dict[str, dict[str, Any]] = field(default_factory=dict)
    data_quality: str = "Unavailable"


@dataclass
class RiskResult:
    base: ScannerResult
    fields: dict[str, Any]

    def risk_row(self, headers: list[str]) -> list[Any]:
        base = self.base.base_row()
        return base + [self.fields.get(header, "") for header in headers[len(base):]]
