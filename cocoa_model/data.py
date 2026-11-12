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
    df = df.where(df > -900)
    # derived daily series
    es = 0.6108 * np.exp(17.27 * df["tmax"] / (df["tmax"] + 237.3))
    df["vpd"] = es * (1 - df["rh"] / 100)  # kPa, afternoon vapour pressure deficit
    pet = 0.0135 * ((df["tmax"] + df["tmin"]) / 2 + 17.8) * df["rad"] / 2.45  # mm/day
    df["wbal"] = df["rain"] - pet
    df["heavy"] = (df["rain"] >= 20).where(df["rain"].notna()).astype(float)
    df["heat"] = (df["tmax"] > 33).where(df["tmax"].notna()).astype(float)
    dry = (df["rain"] < 1).astype(int)
    df["dryrun"] = dry.groupby((dry == 0).cumsum()).cumsum()  # running dry-spell length
    return df


def weather_monthly(refresh: bool = False) -> pd.DataFrame:
    """Monthly country-average weather: rain / wbal (mm/month), tmax, tmin, rh, soil, rad,
    wind, vpd, heavy-rain days, heat days, longest dry spell. Months need >=25 valid days."""
    path, ok = _cached("weather_monthly_v2.csv", 24, refresh)
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
        days = g["rain"].size()
        m["n_days"] = g["rain"].count()
        for c in ("rain", "wbal", "heavy", "heat"):
            m[c] = m[c] * days  # daily mean × days in month
        m["dryrun"] = g["dryrun"].max()
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


PINK_COLS = {"Cocoa": "cocoa", "Sugar, world": "sugar", "Palm oil": "palm", "Urea": "urea",
             "Gold": "gold", "Rubber, RSS3": "rubber"}


def pink_sheet(refresh: bool = False, cols: dict[str, str] | None = None,
               cache: str = "pink_sheet.csv") -> pd.DataFrame:
    """World Bank Pink Sheet monthly nominal prices (native units), PeriodIndex(M)."""
    cols = cols or PINK_COLS
    path, ok = _cached(cache, 24, refresh)
    if ok:
        d = pd.read_csv(path, index_col=0)
        d.index = pd.PeriodIndex(d.index, freq="M")
        return d
    try:
        html = _get(WB_PAGE, tries=2, timeout=60).text
        url = re.search(r"https://thedocs\.worldbank\.org[^\"']*CMO-Historical-Data-Monthly\.xlsx", html).group(0)
    except Exception:
        url = WB_FALLBACK
    raw = pd.read_excel(io.BytesIO(_get(url).content), sheet_name="Monthly Prices", header=None)
    hdr = raw.index[raw.apply(lambda r: r.astype(str).str.fullmatch("Cocoa").any(), axis=1)][0]
    names = raw.loc[hdr].astype(str).str.strip()
    body = raw[raw[0].astype(str).str.fullmatch(r"\d{4}M\d{2}")]
    out = pd.DataFrame({short: pd.to_numeric(body[names.index[names == long][0]], errors="coerce")
                        for long, short in cols.items()})
    out.index = pd.PeriodIndex(body[0].str.replace("M", "-"), freq="M")
    out.to_csv(path)
    return out


def price_monthly(refresh: bool = False) -> pd.Series:
    """Monthly cocoa price in US$/tonne, PeriodIndex(M). World Bank Pink Sheet (ICCO daily
    price) extended with monthly averages of the ICE NY front-month future where the
    Pink Sheet has not been published yet."""
    path, ok = _cached("price_monthly.csv", 24, refresh)
    if ok:
        s = pd.read_csv(path, index_col=0)["price"]
        s.index = pd.PeriodIndex(s.index, freq="M")
        return s
    wb = (pink_sheet(refresh)["cocoa"] * 1000.0).dropna()  # $/kg -> $/t
    r = _yahoo("CC=F", period1=0, period2=int(time.time()), interval="1d")
    fut = pd.Series(r["indicators"]["quote"][0]["close"],
                    index=pd.to_datetime(r["timestamp"], unit="s")).dropna()
    fm = fut.groupby(fut.index.to_period("M")).mean()
    s = pd.concat([wb, fm[fm.index > wb.index[-1]]]).rename("price")
    s.to_csv(path)
    return s


