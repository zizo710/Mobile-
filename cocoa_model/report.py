"""Markdown report + charts for a pipeline run."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

from .config import FEATURES, REGIONS, SHORT, WINDOWS  # noqa: E402
from .data import real_factor  # noqa: E402
from .pipeline import Result  # noqa: E402

SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE, NEUTRAL = "#2a78d6", "#eb6834", "#f0efec"
DIVERGING = LinearSegmentedColormap.from_list("div", [ORANGE, NEUTRAL, BLUE])

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "text.color": INK,
    "xtick.color": INK2, "ytick.color": INK2, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.8, "axes.spines.top": False, "axes.spines.right": False,
    "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "lines.linewidth": 2, "legend.frameon": False,
})

FEATURE_LABELS = {
    "rain_dry0": "Rain, prior dry season (Nov–Mar)", "tmax_dry0": "Max temp, prior dry season",
    "rain_rains1": "Rain, main rains (Apr–Jul)", "rain_rains1_sq": "Rain extremes, main rains",
    "soil_rains1": "Soil moisture, main rains", "rain_aug": "Rain, August",
    "rain_rains2": "Rain, short rains (Sep–Oct)", "rain_rains2_sq": "Rain extremes, short rains",
    "rad_rains2": "Sunshine, short rains", "rain_dry1": "Rain, harmattan (Nov–Mar)",
    "tmax_dry1": "Max temp, harmattan", "rh_dry1": "Humidity, harmattan",
    "rain_rains3": "Rain, Apr–Jun of harvest year", "oni": "ENSO (ONI, Jun–Oct)",
}


def _season(h: int) -> str:
    return f"{h - 1}/{h % 100:02d}"


def chart_correlations(r: Result, path: Path) -> None:
    c = r.ym.correlations.rename(columns=SHORT)
    fig, ax = plt.subplots(figsize=(8, 6.2))
    ax.grid(False)
    im = ax.imshow(c.values, cmap=DIVERGING, vmin=-0.5, vmax=0.5, aspect="auto")
    ax.set_xticks(range(c.shape[1]), c.columns)
    ax.set_yticks(range(c.shape[0]), [FEATURE_LABELS[i] for i in c.index])
    for i in range(c.shape[0]):
        for j in range(c.shape[1]):
            ax.text(j, i, f"{c.values[i, j]:+.2f}", ha="center", va="center", fontsize=9, color=INK)
    ax.set_xticks(np.arange(-.5, c.shape[1]), minor=True)
    ax.set_yticks(np.arange(-.5, c.shape[0]), minor=True)
    ax.grid(which="minor", color=SURFACE, linewidth=2)
    ax.tick_params(which="both", length=0)
    fig.suptitle("Seasonal weather vs cocoa output (deviation from trend)", x=0.02, ha="left",
                 fontsize=12, fontweight="bold")
    cb = fig.colorbar(im, ax=ax, shrink=0.6, pad=0.02)
    cb.outline.set_visible(False)
    cb.set_label("Pearson r  (orange = hurts output, blue = helps)")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def chart_supply(r: Result, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.2))
    act = r.wa_hist[r.wa_hist.index >= r.wa_cv.index.min()] * 100
    ax.axhline(0, color=INK2, linewidth=0.8)
    ax.plot(act.index, act.values, color=BLUE, label="Actual (FAOSTAT)")
    ax.plot(r.wa_cv.index, r.wa_cv.values * 100, color=ORANGE, label="Weather model, out-of-sample")
    now = r.wa_nowcast * 100
    ax.plot(now.index, now.values, color=ORANGE, linestyle="none", marker="o", markersize=7,
            markeredgecolor=SURFACE, markeredgewidth=2, label="Weather nowcast")
    ax.set_ylabel("% deviation from trend")
    ax.set_xlabel("Harvest year (crop year ending)")
    ax.set_title("West African cocoa output vs trend: actual and weather-predicted")
    ax.legend(loc="lower left", ncols=3)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def chart_price(r: Result, path: Path) -> None:
    v = r.val
    real = r.price_cy * real_factor(r.price_cy.index, v.target_year)
    real = real[real.index >= 1980]
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.plot(real.index, real.values, color=BLUE, label="Crop-year average price")
    x = v.target_year
    for val, lab, dx in ((v, "Fair value (supply model)", -0.25), (r.val_enso, "Fair value incl. ENSO", 0.25)):
        ax.errorbar([x + dx], [val.fair_value], color=ORANGE if dx < 0 else "#1baf7a", fmt="o", markersize=7,
                    yerr=[[val.fair_value - val.band68[0]], [val.band68[1] - val.fair_value]],
                    capsize=3, elinewidth=2, label=f"{lab}, ±1σ")
    ax.plot([x], [v.futures_strip], marker="D", color=INK, markersize=7, linestyle="none",
            markeredgecolor=SURFACE, markeredgewidth=1.5, label=f"Futures strip {_season(x)}: ${v.futures_strip:,.0f}")
    ax.set_ylim(0, real.max() * 1.25)
    ax.yaxis.set_major_formatter(lambda y, _: f"${y:,.0f}")
    ax.set_xlabel("Crop year ending")
    ax.set_ylabel(f"US$/tonne, {x} dollars")
    ax.set_title("Real cocoa price, model fair value and the futures market")
    ax.legend(loc="upper center", ncols=2)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _md_table(df: pd.DataFrame, index: bool = True) -> str:
    cols = ([df.index.name or ""] if index else []) + [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for idx, row in df.iterrows():
        cells = ([str(idx)] if index else []) + [str(x) for x in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def build(r: Result, outdir: Path) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    chart_correlations(r, outdir / "weather_yield_correlations.png")
    chart_supply(r, outdir / "west_africa_supply.png")
    chart_price(r, outdir / "price_fair_value.png")

    v, ve, ym, t = r.val, r.val_enso, r.ym, r.val.target_year
    wa_corr = float(np.corrcoef(r.wa_hist.reindex(r.wa_cv.index), r.wa_cv)[0, 1])

    corr = r.ym.correlations.rename(columns=SHORT).copy()
    corr.index = [FEATURE_LABELS[i] for i in corr.index]
    corr = corr.map(lambda x: f"{x:+.2f}")
    corr.index.name = "Weather feature"

    cur = r.feats.xs(t, level="year")
    cur = cur[[n for n, _, _, sq in FEATURES if not sq and cur[n].notna().any()]].T.rename(columns=SHORT)
    cur.index = [FEATURE_LABELS[i] for i in cur.index]
    cur = cur.map(lambda x: f"{x:+.1f}σ")
    cur.index.name = f"Observed so far for {_season(t)}"

    now = (r.country_nowcast * 100).rename(columns=SHORT)
    now["W. Africa"] = r.wa_nowcast * 100
    now["weather observed"] = r.known_share
    now = now.apply(lambda c: c.map(lambda x: f"{x:.0%}") if c.name == "weather observed"
                    else c.map(lambda x: f"{x:+.1f}%"))
    now.index = [_season(h) for h in now.index]
    now.index.name = "Crop year"

    def coefs(val) -> pd.DataFrame:
        names = {"const": "Constant", "S": "Supply shock, current crop", "S_lag": "Supply shock, previous crop",
                 "lp_lag": "Lagged log real price", "oni": "ENSO (ONI)"}
        d = pd.DataFrame({"coef": val.ols.params.map(lambda x: f"{x:+.3f}"),
                          "t-stat": val.ols.tvalues.map(lambda x: f"{x:+.1f}")})
        d.index = [names[i] for i in d.index]
        d.index.name = "Term"
        return d

    curve = r.curve.assign(expiry=r.curve["expiry"].astype(str), price=r.curve["price"].map("${:,.0f}".format))
    curve = curve[["contract", "expiry", "price"]]

    def val_row(name, x):
        return {"Model": name, "Fair value": f"${x.fair_value:,.0f}",
                "68% band": f"${x.band68[0]:,.0f} – ${x.band68[1]:,.0f}",
                "90% band": f"${x.band90[0]:,.0f} – ${x.band90[1]:,.0f}",
                "Futures vs fair": f"{x.mispricing_pct:+.1%}", "z-score": f"{x.z:+.2f}", "Verdict": x.verdict}
    vt = pd.DataFrame([val_row("Supply + mean reversion (headline)", v),
                       val_row("…plus ENSO term (sensitivity)", ve)])

    skill = ("no measurable out-of-sample skill" if ym.cv_r2 <= 0.02 else
             "weak out-of-sample skill" if ym.cv_r2 < 0.15 else "useful out-of-sample skill")
    lr = float(np.exp(-v.ols.params["const"] / v.ols.params["lp_lag"]))
    ov = (f"\n> Manual supply overrides applied: "
          f"{', '.join(f'{_season(k)} {x:+.1%}' for k, x in r.overrides.items())}\n" if r.overrides else "")
    windows = "\n".join(f"- **{n}** – {d}" for n, _, d in WINDOWS)
    asof = r.curve["asof"].max()

    md = f"""# West African cocoa: weather, harvest and futures valuation

