"""Static configuration: growing regions, weather windows, deflator."""
from __future__ import annotations

from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parent / "data_cache"
FIRST_WEATHER_YEAR = 1981  # NASA POWER (MERRA-2) starts here

# FAOSTAT area name -> representative points across each country's cocoa belt (lat, lon)
REGIONS: dict[str, dict[str, tuple[float, float]]] = {
    "Côte d'Ivoire": {
        "Soubré": (5.78, -6.60),
        "Daloa": (6.88, -6.45),
        "Divo": (5.84, -5.36),
        "Abengourou": (6.73, -3.49),
        "Duékoué": (6.74, -7.35),
    },
    "Ghana": {
        "Sefwi Wiawso": (6.20, -2.49),
        "Kumasi": (6.69, -1.62),
        "Tarkwa": (5.30, -1.99),
        "Goaso": (6.80, -2.52),
        "Koforidua": (6.09, -0.26),
    },
    "Nigeria": {
        "Akure": (7.25, 5.20),
        "Ile-Ife": (7.48, 4.56),
        "Ikom": (5.96, 8.71),
    },
    "Cameroon": {
        "Kumba": (4.64, 9.45),
        "Bafia": (4.75, 11.23),
        "Ebolowa": (2.90, 11.15),
    },
}
SHORT = {"Côte d'Ivoire": "CIV", "Ghana": "GHA", "Nigeria": "NGA", "Cameroon": "CMR"}

POWER_PARAMS = {
    "PRECTOTCORR": "rain",  # mm/day
    "T2M_MAX": "tmax",  # °C
    "RH2M": "rh",  # %
    "GWETROOT": "soil",  # root-zone soil wetness, 0-1
    "ALLSKY_SFC_SW_DWN": "rad",  # MJ/m²/day
    "T2M_MIN": "tmin",  # °C
    "WS2M": "wind",  # m/s
}

# Weather windows relative to harvest year H (crop year Oct(H-1)..Sep(H); FAOSTAT year H).
# (name, [(year offset, month), ...], agronomic meaning)
WINDOWS: list[tuple[str, list[tuple[int, int]], str]] = [
    ("dry0", [(-2, 11), (-2, 12), (-1, 1), (-1, 2), (-1, 3)],
     "Dry season before flowering (Nov H-2 – Mar H-1): tree stress / carry-over"),
    ("rains1", [(-1, 4), (-1, 5), (-1, 6), (-1, 7)],
     "Main rains (Apr–Jul H-1): flowering and pod set of the main crop"),
    ("aug", [(-1, 8)], "Little dry season (Aug H-1): pod filling"),
    ("rains2", [(-1, 9), (-1, 10)],
     "Short rains (Sep–Oct H-1): pod maturation; excess → black pod"),
    ("dry1", [(-1, 11), (-1, 12), (0, 1), (0, 2), (0, 3)],
     "Harmattan dry season (Nov H-1 – Mar H): main-crop tail, mid-crop set"),
    ("rains3", [(0, 4), (0, 5), (0, 6)], "Apr–Jun H: mid-crop development"),
    ("enddry0", [(-1, 2), (-1, 3)], "Feb–Mar H-1: end of the dry season, moisture at season start"),
    ("season", [(-1, m) for m in range(4, 11)], "Apr–Oct H-1: whole main-crop growing season"),
]

# (feature name, variable, window, squared?)
FEATURES: list[tuple[str, str, str, bool]] = [
    ("rain_dry0", "rain", "dry0", False),
    ("tmax_dry0", "tmax", "dry0", False),
    ("rain_rains1", "rain", "rains1", False),
    ("rain_rains1_sq", "rain", "rains1", True),
    ("soil_rains1", "soil", "rains1", False),
    ("rain_aug", "rain", "aug", False),
    ("rain_rains2", "rain", "rains2", False),
    ("rain_rains2_sq", "rain", "rains2", True),
    ("rad_rains2", "rad", "rains2", False),
    ("rain_dry1", "rain", "dry1", False),
    ("tmax_dry1", "tmax", "dry1", False),
    ("rh_dry1", "rh", "dry1", False),
    ("rain_rains3", "rain", "rains3", False),
]
# Additional weather candidates: (name, monthly variable, window, aggregation)
EXTRA_WEATHER: list[tuple[str, str, str, str]] = [
    ("dryspell_rains1", "dryrun", "rains1", "max"),
    ("heavy_rains2", "heavy", "rains2", "sum"),
    ("vpd_dry1", "vpd", "dry1", "mean"),
    ("wind_dry1", "wind", "dry1", "mean"),
    ("tmin_rains1", "tmin", "rains1", "mean"),
    ("wbal_season", "wbal", "season", "sum"),
    ("heatdays_dry0", "heat", "dry0", "sum"),
    ("soil_enddry0", "soil", "enddry0", "mean"),
]
SUM_VARS = {"rain", "heavy", "heat", "wbal"}

ONI_MONTHS = [(-1, m) for m in (6, 7, 8, 9, 10)]  # ENSO state Jun–Oct of H-1

# US CPI-U annual average (1982-84=100), BLS. 2025-26 are approximations.
US_CPI = {
    1960: 29.6, 1961: 29.9, 1962: 30.2, 1963: 30.6, 1964: 31.0, 1965: 31.5, 1966: 32.4,
    1967: 33.4, 1968: 34.8, 1969: 36.7, 1970: 38.8, 1971: 40.5, 1972: 41.8, 1973: 44.4,
    1974: 49.3, 1975: 53.8, 1976: 56.9, 1977: 60.6, 1978: 65.2, 1979: 72.6, 1980: 82.4,
    1981: 90.9, 1982: 96.5, 1983: 99.6, 1984: 103.9, 1985: 107.6, 1986: 109.6, 1987: 113.6,
    1988: 118.3, 1989: 124.0, 1990: 130.7, 1991: 136.2, 1992: 140.3, 1993: 144.5,
    1994: 148.2, 1995: 152.4, 1996: 156.9, 1997: 160.5, 1998: 163.0, 1999: 166.6,
    2000: 172.2, 2001: 177.1, 2002: 179.9, 2003: 184.0, 2004: 188.9, 2005: 195.3,
    2006: 201.6, 2007: 207.3, 2008: 215.3, 2009: 214.5, 2010: 218.1, 2011: 224.9,
    2012: 229.6, 2013: 233.0, 2014: 236.7, 2015: 237.0, 2016: 240.0, 2017: 245.1,
    2018: 251.1, 2019: 255.7, 2020: 258.8, 2021: 271.0, 2022: 292.7, 2023: 304.7,
    2024: 313.7, 2025: 322.3, 2026: 331.0, 2027: 339.5,
}

# ICE NY cocoa contract months
FUTURES_MONTHS = {"H": 3, "K": 5, "N": 7, "U": 9, "Z": 12}
