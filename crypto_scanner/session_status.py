from __future__ import annotations


def freshness_is_usable(status: str) -> bool:
    return status in {"Fresh", "Possibly Incomplete", "Stale"}


def freshness_note(status: str) -> str:
    if status == "Fresh":
        return "Fresh"
    if status == "Possibly Incomplete":
        return "Possibly incomplete latest candle; closed higher-timeframe bias still uses completed periods."
    if status == "Stale":
        return "Stale data; update CSV before client use."
    return status