*Run date {r.asof:%d %b %Y} · futures as of {asof:%d %b %Y %H:%M} UTC · target crop year {_season(t)} (Oct {t - 1} – Sep {t})*

## Verdict

**ICE New York cocoa futures for {_season(t)} average ${v.futures_strip:,.0f}/t; the model's fair value is
${v.fair_value:,.0f}/t (68% band ${v.band68[0]:,.0f} – ${v.band68[1]:,.0f}). The market is {v.verdict}
({v.mispricing_pct:+.1%} vs fair value, z = {v.z:+.2f}).**

Adding the current ENSO state (ONI {r.enso[t]:+.1f}) lifts fair value to ${ve.fair_value:,.0f}/t, which would make
futures {ve.verdict} ({ve.mispricing_pct:+.1%}, z = {ve.z:+.2f}). Neither gap is statistically
meaningful: one standard deviation of the forecast is about ±{v.sigma:.0%}.
{ov}
{_md_table(vt, index=False)}

![Price and fair value](price_fair_value.png)

## 1. Weather → harvest

Production data: FAOSTAT, {r.prod.index.min()}–{r.prod.index.max()}, for {", ".join(REGIONS)}.
Target is each country's output deviation from its HP trend. Weather is NASA POWER daily data
averaged over {sum(len(p) for p in REGIONS.values())} cocoa-belt points, turned into seasonal anomalies (σ) around the crop calendar:

