"""Markdown report + charts for a pipeline run."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

from . import candidates as cand  # noqa: E402
from . import selection  # noqa: E402
from .config import EXTRA_WEATHER, REGIONS, SHORT, WINDOWS  # noqa: E402
from .data import real_factor  # noqa: E402
from .pipeline import Result  # noqa: E402

SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE, AQUA, NEUTRAL = "#2a78d6", "#eb6834", "#1baf7a", "#f0efec"
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
FEATURE_LABELS.update(cand.LABELS)


def _season(h: int) -> str:
    return f"{h - 1}/{h % 100:02d}"


def chart_correlations(r: Result, path: Path) -> None:
    rows = [i for i in r.correlations.index if i not in cand.YIELD_UNUSUAL]
    c = r.correlations.loc[rows].rename(columns=SHORT)
    used = {(v, SHORT[k]) for k, y in r.main.ysel.items() if y.used for v in y.selected}
    fig, ax = plt.subplots(figsize=(9, 0.36 * len(c) + 1.6))
    ax.grid(False)
    im = ax.imshow(c.values, cmap=DIVERGING, vmin=-0.5, vmax=0.5, aspect="auto")
    ax.set_xticks(range(c.shape[1]), c.columns)
    ax.set_yticks(range(c.shape[0]), [FEATURE_LABELS[i] for i in c.index])
    for i, name in enumerate(c.index):
        for j, col in enumerate(c.columns):
            star = " ★" if (name, col) in used else ""
            ax.text(j, i, f"{c.values[i, j]:+.2f}{star}", ha="center", va="center", fontsize=8.5, color=INK,
                    fontweight="bold" if star else "normal")
    ax.set_xticks(np.arange(-.5, c.shape[1]), minor=True)
    ax.set_yticks(np.arange(-.5, c.shape[0]), minor=True)
    ax.grid(which="minor", color=SURFACE, linewidth=2)
    ax.tick_params(which="both", length=0)
    fig.suptitle("Candidate drivers vs cocoa output (deviation from trend)   ★ = used in that country's model",
                 x=0.02, ha="left", fontsize=11, fontweight="bold")
    cb = fig.colorbar(im, ax=ax, shrink=0.4, pad=0.02)
    cb.outline.set_visible(False)
    cb.set_label("Pearson r  (orange = lower output, blue = higher)")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def chart_supply(r: Result, path: Path) -> None:
    v = r.main
    fig, ax = plt.subplots(figsize=(9, 4.2))
    act = r.wa_hist[r.wa_hist.index >= v.wa_nested.index.min()] * 100
    ax.axhline(0, color=INK2, linewidth=0.8)
    ax.plot(act.index, act.values, color=BLUE, label="Actual (FAOSTAT)")
    ax.plot(v.wa_nested.index, v.wa_nested.values * 100, color=ORANGE, label="Model, out-of-sample")
    now = v.wa_nowcast * 100
    ax.plot(now.index, now.values, color=ORANGE, linestyle="none", marker="o", markersize=7,
            markeredgecolor=SURFACE, markeredgewidth=2, label="Nowcast")
    ax.set_ylabel("% deviation from trend")
    ax.set_xlabel("Harvest year (crop year ending)")
    ax.set_title(f"West African cocoa output vs trend (out-of-sample correlation {v.wa_corr:+.2f})")
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
    ax.errorbar([x], [v.fair_value], color=ORANGE, fmt="o", markersize=7,
                yerr=[[v.fair_value - v.band68[0]], [v.band68[1] - v.fair_value]],
                capsize=3, elinewidth=2, label=f"Fair value {_season(x)}: ${v.fair_value:,.0f} ±1σ")
    ax.plot([x + 0.5], [v.futures_strip], marker="D", color=INK, markersize=7, linestyle="none",
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


def _yield_card(r: Result, names: list[str], variant) -> pd.DataFrame:
    rows = []
    for n in names:
        row = {"Data point": FEATURE_LABELS[n]}
        for c in REGIONS:
            row[SHORT[c]] = f"{r.correlations.loc[n, c]:+.2f}"
        chosen = [SHORT[c] for c, y in variant.ysel.items() if n in y.selected]
        kept = [SHORT[c] for c, y in variant.ysel.items() if n in y.selected and y.used]
        row["Result"] = (f"**used ({', '.join(kept)})**" if kept else
                         f"picked ({', '.join(chosen)}) but model failed out of sample" if chosen else "rejected")
        rows.append(row)
    return pd.DataFrame(rows)


def _price_card(names: list[str], variant) -> pd.DataFrame:
    sc, ps = variant.psel.scorecard, variant.psel
    rows = []
    for n in names:
        res = ("**used**" if n in ps.selected else
               "picked in-sample, failed out of sample" if n in ps.bic_picks else "rejected")
        rows.append({"Data point": FEATURE_LABELS[n], "t-stat": f"{sc.loc[n, 't']:+.1f}",
                     "Forecast error change": f"{sc.loc[n, 'd_rmse']:+.1%}", "Result": res})
    return pd.DataFrame(rows)


def build(r: Result, outdir: Path) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    chart_correlations(r, outdir / "weather_yield_correlations.png")
    chart_supply(r, outdir / "west_africa_supply.png")
    chart_price(r, outdir / "price_fair_value.png")

    v, t = r.val, r.val.target_year
    m, b, x = r.main, r.base, r.test

    def val_row(name, var):
        q = var.val
        return {"Model": name, "Fair value": f"${q.fair_value:,.0f}",
                "68% band": f"${q.band68[0]:,.0f} – ${q.band68[1]:,.0f}",
                "Futures vs fair": f"{q.mispricing_pct:+.1%}", "z-score": f"{q.z:+.2f}", "Verdict": q.verdict}
    vt = pd.DataFrame([val_row("Per-country, original weather variables", b),
                       val_row("**+ 20 added data points (headline)**", m),
                       val_row("+ 5 unconventional variables (test)", x)])

    def skill_row(name, var):
        row = {"Model": name}
        for c in REGIONS:
            y = var.ysel[c]
            row[SHORT[c]] = f"{y.r2_nested:+.2f}" + ("" if y.used else " (not used)")
        row["W. Africa correlation"] = f"{var.wa_corr:+.2f}"
        row["Price forecast error"] = f"{var.psel.rmse_selected if var.psel.selected else var.psel.rmse_base:.3f}"
        return row
    from .yield_model import aggregate_shock
    pc = aggregate_shock(r.pooled.cv_pred.unstack("country")[list(REGIONS)], r.trend)
    pooled_corr = float(np.corrcoef(r.wa_hist.reindex(pc.index), pc)[0, 1])
    st = pd.DataFrame([{"Model": "First version (one pooled model)", **{SHORT[c]: "–" for c in REGIONS},
                        "W. Africa correlation": f"{pooled_corr:+.2f}", "Price forecast error": f"{b.psel.rmse_base:.3f}"},
                       skill_row("Per-country, original weather variables", b),
                       skill_row("**+ 20 added data points**", m),
                       skill_row("+ 5 unconventional (test)", x)])

    y_new = [e[0] for e in EXTRA_WEATHER] + ["tsa", "tna", "iod", "nao", "price_plant", "price_lag1", "urea_lag"]
    p_new = ["S_row", "gdp_lag", "sugar_lag", "palm_lag", "vol_lag"]
    p_clim = ["tsa", "tna", "iod", "nao", "oni"]

    used_new = [n for n in y_new if any(n in y.selected and y.used for y in m.ysel.values())]
    models = []
    for c in REGIONS:
        y = m.ysel[c]
        if y.used:
            terms = "; ".join(f"{FEATURE_LABELS[n]} ({y.coef[n] * 100:+.1f}% per σ)" for n in y.selected)
            models.append({"Country": c, "Honest R²": f"{y.r2_nested:+.2f}", "Drivers": terms})
        else:
            models.append({"Country": c, "Honest R²": f"{y.r2_nested:+.2f}", "Drivers": "none reliable – held at trend"})
    models = pd.DataFrame(models)

    used_vars = sorted({n for y in m.ysel.values() if y.used for n in y.selected},
                       key=list(r.feats.columns).index)
    cur = r.feats.xs(t, level="year")[used_vars].T.rename(columns=SHORT)
    cur.index = [FEATURE_LABELS[i] for i in cur.index]
    cur = cur.map(lambda q: "not yet observed" if pd.isna(q) else f"{q:+.1f}σ")
    cur.index.name = f"Inputs for {_season(t)}"

    now = (m.country_nowcast * 100).rename(columns=SHORT)
    now["W. Africa"] = m.wa_nowcast * 100
    now = now.map(lambda q: f"{q:+.1f}%")
    now.index = [_season(h) for h in now.index]
    now.index.name = "Crop year"

    names = {"const": "Constant", "S": "Supply shock, current crop", "S_lag": "Supply shock, previous crop",
             "lp_lag": "Lagged log real price", **FEATURE_LABELS}
    coefs = pd.DataFrame({"coef": v.ols.params.map(lambda q: f"{q:+.3f}"),
                          "t-stat": v.ols.tvalues.map(lambda q: f"{q:+.1f}")})
    coefs.index = [names[i] for i in coefs.index]
    coefs.index.name = "Term"

    curve = r.curve.assign(expiry=r.curve["expiry"].astype(str), price=r.curve["price"].map("${:,.0f}".format))
    curve = curve[["contract", "expiry", "price"]]

    lr = float(np.exp(-v.ols.params["const"] / v.ols.params["lp_lag"]))
    ov = (f"\n> Manual supply overrides applied: "
          f"{', '.join(f'{_season(k)} {q:+.1%}' for k, q in r.overrides.items())}\n" if r.overrides else "")
    windows = "\n".join(f"- **{n}** – {d}" for n, _, d in WINDOWS)
    asof = r.curve["asof"].max()
    sc = x.psel.scorecard
    n_sig = int((sc.loc[cand.PRICE_UNUSUAL, "t"].abs() > 1.5).sum())
    test_y = sorted({(n, SHORT[c]) for c, y in x.ysel.items() for n in y.selected if n in cand.YIELD_UNUSUAL})
    ci_drop = m.ysel["Côte d'Ivoire"].r2_nested - x.ysel["Côte d'Ivoire"].r2_nested

    md = f"""# West African cocoa: weather, harvest and futures valuation

