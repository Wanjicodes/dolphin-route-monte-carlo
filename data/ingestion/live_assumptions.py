"""
live_assumptions.py
───────────────────
Bridges live API data into the model's assumption dictionaries.

Pattern:
- Pulls live data on demand
- Falls back gracefully to hardcoded values
- Returns a dict matching the COSTS structure in assumptions.py
- Logs source clearly so simulation output shows what was used
"""

from data.ingestion.eia_client import fetch_with_fallback as fetch_jet_fuel
from data.ingestion.fred_client import fetch_brent_with_fallback as fetch_brent


def get_live_fuel_assumptions(months_back: int = 24, verbose: bool = True) -> dict:
    """
    Pull live fuel data and return assumptions dict ready for simulation.
    
    Returns
    -------
    dict with:
      - jet_fuel_price_usd_per_barrel : float (latest)
      - jet_fuel_mean_24m : float
      - brent_price_usd_per_barrel : float (latest)
      - brent_mean_24m : float
      - brent_annualised_volatility : float
      - ou_sigma_calibrated : float (for OU process)
      - data_sources : dict
      - is_live : bool
    """
    if verbose:
        print("  Fetching live fuel data...")

    jet_fuel = fetch_jet_fuel(months_back=months_back)
    brent = fetch_brent(months_back=months_back)

    # Calibrate OU sigma from observed Brent volatility
    # Convert annualised vol to dollar terms at current price level
    ou_sigma = brent["latest_price"] * brent["annualised_volatility"]

    result = {
        "jet_fuel_price_usd_per_barrel": jet_fuel["latest_price"],
        "jet_fuel_mean_24m": jet_fuel["mean_price"],
        "brent_price_usd_per_barrel": brent["latest_price"],
        "brent_mean_24m": brent["mean_price"],
        "brent_min_24m": brent["min_price"],
        "brent_max_24m": brent["max_price"],
        "brent_annualised_volatility": brent["annualised_volatility"],
        "ou_sigma_calibrated": round(ou_sigma, 2),
        "crack_spread": round(jet_fuel["latest_price"] - brent["latest_price"], 2),
        "data_sources": {
            "jet_fuel": jet_fuel["source"],
            "brent": brent["source"],
            "jet_fuel_latest_date": jet_fuel["latest_date"],
            "brent_latest_date": brent["latest_date"],
        },
        "is_live": jet_fuel.get("is_live", False) and brent.get("is_live", False),
    }

    if verbose:
        live_tag = "LIVE" if result["is_live"] else "FALLBACK"
        print(f"  [{live_tag}] Jet Fuel: ${result['jet_fuel_price_usd_per_barrel']:.2f}/bbl "
              f"(latest: {jet_fuel['latest_date']})")
        print(f"  [{live_tag}] Brent:    ${result['brent_price_usd_per_barrel']:.2f}/bbl "
              f"(24m vol: {result['brent_annualised_volatility']*100:.1f}%)")
        print(f"  Crack spread (jet - brent): ${result['crack_spread']:.2f}/bbl")
        print(f"  OU sigma calibrated to: ${result['ou_sigma_calibrated']:.2f}")

    return result


if __name__ == "__main__":
    # Standalone test
    data = get_live_fuel_assumptions()
    print("\nFull payload:")
    import json
    print(json.dumps(data, indent=2))