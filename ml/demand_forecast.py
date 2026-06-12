"""
demand_forecast.py
──────────────────
Module 4: ML demand forecasting layer.

Generates a synthetic but realistic monthly load factor time series
for the DXB-BOM corridor, calibrated to:
- Emirates ISC load factor: ~82% base
- Strong seasonality: peaks Dec/Jan and Jul/Aug
- India GDP growth trend: +0.3% LF uplift per year
- ISC-specific seasonality: Diwali, Eid, IPL season effects

This module will be replaced by a real Prophet model in Phase 2.
"""

import numpy as np


ISC_SEASONAL_FACTORS = {
    1:  1.08, 2:  0.97, 3:  0.99, 4:  1.02,
    5:  0.94, 6:  0.96, 7:  1.05, 8:  1.07,
    9:  0.95, 10: 0.96, 11: 1.04, 12: 1.09,
}

EVENT_OVERLAYS = {
    "diwali_month": 11,
    "diwali_lift": 0.03,
    "eid_months": [4, 5],
    "eid_lift": 0.02,
    "ipl_months": [3, 4, 5],
    "ipl_drag": -0.005,
}


def generate_seasonal_baseline(base_lf=0.82, n_months=12, india_gdp_annual_growth=0.087, start_month=1):
    """Generate deterministic seasonal load factor baseline."""
    monthly_growth_rate = (1 + india_gdp_annual_growth * 0.12) ** (1/12) - 1

    baseline = np.zeros(n_months)
    for i in range(n_months):
        month = ((start_month - 1 + i) % 12) + 1
        seasonal = ISC_SEASONAL_FACTORS[month]

        event_adj = 0.0
        if month == EVENT_OVERLAYS["diwali_month"]:
            event_adj += EVENT_OVERLAYS["diwali_lift"]
        if month in EVENT_OVERLAYS["eid_months"]:
            event_adj += EVENT_OVERLAYS["eid_lift"]
        if month in EVENT_OVERLAYS["ipl_months"]:
            event_adj += EVENT_OVERLAYS["ipl_drag"]

        trend = (1 + monthly_growth_rate) ** i
        baseline[i] = base_lf * seasonal * trend + event_adj

    return np.clip(baseline, 0.30, 0.98)


def generate_forecast_with_uncertainty(base_lf=0.82, n_months=12, n_simulations=1000, residual_sigma=0.035, seed=42):
    """Prophet-equivalent: seasonal baseline + stochastic residuals."""
    rng = np.random.default_rng(seed)
    baseline = generate_seasonal_baseline(base_lf, n_months)

    rho = 0.30
    simulations = np.zeros((n_simulations, n_months))
    for i in range(n_simulations):
        eps = rng.normal(0, residual_sigma, n_months)
        resid = np.zeros(n_months)
        resid[0] = eps[0]
        for t in range(1, n_months):
            resid[t] = rho * resid[t-1] + eps[t]
        simulations[i] = np.clip(baseline + resid, 0.20, 1.0)

    return {
        "baseline": baseline,
        "lower_80": np.percentile(simulations, 10, axis=0),
        "upper_80": np.percentile(simulations, 90, axis=0),
        "lower_95": np.percentile(simulations, 2.5, axis=0),
        "upper_95": np.percentile(simulations, 97.5, axis=0),
        "simulations": simulations,
        "months": list(range(1, n_months + 1)),
        "month_labels": [
            ["Jan","Feb","Mar","Apr","May","Jun",
             "Jul","Aug","Sep","Oct","Nov","Dec"][m % 12]
            for m in range(n_months)
        ],
    }


def get_competitive_baseline_comparison():
    """Return load factor baselines for key ISC competitors."""
    return {
        "Emirates":  {"base_lf": 0.82, "market_share": 0.35, "weekly_flights": 500},
        "Etihad":    {"base_lf": 0.86, "market_share": 0.15, "weekly_flights": 220},
        "Qatar":     {"base_lf": 0.80, "market_share": 0.20, "weekly_flights": 350},
        "Air India": {"base_lf": 0.70, "market_share": 0.15, "weekly_flights": 200},
        "IndiGo":    {"base_lf": 0.85, "market_share": 0.10, "weekly_flights": 150},
    }