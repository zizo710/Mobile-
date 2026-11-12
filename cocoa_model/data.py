"""Data fetchers (all free/public sources), with an on-disk cache.

- FAOSTAT bulk download ........ cocoa bean production by country, 1961+
- NASA POWER daily API ......... weather at cocoa-belt points, 1981+ (near real time)
- NOAA CPC ..................... Oceanic Niño Index (ENSO)
- World Bank Pink Sheet ........ monthly ICCO cocoa price, 1960+
- Yahoo Finance ................ ICE NY cocoa futures (front-month history + live curve)
"""
from __future__ import annotations

import datetime as dt
import io
import re
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import requests

from .config import CACHE_DIR, FIRST_WEATHER_YEAR, FUTURES_MONTHS, POWER_PARAMS, REGIONS

UA = {"User-Agent": "Mozilla/5.0 (cocoa-model)"}
FAO_URL = "https://bulks-faostat.fao.org/production/Production_Crops_Livestock_E_Africa.zip"
POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
ONI_URL = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
WB_PAGE = "https://www.worldbank.org/en/research/commodity-markets"
WB_FALLBACK = ("https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/"
               "related/CMO-Historical-Data-Monthly.xlsx")
YAHOO_URL = "https://query2.finance.yahoo.com/v8/finance/chart/{sym}"


def _get(url: str, tries: int = 4, timeout: int = 180, **kw) -> requests.Response:
    err: Exception | None = None
    for i in range(tries):
        try:
            r = requests.get(url, headers=UA, timeout=timeout, **kw)
            if r.status_code == 200:
                return r
            err = RuntimeError(f"HTTP {r.status_code} for {url}")
        except requests.RequestException as e:  # network hiccup: back off and retry
            err = e
        time.sleep(2 * 2**i)
    raise RuntimeError(f"failed to fetch {url}: {err}")


def _cached(name: str, max_age_h: float, refresh: bool):
    path = CACHE_DIR / name
    if path.exists() and not refresh:
        if (time.time() - path.stat().st_mtime) / 3600 < max_age_h:
            return path, True
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return path, False


# --------------------------------------------------------------------------- FAOSTAT
def production(refresh: bool = False) -> pd.DataFrame:
    """Cocoa bean production in tonnes; index = FAOSTAT year, columns = country."""
    path, ok = _cached("fao_cocoa_production.csv", 24 * 30, refresh)
    if ok:
        return pd.read_csv(path, index_col=0)
    z = zipfile.ZipFile(io.BytesIO(_get(FAO_URL).content))
    name = next(n for n in z.namelist() if n.endswith("_Africa_NOFLAG.csv"))
    d = pd.read_csv(z.open(name), encoding="utf-8")
    d = d[(d["Item"] == "Cocoa beans") & (d["Element"] == "Production") & d["Area"].isin(REGIONS)]
    ycols = [c for c in d.columns if re.fullmatch(r"Y\d{4}", c)]
    out = d.set_index("Area")[ycols].T
    out.index = [int(c[1:]) for c in ycols]
    out = out[list(REGIONS)].dropna(how="all")
    out.to_csv(path)
    return out


# ------------------------------------------------------------------------ NASA POWER
def _power_point(lat: float, lon: float, end: dt.date) -> pd.DataFrame:
    r = _get(POWER_URL, params={
        "parameters": ",".join(POWER_PARAMS), "community": "AG", "latitude": lat,
        "longitude": lon, "start": f"{FIRST_WEATHER_YEAR}0101",
        "end": end.strftime("%Y%m%d"), "format": "JSON"})
    p = r.json()["properties"]["parameter"]
    df = pd.DataFrame({POWER_PARAMS[k]: pd.Series(v) for k, v in p.items()})
    df.index = pd.to_datetime(df.index, format="%Y%m%d")
    return df.where(df > -900)


def weather_monthly(refresh: bool = False) -> pd.DataFrame:
    """Monthly country-average weather. Columns: country, year, month, rain(mm/month),
    tmax, rh, soil, rad, n_days. Only months with >=25 valid days of rain are kept."""
    path, ok = _cached("weather_monthly.csv", 24, refresh)
    if ok:
        return pd.read_csv(path)
    end = dt.date.today()
    jobs = [(c, s, lat, lon) for c, pts in REGIONS.items() for s, (lat, lon) in pts.items()]
    with ThreadPoolExecutor(4) as ex:
        frames = list(ex.map(lambda j: _power_point(j[2], j[3], end), jobs))
    rows = []
    for (country, _station, _, _), df in zip(jobs, frames):
        g = df.groupby([df.index.year, df.index.month])
        m = g.mean()
        m["n_days"] = g["rain"].count()
        m["rain"] = m["rain"] * g["rain"].size()  # mean mm/day × days in month
        m.index.names = ["year", "month"]
        m = m.reset_index()
        m["country"] = country
        rows.append(m)
    allm = pd.concat(rows)
    out = allm.groupby(["country", "year", "month"], as_index=False).mean(numeric_only=True)
    out = out[out["n_days"] >= 25]
    out.to_csv(path, index=False)
    return out


