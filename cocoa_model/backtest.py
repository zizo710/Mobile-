"""Walk-forward backtest of a long/short cocoa futures strategy driven by the model.

Once a year, on the first trading day of November (start of crop year H), the model is
rebuilt using only information available at that date:

- production history up to crop year H-1, with the trend/cycle recomputed on that window
- output models re-selected and re-fitted on those years; weather windows that lie in
  the future (harmattan, next spring) are blanked for the season being forecast
- price equation re-estimated on prices up to September of H-1

Fair value for crop year H is compared with the futures price on the entry day:
long if the market is below fair value, short if above. The position is held for
twelve months in the front-month future.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm

from . import price_model, selection, yield_model
from .config import REGIONS

FUTURE_WINDOWS = ("_dry1", "_rains3")  # not observed on 1 November of H-1
MIN_TRAIN_YEARS = 15


@dataclass
class Backtest:
    trades: pd.DataFrame  # one row per crop year, all variants
    daily: pd.DataFrame  # daily strategy returns per variant
    stats: pd.DataFrame
    current: pd.Series  # the open signal for the crop year now starting


def _signal(H: int, prod: pd.DataFrame, feats: pd.DataFrame, price_cy: pd.Series, ypool: list[str],
            data_lag: int, use_weather: bool) -> dict:
    last = min(H - 1 - data_lag, prod.index.max())  # latest crop year with known output
    cycle, trend = yield_model.production_cycle(prod.loc[:last])
    wa_hist = yield_model.aggregate_shock(cycle, trend)
    need = list(range(last + 1, H + 1))
    wa_now = pd.Series(0.0, index=need)
    if use_weather:
        t = cycle.stack().rename("cycle")
        t.index.names = ["year", "country"]
        t = t.reorder_levels(["country", "year"])
        pred = {}
        for c in REGIONS:
            X = feats.loc[c].loc[:H].copy()
            X = (X - X.mean()) / X.std()  # standardise on data available at the time
            X.loc[H, [k for k in X.columns if k.endswith(FUTURE_WINDOWS)]] = np.nan
            X.index = pd.MultiIndex.from_product([[c], X.index], names=["country", "year"])
            sel = selection.select_yield(X, t, ypool)
            pred[c] = sel.predict(X).droplevel("country").loc[need]
        wa_now = yield_model.aggregate_shock(pd.DataFrame(pred), trend)
    f = price_model.frame(price_cy.loc[:H - 1], pd.concat([wa_hist, wa_now]), H, pd.DataFrame())
    fit = f.dropna(subset=["dlp"] + price_model.BASE_COLS).loc[:last]
    ols = sm.OLS(fit["dlp"], sm.add_constant(fit[price_model.BASE_COLS])).fit()
    row = f.loc[H, price_model.BASE_COLS]
    dlp = float(ols.params["const"] + (ols.params[price_model.BASE_COLS] * row).sum())
    return {"fair": float(np.exp(f.loc[H - 1, "lp"] + dlp)), "nowcast": float(wa_now[H]),
            "sigma": float(np.sqrt(ols.mse_resid))}


def _stats(ret: pd.Series, daily: pd.Series) -> dict:
    eq = (1 + daily).cumprod()
    n = len(ret)
    return {"Trades": n, "Average return / year": ret.mean(), "Volatility": ret.std(),
            "Sharpe": ret.mean() / ret.std() if ret.std() > 0 else np.nan,
            "t-stat": ret.mean() / ret.std() * np.sqrt(n) if ret.std() > 0 else np.nan,
            "Hit rate": (ret[ret != 0] > 0).mean(),  # share of active trades that made money
            "Compound return / year": eq.iloc[-1] ** (252 / len(eq)) - 1,
            "Max drawdown": (eq / eq.cummax() - 1).min(), "Worst year": ret.min(), "Best year": ret.max()}


def run(prod: pd.DataFrame, feats: pd.DataFrame, price_cy: pd.Series, fut: pd.Series, ypool: list[str],
        target: int, threshold: float = 0.10) -> Backtest:
    first = max(fut.index.min().year + 1, feats.index.get_level_values("year").min() + MIN_TRAIN_YEARS)
    variants = {"model": (0, True), "no_weather": (0, False), "late_data": (1, True)}
    rows, daily = [], {}
    dret = fut.pct_change()
    for H in range(first, target + 1):
        entry_day = fut.index[fut.index >= pd.Timestamp(H - 1, 11, 1)]
        if len(entry_day) == 0:
            continue
        entry_day = entry_day[0]
        window = fut.loc[entry_day:pd.Timestamp(H, 10, 31)]
        done = H < target
        row = {"H": H, "entry_date": entry_day, "entry": float(fut[entry_day]),
               "exit": float(window.iloc[-1]) if done else np.nan,
               "long_ret": float(window.iloc[-1] / fut[entry_day] - 1) if done else np.nan}
        for name, (lag, wx) in variants.items():
            s = _signal(H, prod, feats, price_cy, ypool, lag, wx)
            gap = np.log(s["fair"] / row["entry"])
            row |= {f"{name}_fair": s["fair"], f"{name}_gap": gap, f"{name}_pos": 1.0 if gap > 0 else -1.0}
            if name == "model":
                row |= {"nowcast": s["nowcast"], "sigma": s["sigma"]}
        row["threshold_pos"] = row["model_pos"] if abs(row["model_gap"]) > threshold else 0.0
        rows.append(row)
        if done:
            d = dret.loc[window.index[1:]]
            for name in (*variants, "threshold"):
                daily.setdefault(name, []).append(d * row[f"{name}_pos"])
            daily.setdefault("always_long", []).append(d)
    tr = pd.DataFrame(rows).set_index("H")
    cur, tr = tr.loc[target], tr.drop(index=target)
    daily = pd.DataFrame({k: pd.concat(v) for k, v in daily.items()})
    labels = {"model": "Model long/short", "threshold": f"Model, trade only if gap > {threshold:.0%}",
              "no_weather": "Price equation only (no weather)", "late_data": "Model, crop data one year late",
              "always_long": "Always long (benchmark)"}
    stats = {}
    for name, lab in labels.items():
        ret = tr["long_ret"] * (tr[f"{name}_pos"] if name != "always_long" else 1.0)
        stats[lab] = _stats(ret, daily[name])
        tr[f"{name}_ret"] = ret
    daily.columns = [labels[c] for c in daily.columns]
    return Backtest(tr, daily, pd.DataFrame(stats).T, cur)
