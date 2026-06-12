"""
run_simulation.py
─────────────────
Orchestrator: runs the full DXB-BOM Monte Carlo simulation pipeline.
"""

import sys
import json
import time
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from data.assumptions import SIMULATION, ROUTE, SCENARIOS
from engine.shock_generator import ShockPack
from engine.impact_model import run_impact_model
from engine.risk_metrics import compute_all_metrics, scenario_comparison, fuel_sensitivity
from ml.demand_forecast import generate_forecast_with_uncertainty, get_competitive_baseline_comparison


def run():
    print("=" * 65)
    print("  DXB-BOM ROUTE PROFITABILITY — MONTE CARLO SIMULATION ENGINE")
    print(f"  Route: {ROUTE['origin']} -> {ROUTE['destination']} | "
          f"{ROUTE['aircraft']} | {ROUTE['frequency_daily']}x daily")
    print(f"  Paths: {SIMULATION['n_paths']:,} | Seed: {SIMULATION['seed']}")
    print("=" * 65)

    t0 = time.time()

    print("\n[1/4] Running ML demand forecast (seasonal decomposition)...")
    forecast = generate_forecast_with_uncertainty(
        base_lf=0.82, n_months=12, n_simulations=5_000, seed=SIMULATION["seed"]
    )
    print(f"      Baseline LF range: {forecast['baseline'].min():.3f} - {forecast['baseline'].max():.3f}")
    print(f"      Peak month: {forecast['month_labels'][int(forecast['baseline'].argmax())]} "
          f"({forecast['baseline'].max():.3f})")

    print(f"\n[2/4] Running impact model ({len(SCENARIOS)} scenarios)...")
    all_results = {}
    all_metrics = {}
    for scenario_name in SCENARIOS:
        sc_label = SCENARIOS[scenario_name]["label"]
        shock = ShockPack(scenario_name=scenario_name)
        results = run_impact_model(shock)
        metrics = compute_all_metrics(results)
        all_results[scenario_name] = results
        all_metrics[scenario_name] = metrics
        mean_profit = metrics["mean_annual_profit_usd"]
        prob_loss = metrics["prob_annual_loss"]
        print(f"      [{sc_label:28s}] Mean: ${mean_profit/1e6:7.2f}M | P(loss): {prob_loss:.1%}")

    print("\n[3/4] Computing risk metrics and scenario comparison...")
    comparison = scenario_comparison(all_results)
    fuel_sens = fuel_sensitivity(all_results["base"], all_results["macro_stress"])
    competitors = get_competitive_baseline_comparison()

    base = all_metrics["base"]
    print(f"\n  -- BASE CASE SUMMARY ----------------------------------------")
    print(f"  Mean Annual Profit:    ${base['mean_annual_profit_usd']/1e6:.2f}M")
    print(f"  P5/P50/P95:            ${base['profit_percentiles']['P5']/1e6:.2f}M / "
          f"${base['profit_percentiles']['P50']/1e6:.2f}M / "
          f"${base['profit_percentiles']['P95']/1e6:.2f}M")
    print(f"  VaR 95%:               ${base['var_95_usd']/1e6:.2f}M loss")
    print(f"  Mean Load Factor:      {base['mean_load_factor']:.1%}")
    print(f"  Mean BELF:             {base['mean_belf']:.1%}")
    print(f"  Mean RASK:             ${base['mean_rask']:.4f}/ASK")
    print(f"  Mean CASK:             ${base['mean_cask']:.4f}/ASK")
    print(f"  Fuel sensitivity:      ${fuel_sens/1e6:.2f}M per $10/bbl Brent")

    print(f"\n  -- SCENARIO COMPARISON --------------------------------------")
    print(f"  {'Scenario':<28} {'Mean $M':>9} {'P5 $M':>9} {'P(loss)':>9} {'VaR95 $M':>10}")
    print(f"  {'-'*28} {'-'*9} {'-'*9} {'-'*9} {'-'*10}")
    for name, c in comparison.items():
        print(f"  {SCENARIOS[name]['label']:<28} "
              f"{c['mean_profit']/1e6:>9.2f} "
              f"{c['P5_profit']/1e6:>9.2f} "
              f"{c['prob_loss']:>9.1%} "
              f"{c['var_95']/1e6:>10.2f}")

    print("\n[4/4] Exporting results to JSON...")

    def _to_serialisable(obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.floating, np.float32, np.float64)):
            return float(obj)
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, dict):
            return {k: _to_serialisable(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_to_serialisable(i) for i in obj]
        return obj

    export = {
        "meta": {
            "route": f"{ROUTE['origin']}-{ROUTE['destination']}",
            "aircraft": ROUTE["aircraft"],
            "n_paths": SIMULATION["n_paths"],
            "seed": SIMULATION["seed"],
            "n_months": SIMULATION["n_months"],
        },
        "forecast": {
            "baseline": forecast["baseline"].tolist(),
            "lower_95": forecast["lower_95"].tolist(),
            "upper_95": forecast["upper_95"].tolist(),
            "lower_80": forecast["lower_80"].tolist(),
            "upper_80": forecast["upper_80"].tolist(),
            "month_labels": forecast["month_labels"],
        },
        "metrics": _to_serialisable(all_metrics),
        "scenario_comparison": _to_serialisable(comparison),
        "fuel_sensitivity_per_10bbl": float(fuel_sens),
        "competitors": competitors,
    }

    out_path = Path(__file__).parent / "outputs" / "simulation_results.json"
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(export, f, indent=2)

    elapsed = time.time() - t0
    print(f"\n  Results saved -> {out_path}")
    print(f"  Total runtime: {elapsed:.1f}s")
    print("=" * 65)

    return export


if __name__ == "__main__":
    run()