"""
eia_client.py
─────────────
Client for U.S. Energy Information Administration (EIA) Open Data API.

Pulls:
- Jet fuel spot prices (US Gulf Coast Kerosene-Type Jet Fuel)
- Brent crude spot prices (cross-check vs FRED)

API docs: https://www.eia.gov/opendata/documentation.php
Registration: https://www.eia.gov/opendata/register.php

Free tier: 5,000 requests/hour. Way more than we need.
"""

import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from data.ingestion.cache import get_cached, set_cache


load_dotenv()
EIA_API_KEY = os.getenv("EIA_API_KEY")
EIA_BASE_URL = "https://api.eia.gov/v2"


class EIAError(Exception):
    """Raised when EIA API call fails."""
    pass


def _check_api_key():
    """Verify API key is set."""
    if not EIA_API_KEY or EIA_API_KEY == "your_eia_key_here":
        raise EIAError(
            "EIA_API_KEY not set. Register at https://www.eia.gov/opendata/register.php "
            "and add to .env file."
        )


def fetch_jet_fuel_prices(months_back: int = 24, use_cache: bool = True) -> dict:
    """
    Fetch monthly US Gulf Coast Kerosene-Type Jet Fuel spot prices.
    
    Series ID: PET.EER_EPJK_PF4_RGC_DPG.M (monthly, USD/gallon)
    We convert to USD/barrel (1 barrel = 42 gallons).
    
    Parameters
    ----------
    months_back : int — how many months of history
    use_cache : bool — use 24h cache if available
    
    Returns
    -------
    dict with keys: 'dates' (list), 'prices_usd_per_barrel' (list),
                    'latest_price', 'mean_price', 'source'
    """
    cache_key = f"eia_jet_fuel_{months_back}m"

    if use_cache:
        cached = get_cached(cache_key, ttl_hours=24)
        if cached:
            return cached["data"]

    _check_api_key()

    end_date = datetime.now()
    start_date = end_date - timedelta(days=months_back * 31)

    url = f"{EIA_BASE_URL}/petroleum/pri/spt/data/"
    params = {
        "api_key": EIA_API_KEY,
        "frequency": "monthly",
        "data[0]": "value",
        "facets[series][]": "EER_EPJK_PF4_RGC_DPG",
        "start": start_date.strftime("%Y-%m"),
        "end": end_date.strftime("%Y-%m"),
        "sort[0][column]": "period",
        "sort[0][direction]": "asc",
    }

    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as e:
        raise EIAError(f"EIA API request failed: {e}")

    if "response" not in payload or "data" not in payload["response"]:
        raise EIAError(f"Unexpected EIA response structure: {payload}")

    raw_data = payload["response"]["data"]
    if not raw_data:
        raise EIAError("EIA returned no data — check series ID or date range.")

    # Convert USD/gallon → USD/barrel
    dates = [row["period"] for row in raw_data]
    prices_gallon = [float(row["value"]) for row in raw_data]
    prices_barrel = [round(p * 42, 2) for p in prices_gallon]

    result = {
        "dates": dates,
        "prices_usd_per_barrel": prices_barrel,
        "latest_price": prices_barrel[-1],
        "latest_date": dates[-1],
        "mean_price": round(sum(prices_barrel) / len(prices_barrel), 2),
        "min_price": min(prices_barrel),
        "max_price": max(prices_barrel),
        "n_observations": len(prices_barrel),
        "source": "EIA US Gulf Coast Kerosene-Type Jet Fuel Spot Price",
        "series_id": "EER_EPJK_PF4_RGC_DPG",
    }

    set_cache(cache_key, result)
    return result


def fetch_with_fallback(fallback_price: float = 95.0, **kwargs) -> dict:
    """Fetch jet fuel prices with graceful fallback if API fails."""
    try:
        result = fetch_jet_fuel_prices(**kwargs)
        result["is_live"] = True
        return result
    except EIAError as e:
        print(f"  ⚠ EIA fetch failed, using fallback: {e}")
        return {
            "dates": [],
            "prices_usd_per_barrel": [fallback_price],
            "latest_price": fallback_price,
            "latest_date": "FALLBACK",
            "mean_price": fallback_price,
            "min_price": fallback_price,
            "max_price": fallback_price,
            "n_observations": 0,
            "source": "FALLBACK (hardcoded)",
            "is_live": False,
        }