"""
impact_model.py
───────────────
Module 2: Deterministic financial cascade.

Given a ShockPack, this computes route P&L for every path and every month.
There is no randomness here,all stochasticity lives in shock_generator.py.

P&L cascade:
  ASK → RPK → Passenger Revenue → Total Revenue → RASK
  Fuel Cost → Ex-Fuel Cost → Total CASK
  PASK = RASK - CASK
  Monthly Profit = PASK × ASK
"""

import numpy as np
from data.assumptions import ROUTE, REVENUE, COSTS, OPERATIONS
from engine.shock_generator import ShockPack


def compute_ask(shock):
    """Available Seat Kilometres per month."""
    seats = ROUTE["seats_total"]
    distance = ROUTE["distance_km"]
    freq = ROUTE["frequency_daily"]
    days_per_month = ROUTE["operating_days"] / 12

    base_ask = seats * distance * freq * days_per_month
    ask = np.full((shock.n_paths, shock.n_months), base_ask * shock.ask_scale)

    reg_affected = shock.reg_shock
    ask[reg_affected, :] *= (1 - 0.15)

    aog_ask_loss = seats * distance * freq
    ask -= shock.aog_shock * aog_ask_loss

    return np.clip(ask, 0, None)


def compute_rpk(ask, shock):
    """RPK = ASK × Load Factor (with geo shock adjustment)."""
    lf = shock.load_factor
    lf_adjusted = lf.copy()
    lf_adjusted[shock.geo_shock] *= 0.65
    return ask * np.clip(lf_adjusted, 0.05, 1.0)


def compute_passenger_revenue(rpk, shock):
    """Passenger Revenue = RPK × Blended Yield (no-show adjusted)."""
    base_rev = rpk * shock.yield_per_rpk
    no_show_recovery = 0.40
    no_show_adj = 1 - REVENUE["no_show_rate_base"] * (1 - no_show_recovery)
    return base_rev * no_show_adj


def compute_ancillary_cargo_revenue(rpk, pax_revenue):
    """Cargo + Ancillary revenue."""
    cargo = pax_revenue * REVENUE["cargo_revenue_pct_of_passenger"]
    avg_distance = ROUTE["distance_km"]
    avg_pax_per_month = rpk / avg_distance
    ancillary = avg_pax_per_month * REVENUE["ancillary_revenue_per_pax_usd"]
    return cargo + ancillary


def compute_fuel_cost(ask, shock):
    """Fuel cost with hedging."""
    hr = COSTS["hedge_ratio"]
    hp = COSTS["hedge_price_usd_per_barrel"]
    market_price = shock.fuel_price

    effective_price = hr * hp + (1 - hr) * market_price

    total_km = ask / ROUTE["seats_total"]
    fuel_kg = total_km * COSTS["fuel_burn_kg_per_km"]
    fuel_liters = fuel_kg * COSTS["fuel_density_liters_per_kg"]
    fuel_barrels = fuel_liters * COSTS["barrels_per_liter"]

    return fuel_barrels * effective_price


def compute_ex_fuel_cost(ask, shock):
    """Ex-fuel operating costs."""
    base_ex_fuel = ask * COSTS["cask_ex_fuel_usd"]
    comp_cost_uplift = 1 + 0.04 * shock.competitive_index
    return base_ex_fuel * comp_cost_uplift


def compute_overbooking_cost(rpk):
    """Cost of denied boarding."""
    avg_pax = rpk / ROUTE["distance_km"]
    overbook_rate = OPERATIONS["overbooking_rate"]
    expected_denied = avg_pax * overbook_rate * 0.10
    return expected_denied * OPERATIONS["compensation_cost_per_denied_pax_usd"]


def run_impact_model(shock):
    """Full financial cascade for a given ShockPack."""
    ask = compute_ask(shock)
    rpk = compute_rpk(ask, shock)
    load_factor_realised = np.where(ask > 0, rpk / ask, 0)

    pax_revenue = compute_passenger_revenue(rpk, shock)
    other_revenue = compute_ancillary_cargo_revenue(rpk, pax_revenue)
    total_revenue = pax_revenue + other_revenue

    fuel_cost = compute_fuel_cost(ask, shock)
    ex_fuel_cost = compute_ex_fuel_cost(ask, shock)
    overbook_cost = compute_overbooking_cost(rpk)
    total_cost = fuel_cost + ex_fuel_cost + overbook_cost

    safe_ask = np.where(ask > 0, ask, np.nan)
    rask = total_revenue / safe_ask
    cask = total_cost / safe_ask
    pask = rask - cask

    monthly_profit = total_revenue - total_cost

    annual_profit = monthly_profit.sum(axis=1)
    annual_revenue = total_revenue.sum(axis=1)
    annual_cost = total_cost.sum(axis=1)
    annual_ask = ask.sum(axis=1)

    annual_rask = annual_revenue / annual_ask
    annual_cask = annual_cost / annual_ask
    annual_pask = annual_rask - annual_cask

    mean_yield = np.nanmean(shock.yield_per_rpk, axis=1)
    belf = np.where(mean_yield > 0, np.nanmean(cask, axis=1) / mean_yield, np.nan)

    return {
        "ask": ask, "rpk": rpk, "load_factor_realised": load_factor_realised,
        "pax_revenue": pax_revenue, "other_revenue": other_revenue,
        "total_revenue": total_revenue, "fuel_cost": fuel_cost,
        "ex_fuel_cost": ex_fuel_cost, "total_cost": total_cost,
        "rask": rask, "cask": cask, "pask": pask,
        "monthly_profit": monthly_profit,
        "annual_profit": annual_profit, "annual_revenue": annual_revenue,
        "annual_cost": annual_cost, "annual_ask": annual_ask,
        "annual_rask": annual_rask, "annual_cask": annual_cask,
        "annual_pask": annual_pask, "belf": belf,
    }