*Run date {r.asof:%d %b %Y} · futures as of {asof:%d %b %Y %H:%M} UTC · target crop year {_season(t)} (Oct {t - 1} – Sep {t})*

## Verdict

**ICE New York cocoa futures for {_season(t)} average ${v.futures_strip:,.0f}/t; the model's fair value is
${v.fair_value:,.0f}/t (68% band ${v.band68[0]:,.0f} – ${v.band68[1]:,.0f}). The market is {v.verdict}
({v.mispricing_pct:+.1%} vs fair value, z = {v.z:+.2f}).** One standard deviation of the forecast is
about ±{v.sigma:.0%}, so the gap is not statistically meaningful.
{ov}
{_md_table(vt, index=False)}

![Price and fair value](price_fair_value.png)

## What the added data changed

{_md_table(st, index=False)}

Country columns are the honest out-of-sample R² of each country's output model ("nested"
leave-one-year-out: the variable search is repeated inside every held-out year, so the score is
not flattered by the search). A country model is used only if that R² exceeds
{selection.MIN_NESTED_R2:.2f}; otherwise the country is held at trend. "W. Africa correlation" is
predicted vs actual aggregate output, out of sample. "Price forecast error" is the RMSE of
one-year-ahead log price forecasts since {m.psel.first_oos} (no-change forecast: {m.psel.rmse_nochange:.3f}).