# ------------------------------------------------------------------------------ ENSO
def oni(refresh: bool = False) -> pd.Series:
    """Oceanic Niño Index, indexed by (year, centre month of the 3-month season)."""
    path, ok = _cached("oni.csv", 24 * 7, refresh)
    if ok:
        return pd.read_csv(path, index_col=[0, 1])["oni"]
    seasons = ["DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ", "JJA", "JAS", "ASO", "SON", "OND", "NDJ"]
    rows = []
    for line in _get(ONI_URL, timeout=60).text.splitlines()[1:]:
        p = line.split()
        if len(p) == 4 and p[0] in seasons:
            rows.append((int(p[1]), seasons.index(p[0]) + 1, float(p[3])))
    s = pd.DataFrame(rows, columns=["year", "month", "oni"]).set_index(["year", "month"])["oni"]
    s.to_csv(path)
    return s


# ---------------------------------------------------------------------------- prices
def _yahoo(sym: str, **params) -> dict:
    return _get(YAHOO_URL.format(sym=sym), timeout=40, params=params).json()["chart"]["result"][0]


def price_monthly(refresh: bool = False) -> pd.Series:
    """Monthly cocoa price in US$/tonne, PeriodIndex(M). World Bank Pink Sheet (ICCO daily
    price) extended with monthly averages of the ICE NY front-month future where the
    Pink Sheet has not been published yet."""
    path, ok = _cached("price_monthly.csv", 24, refresh)
    if ok:
        s = pd.read_csv(path, index_col=0)["price"]
        s.index = pd.PeriodIndex(s.index, freq="M")
        return s
    try:
        html = _get(WB_PAGE, tries=2, timeout=60).text
        url = re.search(r"https://thedocs\.worldbank\.org[^\"']*CMO-Historical-Data-Monthly\.xlsx", html).group(0)
    except Exception:
        url = WB_FALLBACK
    raw = pd.read_excel(io.BytesIO(_get(url).content), sheet_name="Monthly Prices", header=None)
    hdr = raw.index[raw.apply(lambda r: r.astype(str).str.fullmatch("Cocoa").any(), axis=1)][0]
    col = raw.columns[raw.loc[hdr].astype(str) == "Cocoa"][0]
    body = raw[raw[0].astype(str).str.fullmatch(r"\d{4}M\d{2}")]
    wb = pd.to_numeric(body[col], errors="coerce") * 1000.0  # $/kg -> $/t
    wb.index = pd.PeriodIndex(body[0].str.replace("M", "-"), freq="M")
    wb = wb.dropna()

    r = _yahoo("CC=F", period1=0, period2=int(time.time()), interval="1d")
    fut = pd.Series(r["indicators"]["quote"][0]["close"],
                    index=pd.to_datetime(r["timestamp"], unit="s")).dropna()
    fm = fut.groupby(fut.index.to_period("M")).mean()
    s = pd.concat([wb, fm[fm.index > wb.index[-1]]]).rename("price")
    s.to_csv(path)
    return s


def futures_curve(today: dt.date | None = None, n: int = 8) -> pd.DataFrame:
    """Live ICE NY cocoa curve: next `n` contracts with last price (US$/t)."""
    today = today or dt.date.today()
    rows = []
    y = today.year
    while len(rows) < n and y < today.year + 4:
        for code, month in FUTURES_MONTHS.items():
            # contracts stop trading mid delivery month; skip the current month
            if (y, month) <= (today.year, today.month) or len(rows) >= n:
                continue
            sym = f"CC{code}{y % 100:02d}.NYB"
            try:
                meta = _yahoo(sym, range="5d", interval="1d")["meta"]
                rows.append({"contract": sym.split(".")[0], "expiry": pd.Period(f"{y}-{month:02d}", "M"),
                             "price": float(meta["regularMarketPrice"]),
                             "asof": dt.datetime.fromtimestamp(meta["regularMarketTime"], dt.timezone.utc)})
            except Exception:
                pass
        y += 1
    if not rows:
        raise RuntimeError("could not fetch any cocoa futures quotes")
    return pd.DataFrame(rows)


def real_factor(years: np.ndarray | list[int], base_year: int) -> np.ndarray:
    """Multiplier converting nominal $ of each year into base-year $."""
    from .config import US_CPI
    last = max(US_CPI)
    cpi = lambda y: US_CPI[min(int(y), last)]  # noqa: E731
    return np.array([cpi(base_year) / cpi(y) for y in years])
