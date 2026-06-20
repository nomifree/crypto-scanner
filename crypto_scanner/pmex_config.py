from __future__ import annotations

from .config import SETTINGS
from .market_data import MarketInstrument


def pmex_instruments() -> list[MarketInstrument]:
    data_dir = SETTINGS.pmex_data_dir
    return [
        MarketInstrument("XAUUSD", "Gold", "PMEX Metals", "PMEX Core", "XAUUSD.csv", data_dir, "Gold clients / intraday / scalpers", "Review", "Yahoo proxy data; confirm exact PMEX contract terms before execution. Futures/margin needs Shariah review.", 5, "GC=F"),
        MarketInstrument("XAGUSD", "Silver", "PMEX Metals", "PMEX Core", "XAGUSD.csv", data_dir, "Precious metals clients", "Review", "Yahoo proxy data; silver can move sharper than gold; keep risk tight.", 5, "SI=F"),
        MarketInstrument("WTI", "Crude Oil", "PMEX Energy", "PMEX Core", "WTI.csv", data_dir, "Advanced crude clients", "Review", "Yahoo proxy data; headline-sensitive; reduce size around inventories/OPEC/geopolitics.", 5, "CL=F"),
        MarketInstrument("DXY", "Dollar Index Proxy", "Macro", "PMEX Macro Filter", "DXY.csv", data_dir, "Macro filter", "Review", "Yahoo proxy data; use as context for gold/silver/currencies.", 5, "DX-Y.NYB"),
        MarketInstrument("EURUSD", "EUR/USD", "FX", "PMEX FX", "EURUSD.csv", data_dir, "FX clients", "Review", "Yahoo proxy data; FX/margin exposure needs separate review; use risk-defined scenarios.", 5, "EURUSD=X"),
        MarketInstrument("GBPUSD", "GBP/USD", "FX", "PMEX FX", "GBPUSD.csv", data_dir, "FX clients", "Review", "Yahoo proxy data; FX/margin exposure needs separate review; use risk-defined scenarios.", 5, "GBPUSD=X"),
        MarketInstrument("USDJPY", "USD/JPY", "FX", "PMEX FX", "USDJPY.csv", data_dir, "FX clients", "Review", "Yahoo proxy data; FX/margin exposure needs separate review; use risk-defined scenarios.", 5, "JPY=X"),
    ]