Two things improved the model:

1. **Fitting each country separately** instead of pooling. Weather responses differ by country, and
   pooling averaged them to nothing.
2. **{len(used_new)} of the 20 added data points** earned a place in a country model that works out of
   sample (table below): {", ".join(FEATURE_LABELS[n].split(",")[0].split(" (")[0].lower() for n in used_new)}.
   Côte d'Ivoire's out-of-sample R² goes from {b.ysel["Côte d'Ivoire"].r2_nested:+.2f} to {m.ysel["Côte d'Ivoire"].r2_nested:+.2f}; Cameroon's goes from
   {b.ysel["Cameroon"].r2_nested:+.2f} to {m.ysel["Cameroon"].r2_nested:+.2f}. Côte d'Ivoire is about 60% of the region's crop, so the West African
   correlation rises from {b.wa_corr:+.2f} to {m.wa_corr:+.2f}.

Ghana and Nigeria still have no usable weather model, and none of the added market variables
improved the price equation.

### Scorecard: 15 added data points tested on output

Numbers are each variable's correlation with that country's output deviation from trend.

{_md_table(_yield_card(r, y_new, m), index=False)}

### Scorecard: 5 added market data points, plus climate indices, tested on price

Each is added to the price equation on its own. "Forecast error change" is the change in
out-of-sample RMSE; negative is better.

