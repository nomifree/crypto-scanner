from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import pandas as pd


STABLE_SYMBOLS = {
    "USDT",
    "USDC",
    "USDE",
    "DAI",
    "USDS",
    "BUSD",
    "FDUSD",
    "TUSD",
    "USDD",
    "PYUSD",
    "USD1",
    "FRAX",
    "LUSD",
    "GHO",
    "SUSD",
    "USDP",
}
BINANCE_URL = "https://data-api.binance.vision/api/v3/klines"
COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/markets"
START = "2017-08-17"
LIMIT = 1000
SEQUENCE_ORDER = [
    "target_only",
    "target_first",
    "opposing_first",
    "opposing_only",
    "same_4h_ambiguous",
    "neither",
]


def fetch_market_cap_candidates(limit: int = 100) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode(
        {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": limit,
            "page": 1,
            "sparkline": "false",
        }
    )
    request = urllib.request.Request(
        f"{COINGECKO_URL}?{params}",
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        data = json.loads(response.read().decode("utf-8"))

    candidates = []
    seen = set()
    for item in data:
        symbol = str(item.get("symbol") or "").upper()
        name = str(item.get("name") or "")
        lower_name = name.lower()
        if not symbol or symbol in seen or symbol in STABLE_SYMBOLS:
            continue
        if "wrapped" in lower_name or "staked" in lower_name:
            continue
        seen.add(symbol)
        candidates.append(
            {
                "symbol": symbol,
                "name": name,
                "market_cap_rank": item.get("market_cap_rank"),
                "market_cap": item.get("market_cap"),
            }
        )
    return candidates


def fetch_4h_usdt(symbol: str) -> tuple[pd.DataFrame, str | None]:
    start = int(pd.Timestamp(START, tz="UTC").timestamp() * 1000)
    end = int(pd.Timestamp.now(tz="UTC").timestamp() * 1000)
    rows = []

    while start < end:
        params = urllib.parse.urlencode(
            {
                "symbol": f"{symbol}USDT",
                "interval": "4h",
                "limit": LIMIT,
                "startTime": start,
                "endTime": end,
            }
        )
        request = urllib.request.Request(
            f"{BINANCE_URL}?{params}",
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                batch = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            return pd.DataFrame(), str(exc)

        if isinstance(batch, dict):
            return pd.DataFrame(), str(batch)
        if not batch:
            break

        rows.extend(batch)
        last_open = int(batch[-1][0])
        next_start = last_open + 4 * 60 * 60 * 1000
        if next_start <= start:
            break
        start = next_start
        time.sleep(0.03)

    if not rows:
        return pd.DataFrame(), "No Binance 4h rows"

    df = pd.DataFrame(
        rows,
        columns=[
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_volume",
            "trades",
            "tb_base",
            "tb_quote",
            "ignore",
        ],
    )
    df["datetime"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    for column in ["open", "high", "low", "close"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close"]).sort_values("datetime")

    current_week = pd.Timestamp.now(tz="UTC").tz_convert(None).to_period("W-SUN")
    df["week_period"] = df["datetime"].dt.tz_convert(None).dt.to_period("W-SUN")
    df = df[df["week_period"] < current_week].copy()
    counts = df.groupby("week_period").size()
    complete_weeks = set(counts[counts == 42].index)
    df = df[df["week_period"].isin(complete_weeks)].copy()
    if df.empty:
        return pd.DataFrame(), "No complete 4h UTC weeks"
    return df, None


def build_weekly(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[pd.Period, pd.DataFrame]]:
    weekly = (
        df.groupby("week_period")
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            bars=("open", "size"),
        )
        .reset_index()
        .sort_values("week_period")
        .reset_index(drop=True)
    )
    by_week = {period: group.sort_values("datetime").reset_index(drop=True) for period, group in df.groupby("week_period")}
    return weekly, by_week


def first_touch(bars: pd.DataFrame, level: float, side: str) -> int | None:
    if side == "up":
        hits = bars.index[bars["high"] >= level].tolist()
    else:
        hits = bars.index[bars["low"] <= level].tolist()
    return hits[0] if hits else None


def sequence_outcome(target_i: int | None, opposing_i: int | None) -> str:
    if target_i is None and opposing_i is None:
        return "neither"
    if target_i is not None and opposing_i is None:
        return "target_only"
    if target_i is None and opposing_i is not None:
        return "opposing_only"
    if target_i < opposing_i:
        return "target_first"
    if opposing_i < target_i:
        return "opposing_first"
    return "same_4h_ambiguous"


def summarize(frame: pd.DataFrame, outcome_col: str, target_col: str, opposing_col: str) -> dict[str, Any]:
    total = len(frame)
    counts = frame[outcome_col].value_counts().to_dict() if total else {}

    def pct(value: int) -> float:
        return round(value / total * 100, 2) if total else 0.0

    target_before = int(counts.get("target_only", 0) + counts.get("target_first", 0))
    opposing_before = int(counts.get("opposing_only", 0) + counts.get("opposing_first", 0))
    return {
        "events": total,
        "sequence": {name: [int(counts.get(name, 0)), pct(int(counts.get(name, 0)))] for name in SEQUENCE_ORDER},
        "target_hit_anytime_week3": [
            int(frame[target_col].sum()) if total else 0,
            pct(int(frame[target_col].sum()) if total else 0),
        ],
        "opposing_hit_anytime_week3": [
            int(frame[opposing_col].sum()) if total else 0,
            pct(int(frame[opposing_col].sum()) if total else 0),
        ],
        "target_before_opposing": [target_before, pct(target_before)],
        "opposing_before_target": [opposing_before, pct(opposing_before)],
    }


def stat_pair(frame: pd.DataFrame, column: str) -> list[float | int]:
    total = len(frame)
    value = int(frame[column].sum()) if total and column in frame else 0
    return [value, round(value / total * 100, 2) if total else 0.0]


def analyze_usdt_pair(candidate: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    symbol = candidate["symbol"]
    df, error = fetch_4h_usdt(symbol)
    if error or df.empty:
        return None, {**candidate, "pair": f"{symbol}USDT", "reason": error or "No data"}

    weekly, by_week = build_weekly(df)
    if len(weekly) < 10:
        return None, {**candidate, "pair": f"{symbol}USDT", "reason": "Insufficient weekly history"}

    sweep_rows = []
    displacement_rows = []
    for i in range(1, len(weekly) - 1):
        week1 = weekly.iloc[i - 1]
        week2 = weekly.iloc[i]
        week3 = weekly.iloc[i + 1]
        bars = by_week.get(week3["week_period"])
        if bars is None or len(bars) != 42:
            continue

        week3_mid = float(week3["low"]) + ((float(week3["high"]) - float(week3["low"])) * 0.5)
        mid_i = first_touch(bars, week3_mid, "down")

        if week2["low"] < week1["low"] and week2["close"] > week1["low"]:
            target1 = float(week2["high"])
            target2 = float(week1["high"])
            opposing1 = float(week2["low"])
            opposing2 = float(week1["low"])
            target1_i = first_touch(bars, target1, "up")
            target2_i = first_touch(bars, target2, "up")
            opposing1_i = first_touch(bars, opposing1, "down")
            opposing2_i = first_touch(bars, opposing2, "down")
            sweep_rows.append(
                {
                    "target1_hit": target1_i is not None,
                    "target2_hit": target2_i is not None,
                    "opposing1_hit": opposing1_i is not None,
                    "opposing2_hit": opposing2_i is not None,
                    "target1_outcome": sequence_outcome(target1_i, opposing1_i),
                    "target2_outcome": sequence_outcome(target2_i, opposing2_i),
                    "mid_before_target1": mid_i is not None and target1_i is not None and mid_i < target1_i,
                    "inside_week2_range": week3["high"] < target1 and week3["low"] > opposing1,
                }
            )

        if week2["close"] > week1["high"]:
            target = float(week2["high"])
            opposing = float(week2["low"])
            target_i = first_touch(bars, target, "up")
            opposing_i = first_touch(bars, opposing, "down")
            displacement_rows.append(
                {
                    "target_hit": target_i is not None,
                    "opposing_hit": opposing_i is not None,
                    "outcome": sequence_outcome(target_i, opposing_i),
                    "mid_before_target": mid_i is not None and target_i is not None and mid_i < target_i,
                    "inside_week2_range": week3["high"] < target and week3["low"] > opposing,
                }
            )

    sweep = pd.DataFrame(sweep_rows)
    displacement = pd.DataFrame(displacement_rows)
    return (
        {
            **candidate,
            "pair": f"{symbol}USDT",
            "complete_weeks": int(len(weekly)),
            "weekly_first": str(weekly["week_period"].iloc[0]),
            "weekly_last": str(weekly["week_period"].iloc[-1]),
            "sweep_reclaim": {
                "setup": "Week2 low < Week1 low and Week2 close > Week1 low. Week3 only.",
                "target1_week2_high": summarize(sweep, "target1_outcome", "target1_hit", "opposing1_hit"),
                "target2_week1_high": summarize(sweep, "target2_outcome", "target2_hit", "opposing2_hit"),
                "week3_50pct_before_target1": stat_pair(sweep, "mid_before_target1"),
                "week3_inside_week2_range": stat_pair(sweep, "inside_week2_range"),
            },
            "bullish_displacement": {
                "setup": "Week2 close > Week1 high. No body or close-position filter. Week3 only.",
                "target_week2_high": summarize(displacement, "outcome", "target_hit", "opposing_hit"),
                "week3_50pct_before_target": stat_pair(displacement, "mid_before_target"),
                "week3_inside_week2_range": stat_pair(displacement, "inside_week2_range"),
            },
        },
        None,
    )


def metric(value: list[float | int]) -> str:
    return f"{value[0]} ({value[1]}%)"


def write_reports(results: list[dict[str, Any]], skipped: list[dict[str, Any]]) -> None:
    Path("reports").mkdir(exist_ok=True)
    payload = {
        "source_note": "Market-cap universe from CoinGecko because the CoinMarketCap public endpoint was unavailable. Each market is analyzed separately as SYMBOLUSDT on Binance 4h candles.",
        "tested_count": len(results),
        "results": results,
        "skipped": skipped,
    }
    Path("reports/weekly_top20_usdt_edge_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Weekly Day3 Edge Summary: Top USDT Pairs",
        "",
        payload["source_note"],
        "",
        "Stablecoins, wrapped assets, and staked assets are excluded.",
        "Weeks are UTC W-SUN. Week3 is tested with 4-hour candles only. No Week4 extension.",
        "",
        "## Comparison",
        "",
        "| # | Rank | Pair | Name | Weeks | Sweep T1 Before Opp | Sweep Opp Before T1 | Displacement T1 Before Opp | Displacement Opp Before T1 |",
        "|---:|---:|---|---|---:|---:|---:|---:|---:|",
    ]
    for index, result in enumerate(results, 1):
        sweep = result["sweep_reclaim"]["target1_week2_high"]
        displacement = result["bullish_displacement"]["target_week2_high"]
        lines.append(
            "| {index} | {rank} | {pair} | {name} | {weeks} | {sweep_target}% | {sweep_opp}% | {disp_target}% | {disp_opp}% |".format(
                index=index,
                rank=result["market_cap_rank"],
                pair=result["pair"],
                name=result["name"],
                weeks=result["complete_weeks"],
                sweep_target=sweep["target_before_opposing"][1],
                sweep_opp=sweep["opposing_before_target"][1],
                disp_target=displacement["target_before_opposing"][1],
                disp_opp=displacement["opposing_before_target"][1],
            )
        )

    lines.extend(["", "## Pair Details", ""])
    for result in results:
        sweep = result["sweep_reclaim"]["target1_week2_high"]
        displacement = result["bullish_displacement"]["target_week2_high"]
        lines.extend(
            [
                f"### {result['pair']} - {result['name']}",
                "",
                f"Weeks: {result['weekly_first']} to {result['weekly_last']} ({result['complete_weeks']} complete weeks)",
                "",
                "| Setup | Events | Target Hit Anytime | Target Before Opposing | Opposing Before Target | 50% Before Target | Inside Week2 Range |",
                "|---|---:|---:|---:|---:|---:|---:|",
                "| Sweep Reclaim T1 | {events} | {hit} | {target_before} | {opp_before} | {mid} | {inside} |".format(
                    events=sweep["events"],
                    hit=metric(sweep["target_hit_anytime_week3"]),
                    target_before=metric(sweep["target_before_opposing"]),
                    opp_before=metric(sweep["opposing_before_target"]),
                    mid=metric(result["sweep_reclaim"]["week3_50pct_before_target1"]),
                    inside=metric(result["sweep_reclaim"]["week3_inside_week2_range"]),
                ),
                "| Bullish Displacement | {events} | {hit} | {target_before} | {opp_before} | {mid} | {inside} |".format(
                    events=displacement["events"],
                    hit=metric(displacement["target_hit_anytime_week3"]),
                    target_before=metric(displacement["target_before_opposing"]),
                    opp_before=metric(displacement["opposing_before_target"]),
                    mid=metric(result["bullish_displacement"]["week3_50pct_before_target"]),
                    inside=metric(result["bullish_displacement"]["week3_inside_week2_range"]),
                ),
                "",
            ]
        )

    if skipped:
        lines.extend(
            [
                "## Skipped Before Filling 20",
                "",
                "| Rank | Pair | Name | Reason |",
                "|---:|---|---|---|",
            ]
        )
        for item in skipped:
            lines.append(f"| {item.get('market_cap_rank')} | {item.get('pair', item.get('symbol'))} | {item.get('name')} | {item.get('reason')} |")

    Path("reports/weekly_top20_usdt_edge_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    candidates = fetch_market_cap_candidates()
    results = []
    skipped = []
    for candidate in candidates:
        if len(results) >= 20:
            break
        result, skip = analyze_usdt_pair(candidate)
        if result:
            results.append(result)
            print(f"OK {len(results):02d}: {result['pair']} {result['name']}")
        else:
            skipped.append(skip or candidate)
            print(f"SKIP: {candidate['symbol']} {candidate['name']} - {(skip or {}).get('reason')}")

    write_reports(results, skipped)
    print("Wrote reports/weekly_top20_usdt_edge_summary.md")
    print("Wrote reports/weekly_top20_usdt_edge_summary.json")


if __name__ == "__main__":
    main()
