"""Variable selection with honest (nested) out-of-sample scoring.

Output model: ridge regression, forward selection on leave-one-year-out (LOYO) R².
The reported skill is *nested*: for each held-out year the whole selection is re-run
on the remaining years, so the score is not flattered by the search itself.

Price model: OLS, forward selection by BIC. The reported out-of-sample error
re-selects at every forecast origin using only earlier data.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import statsmodels.api as sm

ALPHA = 3.0  # light ridge penalty on z-scored features
MIN_GAIN = 0.03  # a variable must add at least 3 points of LOYO R²
MIN_NESTED_R2 = 0.05  # a country's weather model is used only if its honest skill beats this
MAX_VARS = 6


# ------------------------------------------------------------------ output (yield) model
class _Folds:
    """Per-year sufficient statistics so LOYO errors need no row-level refits."""

    def __init__(self, X: pd.DataFrame, t: pd.Series):
        self.cols = list(X.columns)
        self.years = np.array(sorted(set(X.index.get_level_values("year"))))
        yr = X.index.get_level_values("year").to_numpy()
        self.X, self.t, self.rows = X.values, t.values, [np.where(yr == y)[0] for y in self.years]
        self.A = np.stack([self.X[r].T @ self.X[r] for r in self.rows])
        self.b = np.stack([self.X[r].T @ self.t[r] for r in self.rows])
        self.tt = np.array([self.t[r] @ self.t[r] for r in self.rows])

    def r2(self, idx: list[int], folds: np.ndarray) -> float:
        if not idx:
            return 0.0
        ix = np.ix_(folds, idx, idx)
        A, b = self.A[ix], self.b[np.ix_(folds, idx)]
        M = A.sum(0)[None] - A + ALPHA * np.eye(len(idx))[None]
        c = np.linalg.solve(M, (b.sum(0)[None] - b)[..., None])[..., 0]
        sse = self.tt[folds] - 2 * (c * b).sum(1) + np.einsum("yi,yij,yj->y", c, A, c)
        return float(1 - sse.sum() / self.tt[folds].sum())

    def forward(self, pool: list[int], folds: np.ndarray) -> list[int]:
        idx: list[int] = []
        best = 0.0
        while len(idx) < MAX_VARS:
            scores = {j: self.r2(idx + [j], folds) for j in pool if j not in idx}
            j = max(scores, key=scores.get)
            if scores[j] - best < MIN_GAIN:
                break
            idx.append(j)
            best = scores[j]
        return idx

    def coef(self, idx: list[int], folds: np.ndarray) -> np.ndarray:
        A = self.A[np.ix_(folds, idx, idx)].sum(0) + ALPHA * np.eye(len(idx))
        return np.linalg.solve(A, self.b[np.ix_(folds, idx)].sum(0))


@dataclass
class YieldSelection:
    selected: list[str]
    coef: pd.Series
    r2_selected: float  # LOYO R² of the chosen set (optimistic: chosen on this score)
    r2_nested: float  # honest: selection repeated inside every fold
    corr_nested: float
    nested_pred: pd.Series
    scorecard: pd.DataFrame  # per candidate: pooled r, LOYO R² alone
    pick_rate: pd.Series  # share of nested folds in which each variable was chosen
    n_obs: int

    @property
    def used(self) -> bool:
        return bool(self.selected) and self.r2_nested > MIN_NESTED_R2

    def predict(self, X: pd.DataFrame) -> pd.Series:
        if not self.used:
            return pd.Series(0.0, index=X.index)
        return X[self.selected].fillna(0.0) @ self.coef  # unobserved -> climatology


def select_yield(X: pd.DataFrame, t: pd.Series, pool: list[str]) -> YieldSelection:
    df = X[pool].join(t.rename("t"), how="inner").dropna()
    X, t = df[pool], df["t"]
    f = _Folds(X, t)
    allf = np.arange(len(f.years))
    pidx = list(range(len(pool)))
    sel = f.forward(pidx, allf)

    pred = np.zeros(len(t))
    picks = np.zeros(len(pool))
    for k in allf:
        rest = allf[allf != k]
        s = f.forward(pidx, rest)
        picks[s] += 1
        if s:
            pred[f.rows[k]] = f.X[np.ix_(f.rows[k], s)] @ f.coef(s, rest)
    r2n = float(1 - ((f.t - pred) ** 2).sum() / (f.t**2).sum())
    corr = float(np.corrcoef(pred, f.t)[0, 1]) if pred.std() > 0 else 0.0

    card = pd.DataFrame({"r": X.corrwith(t), "r2_alone": [f.r2([j], allf) for j in pidx]}, index=pool)
    names = [pool[j] for j in sel]
    return YieldSelection(names, pd.Series(f.coef(sel, allf), index=names), f.r2(sel, allf), r2n, corr,
                          pd.Series(pred, index=t.index), card, pd.Series(picks / len(allf), index=pool),
                          len(t))


# ------------------------------------------------------------------------- price model
def _bic_forward(d: pd.DataFrame, base: list[str], pool: list[str]) -> list[str]:
    cols = list(base)
    best = sm.OLS(d["dlp"], sm.add_constant(d[cols])).fit().bic
    while True:
        trial = {c: sm.OLS(d["dlp"], sm.add_constant(d[cols + [c]])).fit().bic for c in pool if c not in cols}
        if not trial:
            break
        c = min(trial, key=trial.get)
        if trial[c] >= best:
            break
        cols.append(c)
        best = trial[c]
    return cols[len(base):]


def _oos_rmse(d: pd.DataFrame, cols_fn, start: int) -> float:
    err = []
    for y in d.index[d.index >= start]:
        tr = d[d.index < y]
        cols = cols_fn(tr)
        m = sm.OLS(tr["dlp"], sm.add_constant(tr[cols])).fit()
        err.append(d.loc[y, "dlp"] - float(np.r_[1.0, d.loc[y, cols].values] @ m.params.values))
    return float(np.sqrt(np.mean(np.square(err))))


@dataclass
class PriceSelection:
    selected: list[str]  # BIC picks, kept only if they also forecast better out of sample
    bic_picks: list[str]
    rmse_nochange: float
    rmse_base: float
    rmse_selected: float  # honest: re-selected at each forecast origin
    scorecard: pd.DataFrame  # per candidate: t-stat when added to the baseline, change in OOS RMSE
    n_obs: int
    first_oos: int = field(default=1990)


def select_price(d: pd.DataFrame, base: list[str], pool: list[str], start: int = 1990) -> PriceSelection:
    d = d.dropna(subset=["dlp"] + base + pool)
    rm_base = _oos_rmse(d, lambda tr: base, start)
    rows = {}
    for c in pool:
        m = sm.OLS(d["dlp"], sm.add_constant(d[base + [c]])).fit()
        rows[c] = {"t": m.tvalues[c], "d_rmse": _oos_rmse(d, lambda tr, c=c: base + [c], start) / rm_base - 1}
    oos = d[d.index >= start]["dlp"]
    picks = _bic_forward(d, base, pool)
    rm_sel = _oos_rmse(d, lambda tr: base + _bic_forward(tr, base, pool), start) if pool else rm_base
    return PriceSelection(picks if rm_sel < rm_base else [], picks, float(np.sqrt((oos**2).mean())),
                          rm_base, rm_sel, pd.DataFrame(rows).T, len(d), start)
