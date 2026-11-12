"""Copper price model: which drivers forecast the 12-month change in the real price?

Monthly data. Target: log real price 12 months ahead minus today. Every predictor is
lagged so it was published by the decision date. Variables are chosen by forward
selection on *out-of-sample* error (expanding window, quarterly forecast origins); a
variable is kept only if it cuts squared error by at least MIN_GAIN.

The walk-forward run repeats that whole selection each January using only earlier data,
so its forecasts - and the backtests built on them - contain no hindsight in the choice
of variables or coefficients.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

H = 12  # forecast horizon, months
MIN_GAIN = 0.02
MAX_VARS = 4
FIRST_SEL = 1985  # first forecast origin used to judge variables
FIRST_TRADE = 2001

# name -> (label, group)
CANDIDATES = {
    "cli_g20": ("G20 leading indicator, level vs trend", "demand"),
    "dcli_g20": ("G20 leading indicator, 6-month change", "demand"),
    "cli_chn": ("China leading indicator, level vs trend", "demand"),
    "dcli_chn": ("China leading indicator, 6-month change", "demand"),
    "gdp_world": ("World GDP growth, latest published year", "demand"),
    "gdp_chn": ("China GDP growth, latest published year", "demand"),
    "ddxy12": ("US dollar index, 12-month change", "financial"),
    "dxy_gap": ("US dollar index vs its 10-year average", "financial"),
    "dy10": ("US 10-year yield, 12-month change", "financial"),
    "y10": ("US 10-year yield, level", "financial"),
    "spx12": ("S&P 500, 12-month return", "financial"),
    "vol12": ("Copper price volatility, 12 months", "financial"),
    "cu_gold": ("Copper-to-gold ratio vs its 10-year average", "relative value"),
    "cu_alu": ("Copper-to-aluminium ratio vs its 10-year average", "relative value"),
    "oil12": ("Oil price, 12-month change", "relative value"),
    "iron6": ("Iron ore price, 6-month change", "relative value"),
    "metals12": ("Zinc / nickel / aluminium, 12-month change", "relative value"),
    "gap10": ("Real copper price vs its 10-year average", "own price"),
    "gap5": ("Real copper price vs its 5-year average", "own price"),
    "mom12": ("Copper price, 12-month change", "own price"),
    "mine_growth": ("World mine output growth, latest published year", "supply"),
    "oni": ("ENSO (Chile / Peru weather disruption)", "supply"),
}
PLACEBO = {
    "sunspots": ("Sunspot number", "test"),
    "qbo": ("Quasi-biennial oscillation (stratospheric wind)", "test"),
    "cocoa12": ("Cocoa price, 12-month change", "test"),
}
LABELS = {k: v[0] for k, v in {**CANDIDATES, **PLACEBO}.items()}
REVISED = ["cli_g20", "dcli_g20", "cli_chn", "dcli_chn"]  # series that are revised after publication


def build_features(pk: pd.DataFrame, cpi: pd.Series, cli: pd.DataFrame, fin: pd.DataFrame,
                   gdp_w: pd.Series, gdp_c: pd.Series, mine: pd.Series, oni: pd.Series,
                   ci: pd.DataFrame) -> pd.DataFrame:
    """Monthly feature table. Row t holds what was known at the end of month t."""
    m = pk.index
    lg = lambda s: np.log(s)  # noqa: E731
    dev = lambda s, k=120: s - s.rolling(k).mean()  # noqa: E731
    lp = lg(pk["copper"] / cpi)
    f = pd.DataFrame(index=m)
    f["lp"] = lp
    f["y"] = lp.shift(-H) - lp
    c = cli.reindex(m)
    f["cli_g20"] = c["G20"].shift(2) - 100  # published about two months late
    f["dcli_g20"] = c["G20"].diff(6).shift(2)
    f["cli_chn"] = (c["CHN"].shift(2) - 100).fillna(0.0)  # starts 1992; neutral before
    f["dcli_chn"] = c["CHN"].diff(6).shift(2).fillna(0.0)
    annual = lambda s: pd.Series([s.get(p.year - (1 if p.month >= 7 else 2), np.nan) for p in m], index=m)  # noqa: E731
    f["gdp_world"] = annual(gdp_w).ffill()
    f["gdp_chn"] = annual(gdp_c).ffill()
    fm = fin.reindex(m)
    f["ddxy12"] = lg(fm["dxy"]).diff(12)
    f["dxy_gap"] = dev(lg(fm["dxy"]))
    f["dy10"] = fm["y10"].diff(12)
    f["y10"] = fm["y10"]
    f["spx12"] = lg(fm["spx"]).diff(12)
    f["vol12"] = lp.diff().rolling(12).std()
    f["cu_gold"] = dev(lg(pk["copper"] / pk["gold"]))
    f["cu_alu"] = dev(lg(pk["copper"] / pk["alu"]))
    f["oil12"] = lg(pk["oil"] / cpi).diff(12)
    f["iron6"] = lg(pk["iron"]).diff(6)
    f["metals12"] = (lg(pk["zinc"]) + lg(pk["nickel"]) + lg(pk["alu"])).diff(12) / 3
    f["gap10"] = dev(lp)
    f["gap5"] = dev(lp, 60)
    f["mom12"] = lp.diff(12)
    g = np.log(mine).diff()
    f["mine_growth"] = annual(g).fillna(g.mean())
    f["oni"] = pd.Series([oni.get((p.year, p.month), np.nan) for p in m], index=m).shift(2).ffill()
    for name in ("sunspots", "qbo"):
        s = pd.Series([ci[name].get((p.year, p.month), np.nan) for p in m], index=m).shift(1)
        f[name] = s.ffill().fillna(s.mean())
    f["cocoa12"] = lg(pk["cocoa"]).diff(12)
    return f


class Engine:
    """Fast expanding-window OLS via cumulative moment matrices."""

    def __init__(self, f: pd.DataFrame, pool: list[str]):
        d = f.dropna(subset=pool)
        self.index, self.pool = d.index, pool
        Z = np.column_stack([np.ones(len(d)), d[pool].values])
        y = d["y"].values
        ok = ~np.isnan(y)
        Zy = np.where(ok[:, None], Z, 0.0)
        self.Z, self.y = Z, y
        self.C = np.cumsum(np.einsum("ti,tj->tij", Zy, Zy), axis=0)
        self.D = np.cumsum(Zy * np.where(ok, y, 0.0)[:, None], axis=0)
        self.pos = {p: i for i, p in enumerate(d.index)}

    def coef(self, cols: list[int], t: int) -> np.ndarray:
        """OLS on rows whose 12-month outcome was known at row t (rows <= t - H)."""
        idx = [0] + [c + 1 for c in cols]
        k = t - H
        return np.linalg.solve(self.C[k][np.ix_(idx, idx)] + 1e-9 * np.eye(len(idx)), self.D[k][idx])

    def forecast(self, cols: list[int], t: int) -> float:
        idx = [0] + [c + 1 for c in cols]
        return float(self.Z[t, idx] @ self.coef(cols, t))

    def sse(self, cols: list[int], origins: np.ndarray) -> float:
        return float(sum((self.y[t] - self.forecast(cols, t)) ** 2 for t in origins))

    def select(self, origins: np.ndarray, allowed: list[int]) -> list[int]:
        cols: list[int] = []
        best = self.sse(cols, origins)
        while len(cols) < MAX_VARS:
            trial = {c: self.sse(cols + [c], origins) for c in allowed if c not in cols}
            c = min(trial, key=trial.get)
            if trial[c] > best * (1 - MIN_GAIN):
                break
            cols.append(c)
            best = trial[c]
        return cols


@dataclass
class WalkForward:
    pred: pd.Series  # forecast 12-month real log change, at each quarterly origin
    picks: pd.DataFrame  # year x variable: chosen that year?
    r2: float  # out-of-sample R² vs a no-change forecast (origins with a known outcome)
    corr: float
    hit: float
    rmse: float


@dataclass
class Live:
    selected: list[str]
    coef: pd.Series
    forecast: float  # 12-month real log change from the latest month
    asof: pd.Period
    inputs: pd.Series
    contrib: pd.Series
    scorecard: pd.DataFrame


def quarterly(index: pd.PeriodIndex) -> np.ndarray:
    """Row numbers of Jan/Apr/Jul/Oct month-ends (decisions are taken the next trading day)."""
    return np.array([i for i, p in enumerate(index) if p.month in (1, 4, 7, 10)])


def walk_forward(f: pd.DataFrame, pool: list[str]) -> WalkForward:
    e = Engine(f, pool)
    q = quarterly(e.index)
    allowed = list(range(len(pool)))
    preds, picks, cols = {}, {}, []
    for t in q:
        p = e.index[t]
        if p.year < FIRST_TRADE:
            continue
        if p.month == 1 or not picks:  # re-select once a year on outcomes known by now
            known = q[(q <= t - H) & (np.array([e.index[i].year for i in q]) >= FIRST_SEL)]
            cols = e.select(known, allowed)
            picks[p.year] = {pool[c]: True for c in cols}
        preds[p] = e.forecast(cols, t)
    pred = pd.Series(preds)
    act = f["y"].reindex(pred.index)
    k = act.notna()
    err = act[k] - pred[k]
    return WalkForward(pred, pd.DataFrame(picks).T.reindex(columns=pool).fillna(False),
                       float(1 - (err**2).sum() / (act[k] ** 2).sum()),
                       float(np.corrcoef(pred[k], act[k])[0, 1]),
                       float((np.sign(pred[k]) == np.sign(act[k])).mean()), float(np.sqrt((err**2).mean())))


def live(f: pd.DataFrame, pool: list[str]) -> Live:
    e = Engine(f, pool)
    q = quarterly(e.index)
    known = q[(q <= len(e.index) - 1 - H) & (np.array([e.index[i].year for i in q]) >= FIRST_SEL)]
    allowed = list(range(len(pool)))
    cols = e.select(known, allowed)
    t = len(e.index) - 1
    b = e.coef(cols, t + H)  # use every row with a known outcome
    names = [pool[c] for c in cols]
    x = pd.Series(e.Z[t, [c + 1 for c in cols]], index=names)
    d = f.loc[e.index]
    fit = d[d["y"].notna()]
    contrib = pd.Series(b[1:], index=names) * (x - fit[names].mean())
    base = e.sse([], known)
    card = pd.DataFrame({"r": [fit[c].corr(fit["y"]) for c in pool],
                         "d_sse": [e.sse([i], known) / base - 1 for i in allowed]}, index=pool)
    return Live(names, pd.Series(b, index=["const"] + names), float(b[0] + b[1:] @ x.values), e.index[t],
                x, contrib, card)
