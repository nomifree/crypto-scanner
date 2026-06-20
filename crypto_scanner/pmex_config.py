from __future__ import annotations

from .config import SETTINGS
from .market_data import MarketInstrument


def pmex_instruments() -> list[MarketInstrument]:
    data_dir = SETTINGS.pmex_data_dir
    return [
        MarketInstrument("XAUUSD", "Gold", "PMEX Metals", "PMEX Core", "XAUUSD.csv", data_dir, "Gold clients / intraday / scalpers", "Review", "Use small lot; no guaranteed outcome; futures/margin needs Shariah review.", 5),
        MarketInstrument("XAGUSD", "Silver", "PMEX Metals", "PMEX Core", "XAGUSD.csv", data_dir, "Precious metals clients", "Review", "Silver can move sharper than gold; keep risk tight.", 5),
        MarketInstrument("WTI", "Crude Oil", "PMEX Energy", "PMEX Core", "WTI.csv", data_dir, "Advanced crude clients", "Review", "Headline-sensitive; reduce size around inventories/OPEC/geopolitics.", 5),
        MarketInstrument("DXY", "Dollar Index Proxy", "Macro", "PMEX Macro Filter", "DXY.csv", data_dir, "Macro filter", "Review", "Use as context for gold/silver/currencies, not a direct call unless tradeable.", 5),
        MarketInstrument("EURUSD", "EUR/USD", "FX", "PMEX FX", "EURUSD.csv", data_dir, "FX clients", "Review", "FX/margin exposure needs separate review; use risk-defined scenarios.", 5),
        MarketInstrument("GBPUSD", "GBP/USD", "FX", "PMEX FX", "GBPUSD.csv", data_dir, "FX clients", "Review", "FX/margin exposure needs separate review; use risk-defined scenarios.", 5),
        MarketInstrument("USDJPY", "USD/JPY", "FX", "PMEX FX", "USDJPY.csv", data_dir, "FX clients", "Review", "FX/margin exposure needs separate review; use risk-defined scenarios.", 5),
    ]
