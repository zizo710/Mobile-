"""Supply shock -> price model and futures valuation.

Annual, by crop year H (Oct H-1 .. Sep H), in real (CPI-deflated) US$:

    dlog P_H = a + b1*S_H + b2*S_(H-1) + g*log P_(H-1) [+ d*ONI_(H-1)] + e

S    = West African production deviation from trend (log points)
logP = lagged real price level (mean reversion: high prices ration demand and
       pull in supply; g < 0)
ONI  = optional ENSO term (Jun-Oct before the crop year) - the one weather signal
       that is known ahead of the harvest and has a detectable price footprint

Fair value for the coming crop year = model expectation given the nowcast S.
The futures strip covering that crop year is then compared with it.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import norm

from .data import real_factor

BASE_COLS = ["S", "S_lag", "lp_lag"]


def crop_year_price(monthly: pd.Series, min_months: int = 9) -> pd.Series:
    """Average nominal price per crop year H (Oct H-1 .. Sep H)."""
    h = monthly.index.year + (monthly.index.month >= 10)
    g = monthly.groupby(h)
    return g.mean()[g.count() >= min_months]


@dataclass
class Valuation:
    target_year: int
    fair_value: float  # nominal US$/t, median
    band68: tuple[float, float]
    band90: tuple[float, float]
    futures_strip: float
    mispricing_pct: float  # futures vs fair value
    z: float
    prob_fair_below_futures: float
    verdict: str
    sigma: float  # log-point forecast s.d.
    ols: object
    frame: pd.DataFrame
    prev_price: float
    components: dict[str, float]


def _frame(price_cy: pd.Series, shock: pd.Series, base_year: int, oni: pd.Series) -> pd.DataFrame:
    yrs = sorted(set(price_cy.index) | set(shock.index))
    f = pd.DataFrame(index=yrs)
    f["nominal"] = price_cy
    f["lp"] = np.log(f["nominal"] * real_factor(f.index, base_year))
    f["dlp"] = f["lp"].diff()
    f["S"] = shock
    f["S_lag"] = f["S"].shift(1)
    f["lp_lag"] = f["lp"].shift(1)
    f["oni"] = oni
    return f


def value(price_cy: pd.Series, shock_hist: pd.Series, shock_fcst: pd.Series,
          strip: float, target_year: int, shock_sd: float, oni: pd.Series,
          with_enso: bool = False) -> Valuation:
    """shock_hist: observed W. Africa production cycle (fits the model).
    shock_fcst: weather-model shocks for years after the FAOSTAT sample.
    shock_sd:   s.d. of the weather model's error on the aggregate shock."""
    cols = BASE_COLS + (["oni"] if with_enso else [])
    fit_df = _frame(price_cy, shock_hist, target_year, oni).dropna(subset=["dlp"] + cols)
    ols = sm.OLS(fit_df["dlp"], sm.add_constant(fit_df[cols])).fit()

    full = _frame(price_cy, pd.concat([shock_hist, shock_fcst[~shock_fcst.index.isin(shock_hist.index)]]),
                  target_year, oni)
    row = full.loc[target_year, cols]
    if row.isna().any():
        raise RuntimeError(f"cannot value {target_year}: missing inputs {row[row.isna()].index.tolist()}")
    b = ols.params
    dlp = float(b["const"] + (b[cols] * row).sum())
    prev_real = float(np.exp(full.loc[target_year - 1, "lp"]))  # already in target-year $
    fair = prev_real * np.exp(dlp)
    # forecast uncertainty: price-equation residual + uncertainty in the nowcast shocks
    sigma = float(np.sqrt(ols.mse_resid + (b["S"] ** 2 + b["S_lag"] ** 2) * shock_sd**2))
    z = float(np.log(strip / fair) / sigma)
    band = lambda q: (fair * np.exp(-q * sigma), fair * np.exp(q * sigma))  # noqa: E731
    if z > 1:
        verdict = "OVERVALUED"
    elif z > 0.5:
        verdict = "modestly overvalued"
    elif z < -1:
        verdict = "UNDERVALUED"
    elif z < -0.5:
        verdict = "modestly undervalued"
    else:
        verdict = "roughly fairly valued"
    comps = {"drift": float(b["const"]), "current-crop shock": float(b["S"] * row["S"]),
             "previous-crop shock": float(b["S_lag"] * row["S_lag"]),
             "mean reversion": float(b["lp_lag"] * row["lp_lag"])}
    comps["drift"] += comps.pop("mean reversion")  # constant + level term = pull to long-run mean
    comps["mean reversion"] = comps.pop("drift")
    if with_enso:
        comps["ENSO"] = float(b["oni"] * row["oni"])
    return Valuation(target_year, float(fair), band(1.0), band(1.645), strip,
                     float(strip / fair - 1), z, float(norm.cdf(z)), verdict, sigma, ols, full,
                     prev_real, comps)