{windows}

{_md_table(corr)}

![Correlations](weather_yield_correlations.png)

**Reading it.** A handful of links have the agronomically expected sign – a wet August and a sunny
Sep–Oct help Côte d'Ivoire, a hot prior dry season hurts Cameroon, short-rains rainfall helps Ghana –
but correlations are small (|r| mostly < 0.3 on ~{ym.n_obs // len(REGIONS)} years per country) and inconsistent
across countries.

**Predictive skill.** Pooled ridge regression ({ym.n_obs} country-years, leave-one-year-out):
cross-validated R² = {ym.cv_r2:+.2f}, correlation of predicted vs actual West African output = {wa_corr:+.2f}.
That is **{skill}**: on public annual data, seasonal weather does not forecast output deviations.
Structural drivers (swollen-shoot virus, ageing trees, farm-gate prices, smuggling, illegal mining
in Ghana) and FAOSTAT measurement noise dominate.

![Supply](west_africa_supply.png)

### Current season

{_md_table(cur)}

{_md_table(now)}

Windows not yet observed are set to climatology. Because the weather model has no proven skill, the
nowcast is deliberately shrunk to ≈ trend; it carries a ±{r.shock_sd:.0%} standard error.

## 2. Harvest → price

Crop-year average real price (World Bank / ICCO, CPI-deflated), {int(v.ols.nobs)} years:
`Δlog P = a + b1·S + b2·S(-1) + g·log P(-1)` where S is West African output vs trend.

{_md_table(coefs(v))}

R² = {v.ols.rsquared:.2f}. A West African crop 10% below trend raises the real price by about
{-v.ols.params["S"] * 10:.0f}% that season and a further {-v.ols.params["S_lag"] * 10:.0f}% the next. Prices revert towards a long-run real
level of about ${lr:,.0f}/t at {-v.ols.params["lp_lag"]:.0%} a year. In expanding-window tests since 1990
this beats a no-change forecast by roughly 10% in RMSE.

With ENSO added (R² = {ve.ols.rsquared:.2f}):

{_md_table(coefs(ve))}

El Niño years have tended to precede higher prices, but the term is not significant once supply
shocks are controlled for – treat it as an upside-risk scenario, not a forecast.

## 3. Futures curve

{_md_table(curve, index=False)}

Strip for {_season(t)} = average of contracts expiring Oct {t - 1} – Sep {t}: **${v.futures_strip:,.0f}/t**.
Last completed crop year ({_season(t - 1)}) averaged ${r.price_cy[t - 1]:,.0f}/t.

## Caveats

- The weather → output link is not established by this data; the valuation rests mainly on the
  price-vs-supply relationship and mean reversion, starting from last season's price.
- FAOSTAT is calendar-year, revised late and ends in {r.prod.index.max()}; output for later seasons is the
  model's near-trend nowcast, not reported data. Use `--shock` to feed in your own crop estimate.
- No stocks, grindings/demand, currency, farm-gate price policy or speculative positioning.
  ICCO stocks-to-grindings would be the most valuable addition.
- ICCO price history is spliced with ICE front-month futures for the latest months.
- Forecast error is ±{v.sigma:.0%} (1σ) on a one-year view. Not investment advice.
"""
    out = outdir / "cocoa_report.md"
    out.write_text(md)
    return out
