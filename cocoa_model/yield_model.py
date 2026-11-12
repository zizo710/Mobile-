"""Weather -> cocoa production model.

Target: each country's production "cycle" = log(production) minus a smooth HP trend,
i.e. the % deviation from trend that tree stock / acreage cannot explain.
Features: standardised seasonal weather anomalies around the crop calendar + ENSO.
Estimator: pooled ridge regression, alpha chosen and skill measured by
leave-one-year-out cross-validation (a whole harvest year is held out across countries).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from statsmodels.tsa.filters.hp_filter import hpfilter

from .config import FEATURES, ONI_MONTHS, REGIONS, WINDOWS

HP_LAMBDA = 100  # standard for annual data
ALPHAS = [1, 3, 10, 30, 100, 300, 1000]


def production_cycle(prod: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (cycle, trend) in logs per country."""
    cyc, trend = {}, {}
    for c in prod:
        s = np.log(prod[c].dropna())
        cyc[c], trend[c] = hpfilter(s, lamb=HP_LAMBDA)
    return pd.DataFrame(cyc), pd.DataFrame(trend)


def build_features(wx: pd.DataFrame, oni: pd.Series, years: list[int]) -> pd.DataFrame:
    """Feature matrix indexed by (country, harvest year H). Windows that are not yet
    (fully) observed are NaN here; the caller decides how to fill them."""
    windows = {n: months for n, months, _ in WINDOWS}
    enso = enso_by_harvest_year(oni, years)
    rows = []
    for country in REGIONS:
        w = wx[wx["country"] == country].set_index(["year", "month"])
        raw = {}
        for name, var, win, _sq in FEATURES:
            if (var, win) in raw:
                continue
            vals = []
            for h in years:
                keys = [(h + dy, m) for dy, m in windows[win]]
                if all(k in w.index for k in keys):
                    x = w.loc[keys, var]
                    vals.append(x.sum() if var == "rain" else x.mean())
                else:
                    vals.append(np.nan)
            v = pd.Series(vals, index=years, dtype=float)
            raw[(var, win)] = (v - v.mean()) / v.std()  # z-score vs the country's own history
        for h in years:
            row = {"country": country, "year": h}
            for name, var, win, sq in FEATURES:
                z = raw[(var, win)][h]
                row[name] = z**2 - 1 if sq else z  # centred square: penalises both extremes
            row["oni"] = enso.get(h, np.nan)
            rows.append(row)
    return pd.DataFrame(rows).set_index(["country", "year"])


def _ridge(X: np.ndarray, y: np.ndarray, alpha: float) -> np.ndarray:
    return np.linalg.solve(X.T @ X + alpha * np.eye(X.shape[1]), X.T @ y)


@dataclass
class YieldModel:
    coef: pd.Series
    alpha: float
    cv_r2: float
    cv_corr: float
    cv_corr_by_country: pd.Series
    cv_pred: pd.Series  # out-of-sample predictions, indexed (country, year)
    resid_sd: float
    correlations: pd.DataFrame  # feature x country Pearson r with the production cycle
    n_obs: int

    def predict(self, X: pd.DataFrame) -> pd.Series:
        return X[self.coef.index].fillna(0.0) @ self.coef  # unknown window -> climatology


def fit(feats: pd.DataFrame, cycle: pd.DataFrame) -> YieldModel:
    y = cycle.stack().rename("cycle")
    y.index.names = ["year", "country"]
    df = feats.join(y.reorder_levels(["country", "year"]), how="inner").dropna()
    X, t = df.drop(columns="cycle"), df["cycle"]
    years = df.index.get_level_values("year").to_numpy()

    def loyo(alpha: float) -> np.ndarray:
        pred = np.empty(len(t))
        for yr in np.unique(years):
            te = years == yr
            b = _ridge(X.values[~te], t.values[~te], alpha)
            pred[te] = X.values[te] @ b
        return pred

    scores = {a: 1 - np.sum((t.values - loyo(a)) ** 2) / np.sum(t.values**2) for a in ALPHAS}
    alpha = max(scores, key=scores.get)
    pred = pd.Series(loyo(alpha), index=t.index)
    coef = pd.Series(_ridge(X.values, t.values, alpha), index=X.columns)
    by_c = pd.Series({c: np.corrcoef(pred[c], t[c])[0, 1] for c in REGIONS})
    corr = pd.DataFrame({c: X.loc[c].corrwith(t[c]) for c in REGIONS})
    corr["Pooled"] = X.corrwith(t)
    return YieldModel(coef, alpha, scores[alpha], float(np.corrcoef(pred, t)[0, 1]), by_c, pred,
                      float(np.std(t.values - pred.values)), corr, len(t))


def enso_by_harvest_year(oni: pd.Series, years: list[int]) -> pd.Series:
    """Mean ONI over Jun-Oct preceding each harvest year. The latest seasons lag by a
    month or two, so a year counts once at least 3 of the 5 values are published."""
    out = {}
    for h in years:
        v = oni.reindex([(h + dy, m) for dy, m in ONI_MONTHS]).dropna()
        out[h] = v.mean() if len(v) >= 3 else np.nan
    return pd.Series(out)


def aggregate_shock(country_shock: pd.DataFrame, trend: pd.DataFrame) -> pd.Series:
    """Trend-production-weighted West African shock (log points) per year.
    Weights for years beyond the trend sample use the last available trend level."""
    w = np.exp(trend).reindex(trend.index.union(country_shock.index)).ffill().loc[country_shock.index]
    w = w.div(w.sum(axis=1), axis=0)
    return (country_shock * w[country_shock.columns]).sum(axis=1)