{_md_table(_price_card(p_new + p_clim, m), index=False)}

## The test: 5 unconventional variables

Sunspots, the stratospheric quasi-biennial oscillation, the gold price, the rubber-to-cocoa price
ratio and the date of Easter were put through exactly the same procedure.

{_md_table(_yield_card(r, cand.YIELD_UNUSUAL, x), index=False)}

{_md_table(_price_card(cand.PRICE_UNUSUAL, x), index=False)}

**Result: none survives, and letting them compete makes the model worse.**
{("The search picked " + ", ".join(f"{FEATURE_LABELS[n]} ({c})" for n, c in test_y) + " for an output model that then failed out of sample. ") if test_y else "No unconventional variable was picked for any output model. "}With them in the candidate pool, Côte d'Ivoire's honest R² drops by {ci_drop:.2f} because the search
is distracted by chance fits in some folds. In the price equation {n_sig} of the 5 has |t| > 1.5 –
sunspots look as "significant" as world GDP growth or the Indian Ocean Dipole – yet none lowers
forecast error, and a price equation that searches over all of them forecasts far worse
(RMSE {x.psel.rmse_selected:.3f} vs {x.psel.rmse_base:.3f}). That is the useful lesson of the test: in a sample of ~{x.psel.n_obs} years, an in-sample
t-statistic near 2 is what noise looks like, which is why every variable here has to pass an
out-of-sample check before it is used. The headline model excludes all five.

## 1. Output models

Production: FAOSTAT, {r.prod.index.min()}–{r.prod.index.max()}. Target is each country's output deviation from its
HP trend. Weather: NASA POWER daily data averaged over {sum(len(p) for p in REGIONS.values())} cocoa-belt points, as
anomalies (σ) in these windows relative to harvest year H:

{windows}

{_md_table(models, index=False)}

![Correlations](weather_yield_correlations.png)

![Supply](west_africa_supply.png)

### Current season

{_md_table(cur)}

{_md_table(now)}

Inputs not yet observed are set to normal. The West African nowcast carries a ±{m.shock_sd:.0%} standard error.

## 2. Price model

Crop-year average real price (World Bank / ICCO, CPI-deflated), {int(v.ols.nobs)} years:
`Δlog P = a + b1·S + b2·S(-1) + g·log P(-1)` where S is West African output vs trend.

{_md_table(coefs)}

R² = {v.ols.rsquared:.2f}. A West African crop 10% below trend raises the real price by about
{-v.ols.params["S"] * 10:.0f}% that season and a further {-v.ols.params["S_lag"] * 10:.0f}% the next. Prices revert towards a long-run real
level of about ${lr:,.0f}/t at {-v.ols.params["lp_lag"]:.0%} a year. Out of sample this beats a no-change forecast by
{1 - m.psel.rmse_base / m.psel.rmse_nochange:.0%} in RMSE.

## 3. Futures curve

{_md_table(curve, index=False)}

Strip for {_season(t)} = average of contracts expiring Oct {t - 1} – Sep {t}: **${v.futures_strip:,.0f}/t**.
Last completed crop year ({_season(t - 1)}) averaged ${r.price_cy[t - 1]:,.0f}/t.

## Caveats

- Skill is modest: the output models explain roughly a fifth of the variation in Côte d'Ivoire and
  Cameroon and none in Ghana or Nigeria. Choosing which countries get a model is itself a
  selection step, so true skill is probably a little lower than shown.
- FAOSTAT is calendar-year, revised late and ends in {r.prod.index.max()}; output for later seasons is the
  model's nowcast, not reported data. Use `--shock` to feed in your own crop estimate.
- The most recent months of NASA POWER rainfall come from a near-real-time product and can be
  biased against the long history.
- Still missing: stocks, grindings, port arrivals, pod counts and positioning. These are the data
  most likely to improve the model further, and they are not freely available with long history.
- Forecast error is ±{v.sigma:.0%} (1σ) on a one-year view. Not investment advice.
"""
    out = outdir / "cocoa_report.md"
    out.write_text(md)
    return out
