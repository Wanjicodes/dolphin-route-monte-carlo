"""
risk_metrics.py
───────────────
Module 3: Risk metrics are computed from simulation output.

Metrics:
- VaR (Value at Risk) at 95% and 99%
- ES / CVaR (Expected Shortfall)
- Probability of loss-making year/quarter
- Break-Even Load Factor (BELF) distribution
- Profit percentiles (P5, P25, P50, P75, P95)
- Fuel sensitivity: ΔProfit per $10/bbl Brent
"""

import numpy as np


def var(profits, confidence=0.95):
    """Value at Risk: loss exceeded with probability (1 - confidence)."""
    return float(-np.percentile(profits, (1 - confidence) * 100))


def expected_shortfall(profits, confidence=0.95):
    """Expected Shortfall (CVaR): mean loss in the worst tail."""
    threshold = np.percentile(profits, (1 - confidence) * 100)
    tail = profits[profits <= threshold]
    return float(-tail.mean()) if len(tail) > 0 else 0.0


def probability_of_loss(profits):
    """P(annual profit < 0)"""
    return float((profits < 0).mean())


def probability_of_loss_quarter(monthly_profits):
    """P(any quarter sum < 0)"""
    n_paths, n_months = monthly_profits.shape
    quarterly = np.array([
        monthly_profits[:, i*3:(i+1)*3].sum(axis=1)
        for i in range(n_months // 3)
    ])
    any_loss_quarter = (quarterly < 0).any(axis=0)
    return float(any_loss_quarter.mean())


def belf_breach_probability(belf, actual_lf):
    """P(actual load factor < BELF)"""
    mean_lf = np.nanmean(actual_lf, axis=1)
    return float((mean_lf < belf).mean())


def profit_percentiles(profits):
    """Return key percentiles of the profit distribution."""
    percentiles = [1, 5, 10, 25, 50, 75, 90, 95, 99]
    return {f"P{p}": float(np.percentile(profits, p)) for p in percentiles}


def rask_cask_margin_stats(results):
    """Statistics on the RASK-CASK margin (PASK)."""
    pask = results["annual_pask"]
    return {
        "mean": float(np.nanmean(pask)),
        "std": float(np.nanstd(pask)),
        "P5": float(np.nanpercentile(pask, 5)),
        "P50": float(np.nanpercentile(pask, 50)),
        "P95": float(np.nanpercentile(pask, 95)),
        "pct_positive": float((pask > 0).mean()),
    }


def compute_all_metrics(results):
    """Compute the full risk metrics suite."""
    profits = results["annual_profit"]
    monthly = results["monthly_profit"]
    belf = results["belf"]
    lf = results["load_factor_realised"]

    return {
        "mean_annual_profit_usd": float(profits.mean()),
        "std_annual_profit_usd": float(profits.std()),
        "median_annual_profit_usd": float(np.median(profits)),
        "var_95_usd": var(profits, 0.95),
        "var_99_usd": var(profits, 0.99),
        "es_95_usd": expected_shortfall(profits, 0.95),
        "es_99_usd": expected_shortfall(profits, 0.99),
        "prob_annual_loss": probability_of_loss(profits),
        "prob_quarterly_loss": probability_of_loss_quarter(monthly),
        "prob_belf_breach": belf_breach_probability(belf, lf),
        "profit_percentiles": profit_percentiles(profits),
        "mean_rask": float(np.nanmean(results["annual_rask"])),
        "mean_cask": float(np.nanmean(results["annual_cask"])),
        "mean_pask": float(np.nanmean(results["annual_pask"])),
        "mean_load_factor": float(np.nanmean(lf)),
        "mean_belf": float(np.nanmean(belf)),
        "rask_cask_margin": rask_cask_margin_stats(results),
        "mean_annual_revenue_usd": float(results["annual_revenue"].mean()),
        "mean_annual_cost_usd": float(results["annual_cost"].mean()),
        "mean_fuel_cost_usd": float(results["fuel_cost"].sum(axis=1).mean()),
        "mean_ex_fuel_cost_usd": float(results["ex_fuel_cost"].sum(axis=1).mean()),
        "fuel_cost_pct": float(
            results["fuel_cost"].sum(axis=1).mean() /
            results["annual_cost"].mean()
        ),
    }


def fuel_sensitivity(base_results, stressed_results):
    """ΔProfit per $10/bbl increase in Brent crude."""
    base_mean = base_results["annual_profit"].mean()
    stressed_mean = stressed_results["annual_profit"].mean()
    delta_per_10 = (stressed_mean - base_mean) * (10 / 25)
    return float(delta_per_10)


def scenario_comparison(all_results):
    """Build comparison table across all scenarios."""
    comparison = {}
    for scenario_name, results in all_results.items():
        profits = results["annual_profit"]
        comparison[scenario_name] = {
            "mean_profit": float(profits.mean()),
            "P5_profit": float(np.percentile(profits, 5)),
            "P50_profit": float(np.percentile(profits, 50)),
            "P95_profit": float(np.percentile(profits, 95)),
            "prob_loss": float((profits < 0).mean()),
            "var_95": var(profits, 0.95),
            "mean_lf": float(np.nanmean(results["load_factor_realised"])),
            "mean_rask": float(np.nanmean(results["annual_rask"])),
            "mean_cask": float(np.nanmean(results["annual_cask"])),
        }
    return comparison