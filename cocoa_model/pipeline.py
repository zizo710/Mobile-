"""End-to-end run: data -> output model -> nowcast -> price model -> futures valuation."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import candidates as cand
from . import data, price_model, selection, yield_model
from .config import EXTRA_WEATHER, FEATURES, FIRST_WEATHER_YEAR, REGIONS


@dataclass
class Variant:
    """One version of the model (a given pool of allowed variables)."""
    name: str
    ysel: dict[str, selection.YieldSelection]  # one output model per country
    psel: selection.PriceSelection
    country_nowcast: pd.DataFrame
    wa_nowcast: pd.Series
    wa_nested: pd.Series
    wa_corr: float
    shock_sd: float
    val: price_model.Valuation


@dataclass
class Result:
    asof: dt.date
    prod: pd.DataFrame
    cycle: pd.DataFrame
    trend: pd.DataFrame
    feats: pd.DataFrame  # all output-model candidates, (country, year)
    correlations: pd.DataFrame  # baseline weather feature x country correlations
    known_share: pd.Series
    wa_hist: pd.Series
    price_m: pd.Series
    price_cy: pd.Series
    curve: pd.DataFrame
    pcands: pd.DataFrame
    enso: pd.Series
    base: Variant  # v1: baseline weather features only, no extra price terms
    main: Variant  # + 20 conventional candidates
    test: Variant  # + 5 unconventional candidates
    overrides: dict[int, float]
    pooled: yield_model.YieldModel  # v1 reference: one pooled ridge on the original features

    @property
    def val(self) -> price_model.Valuation:
        return self.main.val


def run(refresh: bool = False, overrides: dict[int, float] | None = None) -> Result:
    overrides = overrides or {}
    today = dt.date.today()
    target = today.year + (today.month >= 10)  # crop year in progress / just starting

    prod = data.production(refresh)
    wx = data.weather_monthly(refresh)
    oni = data.oni(refresh)
    price_m = data.price_monthly(refresh)
    pink = data.pink_sheet(refresh)
    ci = data.climate_indices(refresh)
    gdp = data.world_gdp_growth(refresh)
    row_prod = data.row_production(refresh)
    curve = data.futures_curve(today)

    cycle, trend = yield_model.production_cycle(prod)
    wa_hist = yield_model.aggregate_shock(cycle, trend)
    price_cy = price_model.crop_year_price(price_m)
    all_years = list(range(1951, target + 1))
    years = list(range(FIRST_WEATHER_YEAR + 2, target + 1))
    enso = yield_model.enso_by_harvest_year(oni, all_years)
    common = cand.common_series(pink, price_cy, ci, gdp, row_prod, price_m, all_years, target)

    feats = yield_model.build_features(wx, oni, years).join(cand.yield_candidates(wx, common, years))
    t = cycle.stack().rename("cycle")
    t.index.names = ["year", "country"]
    t = t.reorder_levels(["country", "year"])
    corr = pd.DataFrame({c: feats.loc[c].corrwith(t[c]) for c in REGIONS})
    corr["Pooled"] = feats.corrwith(t.reindex(feats.index))
    now_years = [y for y in years if y > prod.index.max()]
    known = feats.notna().groupby("year").mean().mean(axis=1).loc[now_years]

    pcands = cand.price_candidates(common, enso)
    lo, hi = pd.Period(f"{target - 1}-10", "M"), pd.Period(f"{target}-09", "M")
    strip = float(curve[(curve["expiry"] >= lo) & (curve["expiry"] <= hi)]["price"].mean())
    pframe = price_model.frame(price_cy, wa_hist, target, pcands)

    y_base = [f[0] for f in FEATURES] + ["oni"]
    y_conv = y_base + [e[0] for e in EXTRA_WEATHER] + ["tsa", "tna", "iod", "nao", "price_plant",
                                                         "price_lag1", "urea_lag"]

    def variant(name: str, ypool: list[str], ppool: list[str]) -> Variant:
        ysel, pred, nested = {}, {}, {}
        for c in REGIONS:
            Xc = feats[feats.index.get_level_values("country") == c]
            ysel[c] = selection.select_yield(Xc, t, ypool)
            pred[c] = ysel[c].predict(Xc).droplevel("country")
            n = ysel[c].nested_pred.droplevel("country")
            nested[c] = n if ysel[c].used else n * 0.0  # countries without skill sit at trend
        cn = pd.DataFrame(pred).loc[now_years]
        wa_now = yield_model.aggregate_shock(cn, trend)
        for y, v in overrides.items():
            wa_now.loc[y] = v
        wa_now = wa_now.sort_index()
        wa_nested = yield_model.aggregate_shock(pd.DataFrame(nested).dropna(), trend)
        act = wa_hist.reindex(wa_nested.index)
        corr_wa = float(np.corrcoef(act, wa_nested)[0, 1]) if wa_nested.std() > 0 else 0.0
        sd = float((act - wa_nested).std())
        psel = selection.select_price(pframe, price_model.BASE_COLS, ppool)
        val = price_model.value(price_cy, wa_hist, wa_now, strip, target, sd, pcands, psel.selected)
        return Variant(name, ysel, psel, cn, wa_now, wa_nested, corr_wa, sd, val)

    base = variant("Original model", y_base, [])
    main = variant("With 20 added data points", y_conv, cand.PRICE_CONVENTIONAL)
    test = variant("…plus 5 unconventional (test)", y_conv + cand.YIELD_UNUSUAL,
                   cand.PRICE_CONVENTIONAL + cand.PRICE_UNUSUAL)
    return Result(today, prod, cycle, trend, feats, corr, known, wa_hist, price_m, price_cy, curve,
                  pcands, enso, base, main, test, overrides, yield_model.fit(feats[y_base], cycle))
