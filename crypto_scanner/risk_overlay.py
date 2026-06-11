from __future__ import annotations

from collections import defaultdict, deque
from math import isfinite
from math import log
from typing import Any

import pandas as pd

from .models import DefiLlamaContext, RiskResult, ScannerResult
from .shariah import screen_asset


def clamp(value: float, low: float = 0, high: float = 100) -> float:
    if not isfinite(value):
        return 0
    return max(low, min(high, value))


def log_returns(close: pd.Series, window: int) -> pd.Series:
    returns = (close.astype(float) / close.astype(float).shift(1)).apply(lambda x: pd.NA if x <= 0 else x)
    returns = returns.dropna().astype(float).map(log)
    return returns.tail(window)


def align_returns(left: pd.Series, right: pd.Series) -> tuple[pd.Series, pd.Series]:
    joined = pd.concat([left, right], axis=1, join="inner").dropna()
    if joined.shape[0] < 10:
        return pd.Series(dtype=float), pd.Series(dtype=float)
    return joined.iloc[:, 0], joined.iloc[:, 1]


def safe_corr(left: pd.Series, right: pd.Series) -> float | None:
    a, b = align_returns(left, right)
    if a.empty:
        return None
    corr = float(a.corr(b))
    return corr if isfinite(corr) else None


def safe_beta(asset: pd.Series, benchmark: pd.Series) -> float | None:
    a, b = align_returns(asset, benchmark)
    if a.empty:
        return None
    variance = float(b.var())
    if variance == 0 or not isfinite(variance):
        return None
    beta = float(a.cov(b) / variance)
    return beta if isfinite(beta) else None


def liquidity_score(volume: float | None) -> float:
    if volume is None:
        return 20
    if volume > 500_000_000:
        return 100
    if volume > 100_000_000:
        return 80
    if volume > 25_000_000:
        return 60
    if volume > 5_000_000:
        return 40
    return 20


def volatility_score(df: pd.DataFrame) -> float:
    if df is None or len(df) < 30:
        return 30
    close = df["close"].astype(float).tail(30)
    returns = close.pct_change().dropna()
    if returns.empty:
        return 30
    vol = float(returns.std())
    if vol <= 0.025:
        return 90
    if vol <= 0.04:
        return 75
    if vol <= 0.06:
        return 55
    if vol <= 0.09:
        return 35
    return 20


def setup_score(grade: str) -> float:
    if grade.startswith("A-Tier"):
        return 90
    if grade.startswith("B-Tier"):
        return 75
    if grade.startswith("C-Tier"):
        return 50
    return 25


def valuation_score(result: ScannerResult) -> float:
    bullish = "Bullish" in result.signal.bias
    bearish = "Bearish" in result.signal.bias
    if bullish and result.signal.valuation == "Discount":
        return 100
    if bearish and result.signal.valuation == "Premium":
        return 100
    return 45


def protocol_scores(result: ScannerResult, context: DefiLlamaContext) -> dict[str, Any]:
    symbol = result.coin.symbol.upper()
    protocol = context.protocol_by_symbol.get(symbol) or context.protocol_by_symbol.get(result.coin.name.upper())
    category = protocol.get("category", "") if isinstance(protocol, dict) else ""
    tvl = float(protocol.get("tvl") or 0) if isinstance(protocol, dict) else 0
    tvl_score = 80 if tvl > 1_000_000_000 else 65 if tvl > 100_000_000 else 45 if tvl > 0 else 35

    fee_data = context.fees_by_name.get(result.coin.name.lower()) or context.fees_by_name.get(symbol.lower())
    fees_score = 70 if fee_data else 35
    dex_data = context.dex_by_name.get(result.coin.name.lower()) or context.dex_by_name.get(symbol.lower())
    dex_score = 70 if dex_data else 35
    data_quality = context.data_quality if protocol or fee_data or dex_data else "Manual Review"

    return {
        "DefiLlama Category": category,
        "TVL Score": tvl_score,
        "Fees/Revenue Score": fees_score,
        "DEX Volume Score": dex_score,
        "On-Chain Data Quality": data_quality,
    }


