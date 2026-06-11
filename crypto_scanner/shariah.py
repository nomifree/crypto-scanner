from __future__ import annotations

from .config import BLOCK_FLAGS, REVIEW_FLAGS
from .models import CoinMarketData


REVIEW_KEYWORDS = {
    "AAVE": "BUSINESS_MODEL_FLAG",
    "COMP": "BUSINESS_MODEL_FLAG",
    "MKR": "BUSINESS_MODEL_FLAG",
    "MORPHO": "BUSINESS_MODEL_FLAG",
    "ONDO": "TOKENIZED_DEBT_FLAG",
    "MPL": "PRIVATE_CREDIT_FLAG",
}


def screen_asset(coin: CoinMarketData, category: str | None = None) -> dict[str, str]:
    flags: list[str] = []
    symbol = coin.symbol.upper()
    category_text = (category or "").lower()

    if symbol in REVIEW_KEYWORDS:
        flags.append(REVIEW_KEYWORDS[symbol])
    if any(word in category_text for word in ("lending", "yield", "rwa", "real world assets", "treasury")):
        flags.append("BUSINESS_MODEL_FLAG")

    block = [flag for flag in flags if flag in BLOCK_FLAGS]
    review = [flag for flag in flags if flag in REVIEW_FLAGS]

    if block:
        return {
            "Shariah Status": "Fail",
            "Riba Exposure Flag": ",".join(block),
            "Business Activity Flag": ",".join(review),
            "Custody/Control Flag": "",
            "Review Trigger": "Blocked by automated riba/leverage/debt screen; manual scholar review required for override.",
        }
    if review:
        return {
            "Shariah Status": "Review",
            "Riba Exposure Flag": "",
            "Business Activity Flag": ",".join(review),
            "Custody/Control Flag": "",
            "Review Trigger": "Business model/category needs Shariah review before capital deployment.",
        }
    return {
        "Shariah Status": "Pass",
        "Riba Exposure Flag": "",
        "Business Activity Flag": "",
        "Custody/Control Flag": "",
        "Review Trigger": "",
    }
