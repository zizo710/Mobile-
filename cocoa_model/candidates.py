"""Candidate explanatory variables beyond the baseline model.

20 conventional candidates and 5 deliberately unconventional ones (the "test" set).
Every candidate must earn its place out of sample - see selection.py.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
from statsmodels.tsa.filters.hp_filter import hpfilter

from .config import EXTRA_WEATHER, REGIONS, SUM_VARS, WINDOWS
from .data import real_factor

# name -> (label, group, source)
CONVENTIONAL = {
    # weather (per country) -> output model
    "dryspell_rains1": ("Longest dry spell, main rains", "weather", "NASA POWER"),
    "heavy_rains2": ("Heavy-rain days (≥20 mm), short rains", "weather", "NASA POWER"),
    "vpd_dry1": ("Vapour-pressure deficit, harmattan", "weather", "NASA POWER"),
    "wind_dry1": ("Wind speed, harmattan", "weather", "NASA POWER"),
    "tmin_rains1": ("Night temperature, main rains", "weather", "NASA POWER"),
    "wbal_season": ("Water balance (rain − PET), Apr–Oct", "weather", "NASA POWER"),
    "heatdays_dry0": ("Heat days (>33 °C), prior dry season", "weather", "NASA POWER"),
    "soil_enddry0": ("Soil moisture at end of dry season", "weather", "NASA POWER"),
    # ocean / atmosphere indices -> both models
    "tsa": ("Tropical South Atlantic SST (Atlantic Niño), Jun–Aug", "climate", "NOAA PSL"),
    "tna": ("Tropical North Atlantic SST, Jun–Aug", "climate", "NOAA PSL"),
    "iod": ("Indian Ocean Dipole, Jun–Oct", "climate", "NOAA PSL"),
    "nao": ("North Atlantic Oscillation, Dec–Feb", "climate", "NOAA PSL"),
    # supply economics -> output model
    "price_plant": ("Real cocoa price 3–6 years earlier (plantings)", "economics", "World Bank"),
    "price_lag1": ("Real cocoa price last season (farm upkeep)", "economics", "World Bank"),
    "urea_lag": ("Real fertiliser (urea) price last season", "economics", "World Bank"),
    # market -> price model
    "S_row": ("Rest-of-world cocoa output vs trend", "market", "FAOSTAT"),
    "gdp_lag": ("World GDP growth, prior year", "market", "World Bank"),
    "sugar_lag": ("Sugar price change, prior season", "market", "World Bank"),
    "palm_lag": ("Palm oil price change, prior season", "market", "World Bank"),
    "vol_lag": ("Cocoa price volatility, prior season", "market", "World Bank"),
}
UNUSUAL = {
    "sunspots": ("Sunspot number, prior year", "test", "SILSO"),
    "qbo": ("Quasi-biennial oscillation (stratospheric wind)", "test", "NOAA PSL"),
    "gold_lag": ("Real gold price (illegal-mining pressure)", "test", "World Bank"),
    "rubber_rel": ("Rubber-to-cocoa price ratio (crop switching)", "test", "World Bank"),
    "easter": ("Easter date (days after 1 March)", "test", "calendar"),
}
LABELS = {k: v[0] for k, v in {**CONVENTIONAL, **UNUSUAL}.items()}
LABELS["oni"] = "ENSO (ONI), Jun–Oct"

INDEX_WINDOWS = {
    "tsa": [(-1, 6), (-1, 7), (-1, 8)],
    "tna": [(-1, 6), (-1, 7), (-1, 8)],
    "iod": [(-1, m) for m in (6, 7, 8, 9, 10)],
    "nao": [(-2, 12), (-1, 1), (-1, 2)],
    "qbo": [(-1, m) for m in (6, 7, 8, 9, 10)],
    "sunspots": [(-1, m) for m in range(1, 13)],
}


def _z(s: pd.Series) -> pd.Series:
    return (s - s.mean()) / s.std()


def _easter_offset(year: int) -> int:
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    g = (8 * b + 13) // 25
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741
    m = (a + 11 * h + 19 * l) // 433
    month = (h + l - 7 * m + 90) // 25
    day = (h + l - 7 * m + 33 * month + 19) % 32
    return (dt.date(year, month, day) - dt.date(year, 3, 1)).days


def crop_year_mean(monthly: pd.Series, min_months: int = 9) -> pd.Series:
    h = monthly.index.year + (monthly.index.month >= 10)
    g = monthly.dropna().groupby(h[monthly.notna()])
    return g.mean()[g.count() >= min_months]


def index_features(ci: pd.DataFrame, years: list[int]) -> pd.DataFrame:
    """Seasonal means of the climate indices per harvest year (need >= half the months)."""
    out = {}
    for name, months in INDEX_WINDOWS.items():
        vals = {}
        for h in years:
            v = ci[name].reindex([(h + dy, m) for dy, m in months]).dropna()
            vals[h] = v.mean() if len(v) * 2 >= len(months) else np.nan
        out[name] = pd.Series(vals)
    return pd.DataFrame(out)


def common_series(pink: pd.DataFrame, cocoa_cy: pd.Series, ci: pd.DataFrame, gdp: pd.Series,
                  row_prod: pd.Series, price_m: pd.Series, years: list[int], base_year: int) -> pd.DataFrame:
    """All year-indexed (not country-specific) candidates, in raw units."""
    f = index_features(ci, years)
    ext = lambda s: s.reindex(years)  # noqa: E731  (extend to future years before lagging)
    real = lambda s: np.log(s * real_factor(s.index, base_year))  # noqa: E731
    lp = ext(real(cocoa_cy))
    cy = {c: ext(real(crop_year_mean(pink[c]))) for c in ("sugar", "palm", "urea", "gold", "rubber")}
    f["price_plant"] = lp.rolling(4).mean().shift(3)
    f["price_lag1"] = lp.shift(1)
    f["urea_lag"] = cy["urea"].shift(1)
    cyc, _ = hpfilter(np.log(row_prod.dropna()), lamb=100)
    f["S_row"] = cyc
    f["gdp_lag"] = ext(gdp).shift(1).ffill()
    f["sugar_lag"] = cy["sugar"].diff().shift(1)
    f["palm_lag"] = cy["palm"].diff().shift(1)
    dl = np.log(price_m).diff()
    f["vol_lag"] = ext(dl.groupby(price_m.index.year + (price_m.index.month >= 10)).std()).shift(1)
    f["gold_lag"] = cy["gold"].shift(1)
    f["rubber_rel"] = (cy["rubber"] - lp).rolling(4).mean().shift(3)
    f["easter"] = pd.Series({h: _easter_offset(h) for h in years})
    return f.reindex(years)


def yield_candidates(wx: pd.DataFrame, common: pd.DataFrame, years: list[int]) -> pd.DataFrame:
    """Extra candidates for the output model, z-scored, indexed (country, year)."""
    windows = {n: months for n, months, _ in WINDOWS}
    shared = ["tsa", "tna", "iod", "nao", "price_plant", "price_lag1", "urea_lag",
              "sunspots", "qbo", "gold_lag", "rubber_rel"]
    zc = common[shared].apply(_z)
    frames = []
    for country in REGIONS:
        w = wx[wx["country"] == country].set_index(["year", "month"])
        d = pd.DataFrame(index=years)
        for name, var, win, agg in EXTRA_WEATHER:
            vals = []
            for h in years:
                keys = [(h + dy, m) for dy, m in windows[win]]
                if all(k in w.index for k in keys) and w.loc[keys, var].notna().all():
                    x = w.loc[keys, var]
                    vals.append(x.sum() if var in SUM_VARS else x.max() if agg == "max" else x.mean())
                else:
                    vals.append(np.nan)
            d[name] = _z(pd.Series(vals, index=years, dtype=float))
        d = d.join(zc)
        d["country"] = country
        frames.append(d.rename_axis("year").reset_index().set_index(["country", "year"]))
    return pd.concat(frames)


def price_candidates(common: pd.DataFrame, enso: pd.Series) -> pd.DataFrame:
    """Candidates for the price equation, indexed by harvest year (raw units)."""
    f = common[["S_row", "gdp_lag", "sugar_lag", "palm_lag", "vol_lag", "tsa", "tna", "iod", "nao",
                "sunspots", "qbo", "easter"]].copy()
    f["S_row_lag"] = f["S_row"].shift(1)
    f["oni"] = enso
    f["gold_lag"] = common["gold_lag"].diff()  # change in real gold price, prior season
    f["rubber_lag"] = common["rubber_rel"]
    return f


PRICE_CONVENTIONAL = ["S_row", "S_row_lag", "gdp_lag", "sugar_lag", "palm_lag", "vol_lag",
                      "oni", "tsa", "tna", "iod", "nao"]
PRICE_UNUSUAL = ["sunspots", "qbo", "gold_lag", "rubber_lag", "easter"]
YIELD_UNUSUAL = ["sunspots", "qbo", "gold_lag", "rubber_rel"]
LABELS["S_row_lag"] = "Rest-of-world output vs trend, prior season"
LABELS["rubber_lag"] = LABELS["rubber_rel"]
