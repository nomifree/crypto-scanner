from __future__ import annotations

from .config import SETTINGS
from .market_data import MarketInstrument


KMI30_SYMBOLS = {
    "AIRLINK",
    "ATRL",
    "CPHL",
    "CNERGY",
    "DGKC",
    "EFERT",
    "ENGROH",
    "FCCL",
    "FFC",
    "FFL",
    "GHNI",
    "GAL",
    "GLAXO",
    "HUBC",
    "LUCK",
    "MARI",
    "MEBL",
    "MLCF",
    "MTL",
    "NRL",
    "OGDC",
    "PAEL",
    "PPL",
    "PRL",
    "PSO",
    "SAZEW",
    "SSGC",
    "SEARL",
    "SNGP",
    "SYS",
}


def psx_instruments() -> list[MarketInstrument]:
    data_dir = SETTINGS.psx_data_dir
    definitions = [
        ("MEBL", "Meezan Bank", "Bank", "KMI30"),
        ("SYS", "Systems Limited", "Technology", "KMI30"),
        ("FFC", "Fauji Fertilizer", "Fertilizer", "KMI30"),
        ("MARI", "Mari Energies", "E&P", "KMI30"),
        ("OGDC", "Oil & Gas Development", "E&P", "KMI30"),
        ("PPL", "Pakistan Petroleum", "E&P", "KMI30"),
        ("LUCK", "Lucky Cement", "Cement", "KMI30"),
        ("HUBC", "Hub Power", "Power", "KMI30"),
    ]
    instruments = []
    for symbol, name, sector, universe in definitions:
        shariah = "KMI Pass" if symbol in KMI30_SYMBOLS else "Review"
        instruments.append(
            MarketInstrument(
                symbol,
                name,
                sector,
                universe,
                f"{symbol}.csv",
                data_dir,
                "PSX watchlist / swing context",
                shariah,
                "Use only after EOD data is fresh; equity suitability depends on client mandate.",
                17,
                f"{symbol}.KA",
            )
        )
    return instruments
