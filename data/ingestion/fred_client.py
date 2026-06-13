"""
fred_client.py
──────────────
Client for Federal Reserve Economic Data (FRED) API.

Pulls:
- Brent crude oil spot prices (Europe Brent Spot, DCOILBRENTEU)
- USD/INR exchange rate (optional, for ISC route economics)

API docs: https://fred.stlouisfed.org/docs/api/fred/
Registration: https://fredaccount.stlouisfed.org/apikey

Free tier: 120 requests/minute. Plenty for our use.
"""

import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from data.ingestion.cache import get_cached, set_cache


load_dotenv()
FRED_API_KEY = os.getenv("FRED_API_KEY")
FRED_BASE_URL = "https://api.stlouisfed.org/fred"


class FREDError(Exception):
    """Raised when FRED API call fails."""
    pass


def _check_api_key():
    if not FRED_API_KEY or FRED_API_KEY == "your_fred_key_here":
        raise FREDError(
            "FRED_API_KEY not set. Register at https://fredaccount.stlouisfed.org/apikey "
            "and add to .env file."
        )


def fetch_brent_crude(months_back: int = 24, use_cache: bool = True) -> dict:
    """
    Fetch monthly Brent crude spot price (USD/barrel).
    
    Series ID: DCOILBRENTEU (daily, USD/barrel) — we aggregate to monthly.
    
    Returns
    -------
    dict with keys: 'dates', 'prices_usd_per_barrel', 'latest_price',
                    'mean_price', 'volatility', 'source'
    """
    cache_key = f"fred_brent_{months_back}m"

    if use_cache:
        cached = get_cached(cache_key, ttl_hours=24)
        if cached:
            return cached["data"]

    _check_api_key()

    end_date = datetime.now()
    start_date = end_date - timedelta(days=months_back * 31)

    url = f"{FRED_BASE_URL}/series/observations"
    params = {
        "series_id": "DCOILBRENTEU",
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "observation_start": start_date.strftime("%Y-%m-%d"),
        "observation_end": end_date.strftime("%Y-%m-%d"),
        "frequency": "m",  # Monthly aggregation
        "aggregation_method": "avg",
    }

    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as e:
        raise FREDError(f"FRED API request failed: {e}")

    if "observations" not in payload:
        raise FREDError(f"Unexpected FRED response: {payload}")

    observations = payload["observations"]
    if not observations:
        raise FREDError("FRED returned no observations.")

    # Filter out missing values (FRED uses '.')
    valid = [obs for obs in observations if obs["value"] != "."]
    dates = [obs["date"] for obs in valid]
    prices = [float(obs["value"]) for obs in valid]

    # Compute volatility (monthly std dev of returns)
    import math
    returns = [(prices[i] / prices[i-1] - 1) for i in range(1, len(prices))]
    mean_ret = sum(returns) / len(returns) if returns else 0
    variance = sum((r - mean_ret) ** 2 for r in returns) / len(returns) if returns else 0
    monthly_vol = math.sqrt(variance) if variance > 0 else 0
    annualised_vol = monthly_vol * math.sqrt(12)

    result = {
        "dates": dates,
        "prices_usd_per_barrel": prices,
        "latest_price": round(prices[-1], 2),
        "latest_date": dates[-1],
        "mean_price": round(sum(prices) / len(prices), 2),
        "min_price": round(min(prices), 2),
        "max_price": round(max(prices), 2),
        "monthly_volatility": round(monthly_vol, 4),
        "annualised_volatility": round(annualised_vol, 4),
        "n_observations": len(prices),
        "source": "FRED Brent Crude Europe Spot Price",
        "series_id": "DCOILBRENTEU",
    }

    set_cache(cache_key, result)
    return result


def fetch_brent_with_fallback(fallback_price: float = 80.0, **kwargs) -> dict:
    """Fetch Brent with graceful fallback."""
    try:
        result = fetch_brent_crude(**kwargs)
        result["is_live"] = True
        return result
    except FREDError as e:
        print(f"  ⚠ FRED fetch failed, using fallback: {e}")
        return {
            "dates": [],
            "prices_usd_per_barrel": [fallback_price],
            "latest_price": fallback_price,
            "latest_date": "FALLBACK",
            "mean_price": fallback_price,
            "min_price": fallback_price,
            "max_price": fallback_price,
            "monthly_volatility": 0.08,
            "annualised_volatility": 0.28,
            "n_observations": 0,
            "source": "FALLBACK (hardcoded)",
            "is_live": False,
        }