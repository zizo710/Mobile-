"""End-to-end run: data -> weather/yield model -> nowcast -> futures valuation."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import data, price_model, yield_model
from .config import FIRST_WEATHER_YEAR, REGIONS


@dataclass
class Result:
    asof: dt.date
    prod: pd.DataFrame
    cycle: pd.DataFrame
    trend: pd.DataFrame
    feats: pd.DataFrame
    ym: yield_model.YieldModel
    country_nowcast: pd.DataFrame  # predicted cycle per country for nowcast years
    known_share: pd.Series  # share of features observed per nowcast year
    wa_hist: pd.Series
    wa_cv: pd.Series
    wa_nowcast: pd.Series
    price_m: pd.Series
    price_cy: pd.Series
    curve: pd.DataFrame
    val: price_model.Valuation
    val_enso: price_model.Valuation
    enso: pd.Series
    shock_sd: float
    overrides: dict[int, float]


def run(refresh: bool = False, overrides: dict[int, float] | None = None) -> Result:
    overrides = overrides or {}
    today = dt.date.today()
    target = today.year + (today.month >= 10)  # crop year in progress / just starting

    prod = data.production(refresh)
    wx = data.weather_monthly(refresh)
    oni = data.oni(refresh)
    price_m = data.price_monthly(refresh)
    curve = data.futures_curve(today)

    cycle, trend = yield_model.production_cycle(prod)
    years = list(range(FIRST_WEATHER_YEAR + 2, target + 1))
    feats = yield_model.build_features(wx, oni, years)
    ym = yield_model.fit(feats, cycle)

    now_years = [y for y in years if y > prod.index.max()]
    pred = ym.predict(feats).unstack("country")[list(REGIONS)]
    country_nowcast = pred.loc[now_years]
    known = feats.notna().groupby("year").mean().mean(axis=1).loc[now_years]

    wa_hist = yield_model.aggregate_shock(cycle, trend)
    cv = ym.cv_pred.unstack("country")[list(REGIONS)]
    wa_cv = yield_model.aggregate_shock(cv, trend)
    wa_now = yield_model.aggregate_shock(country_nowcast, trend)
    for y, v in overrides.items():
        wa_now.loc[y] = v
    wa_now = wa_now.sort_index()
    shock_sd = float((wa_hist.reindex(wa_cv.index) - wa_cv).std())

    price_cy = price_model.crop_year_price(price_m)
    # futures strip for the target crop year: contracts expiring Oct(target-1)..Sep(target)
    lo, hi = pd.Period(f"{target - 1}-10", "M"), pd.Period(f"{target}-09", "M")
    strip = float(curve[(curve["expiry"] >= lo) & (curve["expiry"] <= hi)]["price"].mean())
    enso = yield_model.enso_by_harvest_year(oni, list(range(1951, target + 1)))
    val = price_model.value(price_cy, wa_hist, wa_now, strip, target, shock_sd, enso)
    val_enso = price_model.value(price_cy, wa_hist, wa_now, strip, target, shock_sd, enso, with_enso=True)
    return Result(today, prod, cycle, trend, feats, ym, country_nowcast, known, wa_hist, wa_cv,
                  wa_now, price_m, price_cy, curve, val, val_enso, enso, shock_sd, overrides)
