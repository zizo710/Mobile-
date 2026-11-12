"""Copper data (all free/public). Reuses the cocoa model's download + cache helpers.

- World Bank Pink Sheet ... monthly LME copper, aluminium, oil, gold, iron ore, zinc, nickel (1960+)
- OECD .................... composite leading indicators, G20 and China
- Yahoo Finance ........... COMEX copper futures (HG), dollar index, US 10-year yield, S&P 500
- World Bank .............. world and China GDP growth
- USGS .................... world copper mine production (annual)
- NOAA / SILSO ............ ENSO, QBO, sunspots (the last two only as placebo variables)
"""
from __future__ import annotations

import datetime as dt
import io
import time

import numpy as np
import pandas as pd

from cocoa_model import data as base
from cocoa_model.config import US_CPI

LB_PER_TONNE = 2204.62
PINK = {"Copper": "copper", "Aluminum": "alu", "Crude oil, average": "oil", "Gold": "gold",
        "Iron ore, cfr spot": "iron", "Zinc": "zinc", "Nickel": "nickel", "Cocoa": "cocoa"}
CLI_URL = ("https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_STES@DF_CLI/"
           "CHN+G20.M.LI...AA...H?startPeriod=1960-01&format=csvfile")
GDP_URL = "https://api.worldbank.org/v2/country/{}/indicator/NY.GDP.MKTP.KD.ZG?format=json&per_page=200"
USGS_URL = ("https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/s3fs-public/"
            "media/files/ds140-copper-2020.xlsx")
# USGS Mineral Commodity Summaries, world mine production (t), approximate, for years after ds140
USGS_RECENT = {2021: 21.2e6, 2022: 22.0e6, 2023: 22.6e6, 2024: 23.0e6}
HG_MONTHS = "FGHJKMNQUVXZ"


def prices(refresh: bool = False) -> pd.DataFrame:
    return base.pink_sheet(refresh, PINK, "pink_copper.csv")


def yahoo_daily(sym: str, name: str, refresh: bool = False) -> pd.Series:
    path, ok = base._cached(f"yahoo_{name}.csv", 24, refresh)
    if ok:
        return pd.read_csv(path, index_col=0, parse_dates=True)["close"]
    r = base._yahoo(sym, period1=0, period2=int(time.time()), interval="1d")
    s = pd.Series(r["indicators"]["quote"][0]["close"],
                  index=pd.to_datetime(r["timestamp"], unit="s").normalize(), name="close").dropna()
    s = s[~s.index.duplicated(keep="last")]
    s.to_csv(path)
    return s


def cli(refresh: bool = False) -> pd.DataFrame:
    """OECD composite leading indicators (amplitude adjusted), columns G20 and CHN."""
    path, ok = base._cached("oecd_cli.csv", 24 * 7, refresh)
    if ok:
        d = pd.read_csv(path, index_col=0)
    else:
        raw = pd.read_csv(io.StringIO(base._get(CLI_URL, timeout=120).text))
        d = raw.pivot_table(index="TIME_PERIOD", columns="REF_AREA", values="OBS_VALUE")
        d.to_csv(path)
    d.index = pd.PeriodIndex(d.index, freq="M")
    return d


def gdp_growth(country: str, refresh: bool = False) -> pd.Series:
    path, ok = base._cached(f"gdp_{country}.csv", 24 * 30, refresh)
    if ok:
        return pd.read_csv(path, index_col=0)["gdp"]
    rows = base._get(GDP_URL.format(country), timeout=60).json()[1]
    s = pd.Series({int(r["date"]): r["value"] for r in rows if r["value"] is not None}, name="gdp").sort_index()
    s.to_csv(path)
    return s


def mine_production(refresh: bool = False) -> pd.Series:
    """World copper mine production, tonnes per year."""
    path, ok = base._cached("usgs_copper.csv", 24 * 90, refresh)
    if ok:
        return pd.read_csv(path, index_col=0)["world"]
    raw = pd.read_excel(io.BytesIO(base._get(USGS_URL).content), header=None)
    hdr = raw.index[raw[0].astype(str).str.strip() == "Year"][0]
    col = [c for c in raw.columns if str(raw.loc[hdr, c]).strip() == "World production"][0]
    body = raw.loc[hdr + 1:]
    body = body[pd.to_numeric(body[0], errors="coerce").notna()]
    s = pd.Series(pd.to_numeric(body[col], errors="coerce").values, index=body[0].astype(int), name="world").dropna()
    for y, v in USGS_RECENT.items():
        s.loc[y] = v
    s = s.sort_index()
    s.to_csv(path)
    return s


def cpi_monthly(index: pd.PeriodIndex) -> pd.Series:
    """US CPI interpolated to months from the annual table (extrapolated at the last growth rate)."""
    c = pd.Series(US_CPI)
    x = index.year + (index.month - 0.5) / 12
    return pd.Series(np.interp(x, c.index + 0.5, c.values), index=index)


def futures_curve(today: dt.date | None = None, n: int = 16) -> pd.DataFrame:
    """Live COMEX copper curve (US$/lb) for the next `n` contract months."""
    today = today or dt.date.today()
    rows = []
    y, m = today.year, today.month
    for _ in range(n):
        m += 1
        if m > 12:
            y, m = y + 1, 1
        sym = f"HG{HG_MONTHS[m - 1]}{y % 100:02d}.CMX"
        try:
            meta = base._yahoo(sym, range="5d", interval="1d")["meta"]
            rows.append({"contract": sym.split(".")[0], "expiry": pd.Period(f"{y}-{m:02d}", "M"),
                         "price": float(meta["regularMarketPrice"]),
                         "asof": dt.datetime.fromtimestamp(meta["regularMarketTime"], dt.timezone.utc)})
        except Exception:
            pass
    if not rows:
        raise RuntimeError("could not fetch any copper futures quotes")
    return pd.DataFrame(rows)
