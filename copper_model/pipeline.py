"""End-to-end copper run: data -> drivers -> fair value vs futures -> backtests."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import numpy as np
import pandas as pd

from cocoa_model import data as base

from . import backtest, data, model


@dataclass
class Result:
    asof: dt.date
    feats: pd.DataFrame
    live: model.Live
    live_test: model.Live  # with placebo variables allowed
    wf: dict[str, model.WalkForward]
    curve: pd.DataFrame
    fut: pd.Series  # front-month future, US$/lb daily
    spot: float  # latest front-month price
    base_price: float  # futures average over the model's latest month
    fair: float  # US$/lb, 12 months ahead
    band68: tuple[float, float]
    fut12: float  # futures price about 12 months out
    fut12_contract: str
    gap: float
    z: float
    verdict: str
    sigma: float
    bt: backtest.Backtest


MAIN, NOREV, TEST = "Model long/short", "Market data only (no revised indicators)", "With 3 placebo variables (test)"


def run(refresh: bool = False) -> Result:
    today = dt.date.today()
    pk = data.prices(refresh)
    fut = data.yahoo_daily("HG=F", "hg", refresh)
    fin = pd.DataFrame({k: (lambda s: s.groupby(s.index.to_period("M")).last())(data.yahoo_daily(sym, k, refresh))
                        for k, sym in (("dxy", "DX-Y.NYB"), ("y10", "^TNX"), ("spx", "^GSPC"))})
    feats = model.build_features(pk, data.cpi_monthly(pk.index), data.cli(refresh), fin,
                                 data.gdp_growth("WLD", refresh), data.gdp_growth("CHN", refresh),
                                 data.mine_production(refresh), base.oni(refresh), base.climate_indices(refresh))
    conv = list(model.CANDIDATES)
    pools = {MAIN: conv, NOREV: [c for c in conv if c not in model.REVISED], TEST: conv + list(model.PLACEBO)}
    wf = {k: model.walk_forward(feats, p) for k, p in pools.items()}
    lv, lv_test = model.live(feats, conv), model.live(feats, pools[TEST])
    bt = backtest.run(fut, {k: w.pred for k, w in wf.items()})

    curve = data.futures_curve(today)
    target = lv.asof + model.H
    far = curve.iloc[(curve["expiry"].map(lambda p: abs((p - target).n))).argmin()]
    month = fut[fut.index.to_period("M") == lv.asof]
    base_price = float(month.mean())
    cpi = data.cpi_monthly(pd.period_range(lv.asof, target, freq="M"))
    fair = base_price * float(np.exp(lv.forecast) * cpi.iloc[-1] / cpi.iloc[0])
    sigma = wf[MAIN].rmse
    gap = float(far["price"] / fair - 1)
    z = float(np.log(far["price"] / fair) / sigma)
    verdict = ("OVERVALUED" if z > 1 else "modestly overvalued" if z > 0.5 else "UNDERVALUED" if z < -1
               else "modestly undervalued" if z < -0.5 else "roughly fairly valued")
    return Result(today, feats, lv, lv_test, wf, curve, fut, float(fut.iloc[-1]), base_price, fair,
                  (fair * np.exp(-sigma), fair * np.exp(sigma)), float(far["price"]), far["contract"],
                  gap, z, verdict, sigma, bt)
