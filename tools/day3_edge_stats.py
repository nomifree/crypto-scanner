from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import pandas as pd


BASE_URL = "https://data-api.binance.vision/api/v3/klines"
INTERVAL = "1h"
LIMIT = 1000
START = "2017-08-17"
SEQUENCE_ORDER = [
    "target_only",
    "target_first",
    "opposing_first",
    "opposing_only",
    "same_hour_ambiguous",
    "neither",
]


def fetch_hourly(symbol: str) -> pd.DataFrame:
    start = int(pd.Timestamp(START, tz="UTC").timestamp() * 1000)
    end = int(pd.Timestamp.now(tz="UTC").timestamp() * 1000)
    rows: list[list[Any]] = []

    while start < end:
        params = urllib.parse.urlencode(
            {
                "symbol": f"{symbol}USDT",
                "interval": INTERVAL,
                "limit": LIMIT,
                "startTime": start,
                "endTime": end,
            }
        )
        request = urllib.request.Request(
            f"{BASE_URL}?{params}",
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            batch = json.loads(response.read().decode("utf-8"))
        if not batch:
            break

        rows.extend(batch)
        last_open = int(batch[-1][0])
        next_start = last_open + 60 * 60 * 1000
        if next_start <= start:
            break
        start = next_start
        time.sleep(0.05)

    if not rows:
        return pd.DataFrame()

    hourly = pd.DataFrame(
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
    hourly["datetime"] = pd.to_datetime(hourly["open_time"], unit="ms", utc=True)
    for column in ["open", "high", "low", "close"]:
        hourly[column] = pd.to_numeric(hourly[column], errors="coerce")
    hourly = hourly.dropna(subset=["open", "high", "low", "close"]).sort_values("datetime")

    today = pd.Timestamp.now(tz="UTC").normalize()
    hourly = hourly[hourly["datetime"] < today].copy()
    hourly["date"] = hourly["datetime"].dt.floor("D")
    complete_counts = hourly.groupby("date").size()
    complete_dates = set(complete_counts[complete_counts == 24].index)
    return hourly[hourly["date"].isin(complete_dates)].copy()


def rebuild_daily(hourly: pd.DataFrame) -> tuple[pd.DataFrame, dict[pd.Timestamp, pd.DataFrame]]:
    if hourly.empty:
        return pd.DataFrame(), {}
    daily = (
        hourly.groupby("date")
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            hours=("open", "size"),
        )
        .reset_index()
        .sort_values("date")
        .reset_index(drop=True)
    )
    by_date = {date: group.sort_values("datetime").reset_index(drop=True) for date, group in hourly.groupby("date")}
    return daily, by_date


def first_touch(day_hours: pd.DataFrame, level: float, side: str) -> int | None:
    if side == "up":
        hits = day_hours.index[day_hours["high"] >= level].tolist()
    else:
        hits = day_hours.index[day_hours["low"] <= level].tolist()
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
    return "same_hour_ambiguous"


def summarize_sequence(res: pd.DataFrame, outcome_column: str, target_column: str, opposing_column: str) -> dict[str, Any]:
    total = len(res)
    counts = res[outcome_column].value_counts().to_dict() if total else {}

    def pct(value: int) -> float:
        return round(value / total * 100, 2) if total else 0.0

    target_before = int(counts.get("target_only", 0) + counts.get("target_first", 0))
    opposing_before = int(counts.get("opposing_only", 0) + counts.get("opposing_first", 0))
    return {
        "events": total,
        "sequence": {name: [int(counts.get(name, 0)), pct(int(counts.get(name, 0)))] for name in SEQUENCE_ORDER},
        "target_hit_anytime_day3": [int(res[target_column].sum()) if total else 0, pct(int(res[target_column].sum()) if total else 0)],
        "opposing_hit_anytime_day3": [
            int(res[opposing_column].sum()) if total else 0,
            pct(int(res[opposing_column].sum()) if total else 0),
        ],
        "target_before_opposing": [target_before, pct(target_before)],
        "opposing_before_target": [opposing_before, pct(opposing_before)],
    }


def analyze_symbol(symbol: str) -> dict[str, Any]:
    hourly = fetch_hourly(symbol)
    daily, by_date = rebuild_daily(hourly)
    if hourly.empty or daily.empty:
        return {"symbol": symbol, "error": "No hourly data returned"}

    sweep_rows = []
    displacement_rows = []
    for i in range(1, len(daily) - 1):
        day1 = daily.iloc[i - 1]
        day2 = daily.iloc[i]
        day3 = daily.iloc[i + 1]
        day3_hours = by_date.get(day3["date"])
        if day3_hours is None or len(day3_hours) != 24:
            continue

        day3_high = float(day3["high"])
        day3_low = float(day3["low"])
        day3_mid = day3_low + ((day3_high - day3_low) * 0.5)
        mid_i = first_touch(day3_hours, day3_mid, "down")

        if day2["low"] < day1["low"] and day2["close"] > day1["low"]:
            t1 = float(day2["high"])
            t2 = float(day1["high"])
            opp1 = float(day2["low"])
            opp2 = float(day1["low"])
            t1_i = first_touch(day3_hours, t1, "up")
            t2_i = first_touch(day3_hours, t2, "up")
            opp1_i = first_touch(day3_hours, opp1, "down")
            opp2_i = first_touch(day3_hours, opp2, "down")
            sweep_rows.append(
                {
                    "signal_day": day2["date"],
                    "day3": day3["date"],
                    "t1_hit": t1_i is not None,
                    "t2_hit": t2_i is not None,
                    "opp1_hit": opp1_i is not None,
                    "opp2_hit": opp2_i is not None,
                    "t1_outcome": sequence_outcome(t1_i, opp1_i),
                    "t2_outcome": sequence_outcome(t2_i, opp2_i),
                    "mid_before_t1": mid_i is not None and t1_i is not None and mid_i < t1_i,
                    "mid_same_hour_or_before_t1": mid_i is not None and t1_i is not None and mid_i <= t1_i,
                    "inside_day2_range": day3["high"] < t1 and day3["low"] > opp1,
                    "inside_day1_range": day3["high"] < t2 and day3["low"] > opp2,
                    "day3_green": day3["close"] >= day3["open"],
                }
            )

        if day2["close"] > day1["high"]:
            t1 = float(day2["high"])
            opp = float(day2["low"])
            t1_i = first_touch(day3_hours, t1, "up")
            opp_i = first_touch(day3_hours, opp, "down")
            displacement_rows.append(
                {
                    "signal_day": day2["date"],
                    "day3": day3["date"],
                    "t1_hit": t1_i is not None,
                    "opp_hit": opp_i is not None,
                    "outcome": sequence_outcome(t1_i, opp_i),
                    "mid_before_t1": mid_i is not None and t1_i is not None and mid_i < t1_i,
                    "mid_same_hour_or_before_t1": mid_i is not None and t1_i is not None and mid_i <= t1_i,
                    "inside_day2_range": day3["high"] < t1 and day3["low"] > opp,
                    "day3_green": day3["close"] >= day3["open"],
                }
            )

    sweep = pd.DataFrame(sweep_rows)
    displacement = pd.DataFrame(displacement_rows)

    def stat_pair(frame: pd.DataFrame, column: str) -> list[float | int]:
        total = len(frame)
        value = int(frame[column].sum()) if total else 0
        return [value, round(value / total * 100, 2) if total else 0.0]

    return {
        "symbol": symbol,
        "source": f"Binance {symbol}USDT 1h candles rebuilt into UTC daily candles",
        "hourly_first": str(hourly["datetime"].min()),
        "hourly_last": str(hourly["datetime"].max()),
        "hourly_candles": int(len(hourly)),
        "daily_first": str(daily["date"].iloc[0].date()),
        "daily_last": str(daily["date"].iloc[-1].date()),
        "complete_daily_candles": int(len(daily)),
        "bullish_sweep_reclaim": {
            "setup": "Day2 low < Day1 low and Day2 close > Day1 low. Day3 only.",
            "target_1": "Day2 high",
            "target_2": "Day1 high",
            "opposing_1": "Day2 low",
            "opposing_2": "Day1 low",
            "target_1_stats": summarize_sequence(sweep, "t1_outcome", "t1_hit", "opp1_hit"),
            "target_2_stats": summarize_sequence(sweep, "t2_outcome", "t2_hit", "opp2_hit"),
            "day3_hit_50pct_range_before_t1": stat_pair(sweep, "mid_before_t1"),
            "day3_hit_50pct_range_same_hour_or_before_t1": stat_pair(sweep, "mid_same_hour_or_before_t1"),
            "day3_consolidated_inside_day2_range": stat_pair(sweep, "inside_day2_range"),
            "day3_consolidated_inside_day1_range": stat_pair(sweep, "inside_day1_range"),
            "day3_green_close": stat_pair(sweep, "day3_green"),
        },
        "bullish_displacement": {
            "setup": "Day2 close > Day1 high. No body or close-position filter. Day3 only.",
            "target": "Day2 high",
            "opposing": "Day2 low",
            "target_stats": summarize_sequence(displacement, "outcome", "t1_hit", "opp_hit"),
            "day3_hit_50pct_range_before_t1": stat_pair(displacement, "mid_before_t1"),
            "day3_hit_50pct_range_same_hour_or_before_t1": stat_pair(
                displacement, "mid_same_hour_or_before_t1"
            ),
            "day3_consolidated_inside_day2_range": stat_pair(displacement, "inside_day2_range"),
            "day3_green_close": stat_pair(displacement, "day3_green"),
        },
    }


def metric_line(name: str, value: list[float | int]) -> str:
    return f"| {name} | {value[0]} | {value[1]}% |"


def render_markdown(results: list[dict[str, Any]]) -> str:
    lines = [
        "# Day3 Edge Summary: BTC, ETH, ADA, LINK, LTC",
        "",
        "Data uses Binance 1-hour candles rebuilt into UTC daily candles.",
        "All tests are Day3-only. No Day4 extension is allowed.",
        "",
        "Definitions:",
        "- Bullish sweep reclaim: Day2 low < Day1 low and Day2 close > Day1 low.",
        "- Bullish displacement: Day2 close > Day1 high, with no body-size or close-position filter.",
        "- Target-before-opposing means Day3 reaches target before the opposing side on 1-hour sequence.",
        "",
    ]

    lines.append("## Comparison")
    lines.append("")
    lines.append("| Symbol | Sweep Events | Sweep T1 Before Opposing | Sweep Opposing Before T1 | Displacement Events | Displacement T1 Before Opposing | Displacement Opposing Before T1 |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for result in results:
        sweep_t1 = result["bullish_sweep_reclaim"]["target_1_stats"]
        disp = result["bullish_displacement"]["target_stats"]
        lines.append(
            "| {symbol} | {se} | {stbo}% | {sobt}% | {de} | {dtbo}% | {dobt}% |".format(
                symbol=result["symbol"],
                se=sweep_t1["events"],
                stbo=sweep_t1["target_before_opposing"][1],
                sobt=sweep_t1["opposing_before_target"][1],
                de=disp["events"],
                dtbo=disp["target_before_opposing"][1],
                dobt=disp["opposing_before_target"][1],
            )
        )

    for result in results:
        lines.extend(
            [
                "",
                f"## {result['symbol']}",
                "",
                f"Source: {result['source']}",
                f"Range: {result['daily_first']} to {result['daily_last']}",
                f"Complete daily candles: {result['complete_daily_candles']}",
                "",
                "### Bullish Sweep Reclaim",
                "",
                "Target 1 = Day2 high. Opposing side = Day2 low.",
                "",
                "| Metric | Count | % |",
                "|---|---:|---:|",
            ]
        )
        sweep_t1 = result["bullish_sweep_reclaim"]["target_1_stats"]
        lines.append(metric_line("Events", [sweep_t1["events"], 100.0]))
        lines.append(metric_line("Target hit anytime Day3", sweep_t1["target_hit_anytime_day3"]))
        lines.append(metric_line("Target before opposing", sweep_t1["target_before_opposing"]))
        lines.append(metric_line("Opposing before target", sweep_t1["opposing_before_target"]))
        lines.append(metric_line("50% Day3 range before T1", result["bullish_sweep_reclaim"]["day3_hit_50pct_range_before_t1"]))
        lines.append(metric_line("Consolidated inside Day2 range", result["bullish_sweep_reclaim"]["day3_consolidated_inside_day2_range"]))
        lines.append("")
        lines.append("Sequence:")
        lines.append("")
        lines.append("| Outcome | Count | % |")
        lines.append("|---|---:|---:|")
        for outcome, value in sweep_t1["sequence"].items():
            lines.append(metric_line(outcome, value))

        lines.extend(
            [
                "",
                "### Bullish Displacement",
                "",
                "Target = Day2 high. Opposing side = Day2 low.",
                "",
                "| Metric | Count | % |",
                "|---|---:|---:|",
            ]
        )
        disp = result["bullish_displacement"]["target_stats"]
        lines.append(metric_line("Events", [disp["events"], 100.0]))
        lines.append(metric_line("Target hit anytime Day3", disp["target_hit_anytime_day3"]))
        lines.append(metric_line("Target before opposing", disp["target_before_opposing"]))
        lines.append(metric_line("Opposing before target", disp["opposing_before_target"]))
        lines.append(metric_line("50% Day3 range before T1", result["bullish_displacement"]["day3_hit_50pct_range_before_t1"]))
        lines.append(metric_line("Consolidated inside Day2 range", result["bullish_displacement"]["day3_consolidated_inside_day2_range"]))
        lines.append("")
        lines.append("Sequence:")
        lines.append("")
        lines.append("| Outcome | Count | % |")
        lines.append("|---|---:|---:|")
        for outcome, value in disp["sequence"].items():
            lines.append(metric_line(outcome, value))

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", nargs="+", default=["BTC", "ETH", "ADA", "LINK", "LTC"])
    parser.add_argument("--out-md", default="reports/day3_edge_summary.md")
    parser.add_argument("--out-json", default="reports/day3_edge_summary.json")
    args = parser.parse_args()

    results = [analyze_symbol(symbol.upper()) for symbol in args.symbols]
    out_md = Path(args.out_md)
    out_json = Path(args.out_json)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    out_md.write_text(render_markdown(results), encoding="utf-8")
    print(f"Wrote {out_md}")
    print(f"Wrote {out_json}")


if __name__ == "__main__":
    main()
