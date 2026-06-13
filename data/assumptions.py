"""
DXB-BOM Route Assumptions
Calibrated to Emirates FY2024-25 public financials and ISC corridor intelligence.

Sources:
- Emirates Group Annual Report 2024-25 (AED 127.9B revenue, 31% fuel share, 80% PSF)
- Competitor intelligence: Emirates 35% ISC market share, load factor ~82%
- Route: Dubai (DXB) → Mumbai (BOM), 2,200km, Boeing 777-300ER

Live data integration:
- Fuel prices: optionally overridden by EIA + FRED live data
- See: data/ingestion/live_assumptions.py
"""

# ── LIVE DATA OVERRIDE ────────────────────────────────────────────────────────
# Set to True to pull live fuel data from EIA + FRED APIs.
# Set to False for reproducible runs with hardcoded values.
USE_LIVE_DATA = True

# ── ROUTE CONFIGURATION ───────────────────────────────────────────────────────
ROUTE = {
    "origin": "DXB",
    "destination": "BOM",
    "distance_km": 2_200,
    "frequency_daily": 2,
    "aircraft": "Boeing 777-300ER",
    "seats_economy": 304,
    "seats_business": 42,
    "seats_first": 8,
    "seats_total": 354,
    "operating_days": 365,
}

# ── REVENUE CALIBRATION ───────────────────────────────────────────────────────
REVENUE = {
    "base_load_factor": 0.82,
    "yield_economy_usd_per_rpk": 0.072,
    "yield_business_usd_per_rpk": 0.290,
    "cabin_mix_economy": 0.78,
    "cabin_mix_business": 0.18,
    "cabin_mix_first": 0.04,
    "cargo_revenue_pct_of_passenger": 0.14,
    "ancillary_revenue_per_pax_usd": 28,
    "no_show_rate_base": 0.07,
}

# ── COST CALIBRATION ─────────────────────────────────────────────────────────
COSTS = {
    "cask_ex_fuel_usd": 0.047,
    "jet_fuel_price_usd_per_barrel": 95,
    "fuel_burn_kg_per_km": 8.2,
    "fuel_density_liters_per_kg": 1.25,
    "barrels_per_liter": 0.00629,
    "hedge_ratio": 0.35,
    "hedge_price_usd_per_barrel": 88,
}

# ── OPERATIONAL PARAMETERS ───────────────────────────────────────────────────
OPERATIONS = {
    "aog_probability_per_month": 0.025,
    "delay_cost_usd_per_hour": 8_500,
    "overbooking_rate": 0.03,
    "compensation_cost_per_denied_pax_usd": 850,
}

# ── SIMULATION PARAMETERS ────────────────────────────────────────────────────
SIMULATION = {
    "n_paths": 10_000,
    "n_months": 12,
    "seed": 42,
    "currency": "USD",
}

# ── CORRELATION MATRIX ───────────────────────────────────────────────────────
CORRELATIONS = {
    "variables": ["load_factor", "yield", "fuel_price", "competitive_index", "demand_shock"],
    "matrix": [
        [ 1.00,  -0.40,  -0.20,  -0.45,   0.65],
        [-0.40,   1.00,   0.35,  -0.30,   0.40],
        [-0.20,   0.35,   1.00,  -0.10,  -0.15],
        [-0.45,  -0.30,  -0.10,   1.00,  -0.50],
        [ 0.65,   0.40,  -0.15,  -0.50,   1.00],
    ]
}

# ── SCENARIO DEFINITIONS ─────────────────────────────────────────────────────
SCENARIOS = {
    "base": {
        "label": "Base Case",
        "description": "Central assumptions, India GDP growth continues",
        "load_factor_delta": 0.00,
        "yield_delta": 0.00,
        "fuel_price_delta": 0,
        "ask_delta": 0.00,
        "probability": 0.47,
        "duration_months": 12,
    },
    "competitive_squeeze": {
        "label": "Competitive Squeeze",
        "description": "IndiGo/Air India ISC expansion. Priority 1 risk.",
        "load_factor_delta": -0.07,
        "yield_delta": -0.12,
        "fuel_price_delta": 0,
        "ask_delta": 0.00,
        "probability": 0.35,
        "duration_months": 12,
    },
    "macro_stress": {
        "label": "Macro Stress",
        "description": "UAE/India economic slowdown, fuel spike. Priority 2.",
        "load_factor_delta": -0.05,
        "yield_delta": -0.08,
        "fuel_price_delta": +25,
        "ask_delta": 0.00,
        "probability": 0.20,
        "duration_months": 6,
    },
    "geopolitical_shock": {
        "label": "Geopolitical Shock",
        "description": "India-Pakistan tensions, Gulf airspace disruption. Priority 1.",
        "load_factor_delta": -0.22,
        "yield_delta": -0.05,
        "fuel_price_delta": 0,
        "ask_delta": -0.10,
        "probability": 0.08,
        "duration_months": 2,
    },
    "regulatory_constraint": {
        "label": "Regulatory Constraint",
        "description": "Indian bilateral policy caps UAE carrier frequencies. Priority 3.",
        "load_factor_delta": 0.00,
        "yield_delta": 0.00,
        "fuel_price_delta": 0,
        "ask_delta": -0.15,
        "probability": 0.06,
        "duration_months": 6,
    },
    "combined_adverse": {
        "label": "Combined Adverse",
        "description": "Geopolitical + competitive + fuel shock simultaneously. Tail risk.",
        "load_factor_delta": -0.15,
        "yield_delta": -0.15,
        "fuel_price_delta": +20,
        "ask_delta": -0.10,
        "probability": 0.04,
        "duration_months": 6,
    },
}