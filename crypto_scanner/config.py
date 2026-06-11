import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    spreadsheet_id: str | None = os.getenv("SPREADSHEET_ID")
    credentials_json: str | None = os.getenv("GOOGLE_CREDENTIALS_JSON")
    coingecko_api_key: str | None = os.getenv("COINGECKO_API_KEY")
    dry_run: bool = os.getenv("DRY_RUN", "").lower() in {"1", "true", "yes"}
    request_timeout: int = int(os.getenv("REQUEST_TIMEOUT", "20"))
    daily_limit: int = int(os.getenv("DAILY_LIMIT", "240"))
    monthly_coin_limit: int = int(os.getenv("MONTHLY_COIN_LIMIT", "350"))
    weekly_coin_limit: int = int(os.getenv("WEEKLY_COIN_LIMIT", "100"))
    sleep_seconds: float = float(os.getenv("SCAN_SLEEP_SECONDS", "1"))


SETTINGS = Settings()

BASE_HEADERS = [
    "Timestamp",
    "Ticker",
    "Exchange",
    "Resolution",
    "Price USD",
    "Directional Bias",
    "Valuation",
    "Setup Grade",
]

RISK_HEADERS = BASE_HEADERS + [
    "Market Cap Rank",
    "Market Cap",
    "FDV",
    "Volume 24H",
    "Volume / Market Cap %",
    "Liquidity Score",
    "Volatility Score",
    "BTC Corr 30D",
    "BTC Corr 90D",
    "BTC Beta 90D",
    "Avg Pairwise Corr",
    "Cluster ID",
    "Cluster Density",
    "Cluster Rank",
    "DefiLlama Category",
    "TVL Score",
    "Fees/Revenue Score",
    "DEX Volume Score",
    "Stablecoin Regime",
    "On-Chain Data Quality",
    "Shariah Status",
    "Riba Exposure Flag",
    "Business Activity Flag",
    "Custody/Control Flag",
    "Correlation Risk Score",
    "Beta Risk Score",
    "Liquidity Risk Score",
    "Final Risk Score",
    "Candidate Score",
    "Action",
    "Max Allocation %",
    "Position Risk %",
    "Risk Notes",
    "Review Trigger",
]

SUMMARY_HEADERS = ["Section", "Ticker/Cluster", "Metric", "Action", "Notes"]

BLOCK_FLAGS = {
    "RIBA_FLAG",
    "LEVERAGE_FLAG",
    "PERPS_FLAG",
    "TOKENIZED_DEBT_FLAG",
    "PRIVATE_CREDIT_FLAG",
    "IB_STABLE_FLAG",
}

REVIEW_FLAGS = {
    "YIELD_FLAG",
    "BUSINESS_MODEL_FLAG",
    "CUSTODY_OPAQUE_FLAG",
    "CONTROL_RISK_FLAG",
}
