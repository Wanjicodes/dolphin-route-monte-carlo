"""
shock_generator.py
──────────────────
Module 1: ShockPack — correlated stochastic variable generation.

All randomness in the simulation originates here.
The impact model (Module 2) is purely deterministic given a ShockPack.

Approach:
- Cholesky decomposition on 5-variable correlation matrix
- Load factor: Beta distribution (bounded [0,1])
- Yield: Log-normal
- Fuel price: Ornstein-Uhlenbeck mean-reverting process
- Competitive index: Normal (pressure index)
- Demand shock: Beta (India macro growth proxy)
- Discrete event shocks: Bernoulli draws (geopolitical, regulatory, AOG)
"""

import numpy as np
from scipy.stats import beta as beta_dist, norm
from data.assumptions import SIMULATION, CORRELATIONS, COSTS, REVENUE, SCENARIOS, OPERATIONS


def _cholesky_factor(corr_matrix):
    """Compute Cholesky factor L such that L @ L.T = Sigma."""
    Sigma = np.array(corr_matrix)
    eigvals = np.linalg.eigvalsh(Sigma)
    if eigvals.min() < 0:
        Sigma += (-eigvals.min() + 1e-8) * np.eye(len(Sigma))
    return np.linalg.cholesky(Sigma)


def _ou_process(n_paths, n_steps, mu, theta, sigma, x0, rng, correlated_noise=None):
    """
    Ornstein-Uhlenbeck mean-reverting process for fuel prices.
    dX = theta*(mu - X)*dt + sigma*dW
    Returns shape (n_paths, n_steps)
    """
    dt = 1 / 12
    X = np.zeros((n_paths, n_steps))
    X[:, 0] = x0
    for t in range(1, n_steps):
        dW = correlated_noise[:, t] if correlated_noise is not None else rng.standard_normal(n_paths)
        X[:, t] = (
            X[:, t - 1]
            + theta * (mu - X[:, t - 1]) * dt
            + sigma * np.sqrt(dt) * dW
        )
    return np.clip(X, 40, 200)


class ShockPack:
    """A versioned, seeded set of correlated futures for the DXB-BOM route."""

    VERSION = "1.0.0"

    def __init__(self, scenario_name="base"):
        self.scenario_name = scenario_name
        self.scenario = SCENARIOS[scenario_name]
        self.n_paths = SIMULATION["n_paths"]
        self.n_months = SIMULATION["n_months"]
        self.seed = SIMULATION["seed"]
        self.rng = np.random.default_rng(self.seed)
        self._generate()

    def _generate(self):
        n, m = self.n_paths, self.n_months
        sc = self.scenario

        # Step 1: Correlated standard normals via Cholesky
        L = _cholesky_factor(CORRELATIONS["matrix"])
        Z_raw = self.rng.standard_normal((n, 5, m))
        corr_Z = np.einsum("ij,kjm->kim", L, Z_raw)

        # Step 2: Load Factor- Beta distribution
        base_lf = REVENUE["base_load_factor"] + sc["load_factor_delta"]
        base_lf = np.clip(base_lf, 0.30, 0.98)
        alpha_lf = base_lf * 9.0
        beta_lf_param = (1 - base_lf) * 9.0
        u_lf = norm.cdf(corr_Z[:, 0, :])
        self.load_factor = beta_dist.ppf(u_lf, alpha_lf, beta_lf_param)
        self.load_factor = np.clip(self.load_factor, 0.20, 1.0)

        # Step 3: Yield- Log-normal
        blended_yield_base = (
            REVENUE["yield_economy_usd_per_rpk"] * REVENUE["cabin_mix_economy"]
            + REVENUE["yield_business_usd_per_rpk"] * REVENUE["cabin_mix_business"]
            + REVENUE["yield_business_usd_per_rpk"] * 1.8 * REVENUE["cabin_mix_first"]
        ) * (1 + sc["yield_delta"])
        sigma_yield = 0.08
        mu_yield = np.log(blended_yield_base) - 0.5 * sigma_yield**2
        u_yield = norm.cdf(corr_Z[:, 1, :])
        self.yield_per_rpk = np.exp(mu_yield + sigma_yield * norm.ppf(np.clip(u_yield, 1e-6, 1-1e-6)))
        self.yield_per_rpk = np.clip(self.yield_per_rpk, 0.030, 0.400)

        # Step 4: Fuel Price- Ornstein-Uhlenbeck
        base_fuel = COSTS["jet_fuel_price_usd_per_barrel"] + sc["fuel_price_delta"]
        self.fuel_price = _ou_process(
            n_paths=n, n_steps=m,
            mu=base_fuel, theta=2.5, sigma=12.0, x0=base_fuel,
            rng=self.rng,
            correlated_noise=corr_Z[:, 2, :],
        )

        # Step 5: Competitive Index
        comp_base = 0.45 + (0.15 if self.scenario_name == "competitive_squeeze" else 0.0)
        self.competitive_index = np.clip(
            comp_base + 0.12 * corr_Z[:, 3, :], 0.0, 1.0
        )

        # Step 6: Demand Index
        u_demand = norm.cdf(corr_Z[:, 4, :])
        self.demand_index = beta_dist.ppf(u_demand, 6.5, 3.5)

        # Step 7: Discrete Event Shocks
        p_geo_monthly = sc["probability"] / 12 if self.scenario_name == "geopolitical_shock" else 0.08 / 12
        self.geo_shock = self.rng.random((n, m)) < p_geo_monthly

        p_reg = sc["probability"] if self.scenario_name == "regulatory_constraint" else 0.06
        self.reg_shock = self.rng.random(n) < p_reg

        self.aog_shock = self.rng.random((n, m)) < OPERATIONS["aog_probability_per_month"]

        self.ask_scale = 1.0 + sc["ask_delta"]


def generate_all_scenarios():
    """Generate ShockPacks for all defined scenarios."""
    return {name: ShockPack(scenario_name=name) for name in SCENARIOS}