def volume_market_cap_ratio(result: ScannerResult) -> float | None:
    market_cap = result.coin.market_cap
    volume = result.coin.volume_24h
    if not market_cap or market_cap <= 0 or volume is None:
        return None
    return (volume / market_cap) * 100


def build_clusters(corr_matrix: dict[tuple[str, str], float], symbols: list[str], threshold: float = 0.65) -> dict[str, str]:
    graph: dict[str, set[str]] = {symbol: set() for symbol in symbols}
    for (a, b), corr in corr_matrix.items():
        if corr >= threshold:
            graph[a].add(b)
            graph[b].add(a)

    clusters: dict[str, str] = {}
    seen: set[str] = set()
    cluster_num = 1
    for symbol in symbols:
        if symbol in seen:
            continue
        queue: deque[str] = deque([symbol])
        members: list[str] = []
        seen.add(symbol)
        while queue:
            node = queue.popleft()
            members.append(node)
            for neighbor in graph[node]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        cluster_id = f"C{cluster_num}_{'-'.join(sorted(members)[:3])}"
        for member in members:
            clusters[member] = cluster_id
        cluster_num += 1
    return clusters


def evaluate_results(
    results: list[ScannerResult],
    btc_ohlc: pd.DataFrame | None,
    defillama: DefiLlamaContext,
) -> list[RiskResult]:
    if not results:
        return []

    returns_30 = {r.coin.symbol: log_returns(r.daily_ohlc["close"], 30) for r in results}
    returns_90 = {r.coin.symbol: log_returns(r.daily_ohlc["close"], 90) for r in results}
    btc_30 = log_returns(btc_ohlc["close"], 30) if btc_ohlc is not None else pd.Series(dtype=float)
    btc_90 = log_returns(btc_ohlc["close"], 90) if btc_ohlc is not None else pd.Series(dtype=float)

    symbols = [r.coin.symbol for r in results]
    pair_corrs: dict[tuple[str, str], float] = {}
    for i, left in enumerate(symbols):
        for right in symbols[i + 1:]:
            corr = safe_corr(returns_90[left], returns_90[right])
            if corr is not None:
                pair_corrs[(left, right)] = corr

    clusters = build_clusters(pair_corrs, symbols)
    cluster_density: dict[str, float] = defaultdict(float)
    cluster_members: dict[str, list[str]] = defaultdict(list)
    for symbol, cluster_id in clusters.items():
        cluster_members[cluster_id].append(symbol)
    for cluster_id, members in cluster_members.items():
        vals = []
        for i, left in enumerate(members):
            for right in members[i + 1:]:
                vals.append(pair_corrs.get((left, right), pair_corrs.get((right, left), 0)))
        cluster_density[cluster_id] = sum(vals) / len(vals) if vals else 0

    interim: list[tuple[ScannerResult, dict[str, Any]]] = []
    for result in results:
        symbol = result.coin.symbol
        btc_corr_30 = safe_corr(returns_30[symbol], btc_30)
        btc_corr_90 = safe_corr(returns_90[symbol], btc_90)
        btc_beta = safe_beta(returns_90[symbol], btc_90)
        pair_values = [
            abs(corr)
            for (a, b), corr in pair_corrs.items()
            if a == symbol or b == symbol
        ]
        avg_pair = sum(pair_values) / len(pair_values) if pair_values else 0
        cluster_id = clusters[symbol]
        protocol = protocol_scores(result, defillama)
        shariah = screen_asset(result.coin, protocol.get("DefiLlama Category"))
        liq_score = liquidity_score(result.coin.volume_24h)
        vol_score = volatility_score(result.daily_ohlc)
        tvl_score = float(protocol["TVL Score"])
        fees_score = float(protocol["Fees/Revenue Score"])
        dex_score = float(protocol["DEX Volume Score"])
        onchain_score = (tvl_score + fees_score + dex_score) / 3
        correlation_risk = clamp(
            100
            * (
                0.45 * max(0, btc_corr_90 or 0)
                + 0.35 * avg_pair
                + 0.20 * cluster_density[cluster_id]
            )
        )
        beta_base = 25 if (btc_beta or 0) <= 0.6 else 45 if (btc_beta or 0) <= 1.0 else 70 if (btc_beta or 0) <= 1.5 else 90
        beta_risk = clamp(beta_base + (10 if vol_score < 35 else 0))
        liquidity_risk = 100 - liq_score
        supply_penalty = 40 if result.coin.fdv and result.coin.market_cap and result.coin.fdv > result.coin.market_cap * 5 else 0
        shariah_penalty = 0 if shariah["Shariah Status"] == "Pass" else 50 if shariah["Shariah Status"] == "Review" else 100
        final_risk = clamp(
            0.30 * correlation_risk
            + 0.25 * beta_risk
            + 0.20 * liquidity_risk
            + 0.15 * supply_penalty
            + 0.10 * shariah_penalty
        )
        candidate = clamp(
            0.25 * setup_score(result.signal.grade)
            + 0.20 * valuation_score(result)
            + 0.20 * onchain_score
            + 0.20 * liq_score
            + 0.15 * (100 - final_risk)
        )
        if shariah["Shariah Status"] == "Fail":
            candidate = 0
        elif shariah["Shariah Status"] == "Review":
            candidate = min(candidate, 50)
        if liq_score < 40:
            candidate = min(candidate, 55)
        if final_risk > 80:
            candidate = min(candidate, 40)

        fields = {
            "Market Cap Rank": result.coin.market_cap_rank,
            "Market Cap": result.coin.market_cap,
            "FDV": result.coin.fdv,
            "Volume 24H": result.coin.volume_24h,
            "Volume / Market Cap %": volume_market_cap_ratio(result),
            "Liquidity Score": round(liq_score, 2),
            "Volatility Score": round(vol_score, 2),
            "BTC Corr 30D": round(btc_corr_30, 4) if btc_corr_30 is not None else "",
            "BTC Corr 90D": round(btc_corr_90, 4) if btc_corr_90 is not None else "",
            "BTC Beta 90D": round(btc_beta, 4) if btc_beta is not None else "",
            "Avg Pairwise Corr": round(avg_pair, 4),
            "Cluster ID": cluster_id,
            "Cluster Density": round(cluster_density[cluster_id], 4),
            "DefiLlama Category": protocol["DefiLlama Category"],
            "TVL Score": round(tvl_score, 2),
            "Fees/Revenue Score": round(fees_score, 2),
            "DEX Volume Score": round(dex_score, 2),
            "Stablecoin Regime": defillama.stablecoin_regime,
            "On-Chain Data Quality": protocol["On-Chain Data Quality"],
            **shariah,
            "Correlation Risk Score": round(correlation_risk, 2),
            "Beta Risk Score": round(beta_risk, 2),
            "Liquidity Risk Score": round(liquidity_risk, 2),
            "Final Risk Score": round(final_risk, 2),
            "Candidate Score": round(candidate, 2),
            "Max Allocation %": "",
            "Position Risk %": "",
            "Risk Notes": "",
        }
        interim.append((result, fields))

    ranked_by_cluster: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for _, fields in interim:
        ranked_by_cluster[fields["Cluster ID"]].append(fields)
    for fields_list in ranked_by_cluster.values():
        fields_list.sort(key=lambda item: item["Candidate Score"], reverse=True)
        for rank, fields in enumerate(fields_list, start=1):
            fields["Cluster Rank"] = rank

    final: list[RiskResult] = []
    for result, fields in interim:
        action = action_for(fields)
        fields["Action"] = action
        fields["Max Allocation %"], fields["Position Risk %"] = sizing_for(action, result.signal.grade)
        fields["Risk Notes"] = risk_notes(fields)
        final.append(RiskResult(result, fields))
    return final