# ------------------------------------------------------------- extra data (v2 candidates)
PSL = "https://psl.noaa.gov/data/correlation/{}.data"
INDEX_URLS = {"tsa": PSL.format("tsa"), "tna": PSL.format("tna"), "nao": PSL.format("nao"),
              "qbo": PSL.format("qbo"),
              "iod": "https://psl.noaa.gov/gcos_wgsp/Timeseries/Data/dmi.had.long.data"}
SUNSPOT_URL = "https://www.sidc.be/SILSO/INFO/snmtotcsv.php"
GDP_URL = "https://api.worldbank.org/v2/country/WLD/indicator/NY.GDP.MKTP.KD.ZG?format=json&per_page=200"
FAO_REGION_URL = "https://bulks-faostat.fao.org/production/Production_Crops_Livestock_E_{}.zip"


def climate_indices(refresh: bool = False) -> pd.DataFrame:
    """Monthly climate indices + sunspot number, indexed by (year, month)."""
    path, ok = _cached("climate_indices.csv", 24 * 7, refresh)
    if ok:
        return pd.read_csv(path, index_col=[0, 1])
    cols = {}
    for name, url in INDEX_URLS.items():
        rows = {}
        for line in _get(url, timeout=60).text.splitlines()[1:]:
            p = line.split()
            if len(p) == 13 and re.fullmatch(r"(18|19|20)\d\d", p[0]):
                for m, v in enumerate(p[1:], 1):
                    if abs(float(v)) < 90:
                        rows[(int(p[0]), m)] = float(v)
        cols[name] = pd.Series(rows)
    sun = {}
    for line in _get(SUNSPOT_URL, timeout=60).text.splitlines():
        p = line.split(";")
        if len(p) >= 4 and float(p[3]) >= 0:
            sun[(int(p[0]), int(p[1]))] = float(p[3])
    cols["sunspots"] = pd.Series(sun)
    out = pd.DataFrame(cols)
    out.index.names = ["year", "month"]
    out = out[out.index.get_level_values(0) >= 1950]
    out.to_csv(path)
    return out


def world_gdp_growth(refresh: bool = False) -> pd.Series:
    """World real GDP growth, % per calendar year (World Bank)."""
    path, ok = _cached("world_gdp.csv", 24 * 30, refresh)
    if ok:
        return pd.read_csv(path, index_col=0)["gdp"]
    rows = _get(GDP_URL, timeout=60).json()[1]
    s = pd.Series({int(r["date"]): r["value"] for r in rows if r["value"] is not None}, name="gdp").sort_index()
    s.to_csv(path)
    return s


def row_production(refresh: bool = False) -> pd.Series:
    """Cocoa production of all countries outside the four modelled ones (tonnes, FAOSTAT)."""
    path, ok = _cached("fao_cocoa_row.csv", 24 * 30, refresh)
    if ok:
        return pd.read_csv(path, index_col=0)["row"]
    total = None
    for region in ("Africa", "Americas", "Asia", "Oceania"):
        z = zipfile.ZipFile(io.BytesIO(_get(FAO_REGION_URL.format(region)).content))
        name = next(n for n in z.namelist() if n.endswith(f"_{region}_NOFLAG.csv"))
        d = pd.read_csv(z.open(name), encoding="utf-8")
        d = d[(d["Item"] == "Cocoa beans") & (d["Element"] == "Production")
              & ~d["Area"].isin(REGIONS) & (d["Area Code"] < 5000) & (d["Area Code"] != 351)]
        ycols = [c for c in d.columns if re.fullmatch(r"Y\d{4}", c)]
        t = d[ycols].sum()
        total = t if total is None else total.add(t, fill_value=0)
    total.index = [int(c[1:]) for c in total.index]
    total = total.rename("row")
    total.to_csv(path)
    return total


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


def futures_daily(refresh: bool = False) -> pd.Series:
    """Daily close of the ICE NY front-month cocoa future (continuous, not roll-adjusted), 2000+."""
    path, ok = _cached("futures_daily.csv", 24, refresh)
    if ok:
        s = pd.read_csv(path, index_col=0, parse_dates=True)["close"]
        return s
    r = _yahoo("CC=F", period1=0, period2=int(time.time()), interval="1d")
    s = pd.Series(r["indicators"]["quote"][0]["close"],
                  index=pd.to_datetime(r["timestamp"], unit="s").normalize(), name="close").dropna()
    s = s[~s.index.duplicated(keep="last")]
    s.to_csv(path)
    return s
