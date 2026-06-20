from __future__ import annotations

import os
import time

import pandas as pd

from .clients import get_defillama_context, get_top_coins, get_waterfall_data
from .bias_runner import scan_markets
from .config import RISK_HEADERS, SETTINGS
from .ict import check_ict_logic
from .models import ScannerResult
from .risk_overlay import build_summary, evaluate_results
from .sheets import deliver_custom_tabs, deliver_outputs
from .timeframes import resample_ohlc


def should_run(now_pkt: pd.Timestamp) -> tuple[bool, bool]:
    is_monthly_run = now_pkt.day == 1
    is_weekly_run = now_pkt.weekday() == 0
    if not is_monthly_run and not is_weekly_run:
        return True, True
    return is_monthly_run, is_weekly_run


def tab_names(now_pkt: pd.Timestamp) -> tuple[str, str, str]:
    month_yr = now_pkt.strftime("%b%y")
    week_num = ((now_pkt.day - 1) // 7) + 1
    return f"{month_yr}_Monthly", f"{month_yr}_W{week_num}", f"{month_yr}_Risk_Summary"


def scan(now_utc: pd.Timestamp | None = None, sleep_fn=time.sleep) -> tuple[dict[str, list], dict[str, list], str, list]:
    now_utc = now_utc or pd.Timestamp.utcnow()
    now_pkt = now_utc.tz_convert("Asia/Karachi")
    today_str = now_pkt.strftime("%Y-%m-%d")
    monthly_tab, weekly_tab, summary_tab = tab_names(now_pkt)
    is_monthly_run, is_weekly_run = should_run(now_pkt)
    coin_limit = SETTINGS.monthly_coin_limit if is_monthly_run else SETTINGS.weekly_coin_limit

    print(f"Starting scan for {today_str}. Monthly={is_monthly_run}, Weekly={is_weekly_run}")
    coins = get_top_coins(coin_limit, sleep_fn=sleep_fn)
    defillama = get_defillama_context()

    monthly_results: list[ScannerResult] = []
    weekly_results: list[ScannerResult] = []
    btc_ohlc = None

    for i, coin in enumerate(coins):
        if SETTINGS.sleep_seconds:
            sleep_fn(SETTINGS.sleep_seconds)
        df_daily, source = get_waterfall_data(coin.coin_id, coin.symbol)
        if df_daily is None:
            continue
        if coin.symbol == "BTC":
            btc_ohlc = df_daily

        if is_monthly_run:
            df_m = resample_ohlc(df_daily, "Monthly", now_utc)
            signal = check_ict_logic(df_m)
            if signal.qualified:
                monthly_results.append(
                    ScannerResult(today_str, coin, source, "Monthly", coin.current_price, signal, df_daily)
                )

        if is_weekly_run and i < SETTINGS.weekly_coin_limit:
            df_w = resample_ohlc(df_daily, "Weekly", now_utc)
            signal = check_ict_logic(df_w)
            if signal.qualified:
                weekly_results.append(
                    ScannerResult(today_str, coin, source, "Weekly", coin.current_price, signal, df_daily)
                )

    if btc_ohlc is None:
        btc_ohlc, _ = get_waterfall_data("bitcoin", "BTC")

    monthly_risk = evaluate_results(monthly_results, btc_ohlc, defillama)
    weekly_risk = evaluate_results(weekly_results, btc_ohlc, defillama)
    all_risk = monthly_risk + weekly_risk

    base_tabs = {}
    risk_tabs = {}
    if is_monthly_run:
        base_tabs[monthly_tab] = [row.base_row() for row in monthly_results]
        risk_tabs[f"{monthly_tab}_Risk"] = [row.risk_row(RISK_HEADERS) for row in monthly_risk]
    if is_weekly_run:
        base_tabs[weekly_tab] = [row.base_row() for row in weekly_results]
        risk_tabs[f"{weekly_tab}_Risk"] = [row.risk_row(RISK_HEADERS) for row in weekly_risk]
    summary_rows = build_summary(all_risk)
    return base_tabs, risk_tabs, summary_tab, summary_rows


def main() -> None:
    mode = os.getenv("SCAN_MODE", SETTINGS.scan_mode).strip().lower()
    if mode not in {"crypto", "pmex", "psx", "markets", "all"}:
        raise ValueError("SCAN_MODE must be one of crypto, pmex, psx, markets, all.")

    if mode in {"crypto", "all"}:
        base_tabs, risk_tabs, summary_tab, summary_rows = scan()
        deliver_outputs(base_tabs, risk_tabs, summary_tab, summary_rows)

    if mode in {"pmex", "psx", "markets", "all"}:
        market_tabs = scan_markets(mode)
        deliver_custom_tabs(market_tabs)


def crypto_main() -> None:
    base_tabs, risk_tabs, summary_tab, summary_rows = scan()
    deliver_outputs(base_tabs, risk_tabs, summary_tab, summary_rows)