def action_for(fields: dict[str, Any]) -> str:
    if fields["Shariah Status"] == "Fail":
        return "BLOCK"
    if fields["Shariah Status"] == "Review":
        return "ESCALATE_SHARIAH_REVIEW"
    if fields["Final Risk Score"] > 80:
        return "BLOCK"
    if fields.get("Cluster Rank", 99) > 2:
        return "WATCHLIST_ONLY"
    candidate = fields["Candidate Score"]
    final_risk = fields["Final Risk Score"]
    if candidate >= 80 and final_risk <= 45:
        return "ALLOW"
    if 70 <= candidate < 80 and final_risk <= 55:
        return "ALLOW_REDUCED_SIZE"
    return "WATCHLIST_ONLY"


def sizing_for(action: str, grade: str) -> tuple[float, float]:
    if action in {"BLOCK", "ESCALATE_SHARIAH_REVIEW", "WATCHLIST_ONLY"}:
        return 0, 0
    if grade.startswith("A-Tier"):
        return (12, 1.0) if action == "ALLOW" else (6, 0.5)
    if grade.startswith("B-Tier"):
        return (6, 0.5) if action == "ALLOW" else (3, 0.25)
    return 2, 0.25


def risk_notes(fields: dict[str, Any]) -> str:
    notes = []
    if fields["Avg Pairwise Corr"] >= 0.75:
        notes.append("High pairwise correlation; treat as duplicate beta.")
    if fields["Final Risk Score"] > 65:
        notes.append("High final risk score.")
    if fields["Liquidity Score"] < 40:
        notes.append("Weak spot liquidity.")
    if fields["On-Chain Data Quality"] == "Manual Review":
        notes.append("Free on-chain mapping unavailable; manual review required.")
    return " ".join(notes)


def build_summary(risk_results: list[RiskResult]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    allowed = [r for r in risk_results if r.fields["Action"] in {"ALLOW", "ALLOW_REDUCED_SIZE"}]
    watch = [r for r in risk_results if r.fields["Action"] == "WATCHLIST_ONLY"]
    review = [r for r in risk_results if r.fields["Action"] == "ESCALATE_SHARIAH_REVIEW"]
    blocked = [r for r in risk_results if r.fields["Action"] == "BLOCK"]
    for result in sorted(allowed, key=lambda r: r.fields["Candidate Score"], reverse=True)[:10]:
        rows.append(["Top Eligible", result.base.coin.symbol, result.fields["Candidate Score"], result.fields["Action"], result.fields["Cluster ID"]])
    for result in review[:20]:
        rows.append(["Shariah Review Queue", result.base.coin.symbol, result.fields["Candidate Score"], result.fields["Action"], result.fields["Review Trigger"]])
    for result in blocked[:20]:
        rows.append(["Blocked", result.base.coin.symbol, result.fields["Final Risk Score"], result.fields["Action"], result.fields["Risk Notes"]])
    clusters: dict[str, list[RiskResult]] = defaultdict(list)
    for result in risk_results:
        clusters[result.fields["Cluster ID"]].append(result)
    for cluster_id, members in sorted(clusters.items(), key=lambda item: len(item[1]), reverse=True)[:10]:
        density = members[0].fields["Cluster Density"] if members else 0
        rows.append(["Highest Correlation Clusters", cluster_id, density, "Monitor", f"{len(members)} candidates in cluster"])
    if risk_results:
        regime = risk_results[0].fields["Stablecoin Regime"]
        rows.append(["Market Regime", "Stablecoins", regime, "Monitor", "Based on free DefiLlama stablecoin chart when available."])
    rows.append(["Data Quality", "On-chain", "", "Manual Review", "Exchange flows, holder concentration, unlocks, and Shariah business-model checks are review fields in v1."])
    if not rows:
        rows.append(["No Risk Rows", "", "", "None", "No qualified setups found."])
    return rows
