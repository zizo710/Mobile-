"""Markdown report + charts for the copper model."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from cocoa_model.hedged import VOL_MARKUP, VOL_WINDOW  # noqa: E402
from cocoa_model.report import AQUA, BLUE, INK, INK2, ORANGE, SURFACE, _md_table  # noqa: E402

from . import model  # noqa: E402
from .data import LB_PER_TONNE  # noqa: E402
from .pipeline import MAIN, NOREV, TEST, Result  # noqa: E402

YELLOW = "#eda100"


def chart_price(r: Result, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.4))
    f = r.fut[r.fut.index >= "2005-01-01"]
    ax.plot(f.index, f.values, color=BLUE, linewidth=1.5, label="Front-month future")
    x = (r.live.asof + model.H).to_timestamp()
    ax.errorbar([x], [r.fair], yerr=[[r.fair - r.band68[0]], [r.band68[1] - r.fair]], color=ORANGE, fmt="o",
                markersize=7, capsize=3, elinewidth=2, label=f"Fair value in 12 months: ${r.fair:.2f} ±1σ")
    ax.plot([x + pd.Timedelta(days=120)], [r.fut12], marker="D", color=INK, markersize=7, linestyle="none",
            markeredgecolor=SURFACE, markeredgewidth=1.5, label=f"{r.fut12_contract} future: ${r.fut12:.2f}")
    ax.set_ylim(0)
    ax.yaxis.set_major_formatter(lambda y, _: f"${y:.0f}")
    ax.set_ylabel("US$ per lb")
    ax.set_title("COMEX copper, model fair value and the futures market")
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def chart_equity(r: Result, path: Path) -> None:
    eq = r.bt.equity
    series = ((f"{MAIN}, unhedged", BLUE, "Model long/short"), (r.bt.headline, AQUA, "Model long/short + 15% OTM options"),
              ("Always long, unhedged", ORANGE, "Always long"), ("Always long + puts 15% OTM", YELLOW, "Always long + 15% OTM puts"))
    fig, ax = plt.subplots(figsize=(9, 4.6))
    for name, colour, label in series:
        e = eq[name].dropna()
        ax.plot(e.index, e, color=colour, label=label, linewidth=1.6)
        ax.annotate(f"{e.iloc[-1]:.1f}×", (e.index[-1], e.iloc[-1]), xytext=(5, 0), textcoords="offset points",
                    va="center", color=INK2, fontsize=9)
    ax.set_yscale("log")
    ax.set_yticks([0.1, 0.25, 0.5, 1, 2, 4, 8], ["0.1×", "0.25×", "0.5×", "1×", "2×", "4×", "8×"])
    ax.minorticks_off()
    ax.axhline(1, color=INK2, linewidth=0.8)
    ax.set_ylabel("Growth of 1 (log scale)")
    ax.set_title("Copper backtest: growth of 1, with and without tail options")
    ax.legend(loc="lower left")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def chart_years(r: Result, path: Path) -> None:
    y = r.bt.yearly
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.set_axisbelow(True)
    w = 0.38
    ax.bar(y.index - w / 2, y["Unhedged"] * 100, width=w, color=BLUE, label="Model long/short", edgecolor=SURFACE)
    ax.bar(y.index + w / 2, y["Always long"] * 100, width=w, color=ORANGE, label="Always long", edgecolor=SURFACE)
    ax.axhline(0, color=INK2, linewidth=0.8)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:+.0f}%")
    ax.set_title("Calendar-year returns: the model fought the 2003–2010 China boom")
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _fmt(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    f = {"Return / year": "{:+.1%}", "Volatility": "{:.0%}", "Sharpe": "{:.2f}", "t-stat": "{:.1f}",
         "Hit rate": "{:.0%}", "Worst quarter": "{:+.0%}", "Max drawdown": "{:+.0%}",
         "Premium / year": "{:.1%}", "Option payoff / year": "{:.1%}"}
    out = pd.DataFrame({c: df[c].map(f[c].format) for c in cols}, index=df.index)
    for c in ("Premium / year", "Option payoff / year"):
        if c in out:
            out[c] = out[c].where(df[c] != 0, "–")
    return out


def build(r: Result, outdir: Path) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    chart_price(r, outdir / "copper_price_fair_value.png")
    chart_equity(r, outdir / "copper_backtest_equity.png")
    chart_years(r, outdir / "copper_backtest_years.png")
    lv, wf, bt, q = r.live, r.wf[MAIN], r.bt, r.bt.quote
    s, h = bt.stats, bt.hedge_stats
    m, al = s.loc[MAIN], s.loc["Always long (benchmark)"]
    hu, hh = h.loc[f"{MAIN}, unhedged"], h.loc[bt.headline]
    lu, lh = h.loc["Always long, unhedged"], h.loc["Always long + puts 15% OTM"]

    def card(names, picks):
        rows = []
        for n in names:
            rows.append({"Driver": model.LABELS[n],
                         "Group": {**model.CANDIDATES, **model.PLACEBO}[n][1],
                         "Correlation": f"{r.live_test.scorecard.loc[n, 'r']:+.2f}",
                         "Forecast error alone": f"{r.live_test.scorecard.loc[n, 'd_sse']:+.0%}",
                         "Chosen (share of years)": f"{picks[n].mean():.0%}" if picks[n].any() else "never",
                         "In current model": "**yes**" if n in lv.selected else "no"})
        return pd.DataFrame(rows)

    coef = pd.DataFrame({"Coefficient": lv.coef.map("{:+.3f}".format)})
    coef["Latest value"] = [""] + [f"{v:+.2f}" for v in lv.inputs]
    coef["Effect on forecast"] = [""] + [f"{v:+.1%}" for v in lv.contrib]
    coef.index = ["Constant"] + [model.LABELS[n] for n in lv.selected]
    coef.index.name = "Term"

    skill = pd.DataFrame({k: {"Out-of-sample R²": f"{w.r2:+.2f}", "Correlation": f"{w.corr:+.2f}",
                              "Direction right": f"{w.hit:.0%}", "Forecast error (1σ)": f"{w.rmse:.0%}"}
                          for k, w in r.wf.items()}).T
    skill.index.name = "Version"

    st = _fmt(s, ["Return / year", "Volatility", "Sharpe", "t-stat", "Hit rate", "Worst quarter", "Max drawdown"])
    st.index.name = "Strategy"
    ht = _fmt(h, ["Return / year", "Volatility", "Sharpe", "Worst quarter", "Max drawdown", "Premium / year",
                  "Option payoff / year"])
    ht.index.name = "Strategy"
    sens = _fmt(bt.markup_sens, ["Return / year", "Sharpe", "Premium / year"])
    sens.index.name = "Implied vol ÷ realised vol"

    curve = r.curve.iloc[[0, 2, 5, 8, 11, len(r.curve) - 1]] if len(r.curve) > 12 else r.curve
    curve = pd.DataFrame({"Contract": curve["contract"], "Expiry": curve["expiry"].astype(str),
                          "US$/lb": curve["price"].map("{:.3f}".format),
                          "US$/t": (curve["price"] * LB_PER_TONNE).map("{:,.0f}".format)})
    yr = bt.yearly
    boom = yr.loc[2003:2010]
    placebo_picks = r.wf[TEST].picks[list(model.PLACEBO)].mean()
    pt = s.loc[TEST]
    fc = lv.forecast
    side = "long" if fc > 0 else "short"
    active = abs(fc) > 0.05
    n_tr = len(bt.trades)
    asof = r.curve["asof"].max()

    md = f"""# Copper: drivers, fair value and a futures strategy with tail options

*Run date {r.asof:%d %b %Y} · futures as of {asof:%d %b %Y %H:%M} UTC · model data to {lv.asof.strftime("%b %Y")}*

## Verdict

**Copper futures look roughly fairly valued, but this model has no proven ability to forecast
copper, so that verdict carries little weight.** The model's fair value twelve months out is
${r.fair:.2f}/lb (${r.fair * LB_PER_TONNE:,.0f}/t; 68% band ${r.band68[0]:.2f} – ${r.band68[1]:.2f}); the {r.fut12_contract} future is
${r.fut12:.2f}/lb, {abs(r.gap):.1%} {"below" if r.gap < 0 else "above"} it (z = {r.z:+.2f}). The front month is ${r.spot:.2f}/lb.

Three findings matter more than the valuation:

1. **No forecasting skill.** Run forward through history with no hindsight, the model's
   12-month forecasts were worse than assuming no change (out-of-sample R² {wf.r2:+.2f}).
2. **The long/short strategy lost money**: {m["Return / year"]:+.1%} a year (Sharpe {m["Sharpe"]:.2f}) over {n_tr} quarterly trades, against
   {al["Return / year"]:+.1%} (Sharpe {al["Sharpe"]:.2f}) for simply holding copper.
3. **Tail options did their job on a plain long position.** Buying 15% out-of-the-money puts each
   quarter cut the worst quarter from {lu["Worst quarter"]:+.0%} to {lh["Worst quarter"]:+.0%} and the maximum drawdown from {lu["Max drawdown"]:+.0%} to
   {lh["Max drawdown"]:+.0%}, at a cost of {lu["Return / year"] - lh["Return / year"]:.1%} a year in return.

![Price and fair value](copper_price_fair_value.png)

## How this differs from the cocoa model

Copper has no harvest, so the weather → crop step is replaced by {len(model.CANDIDATES)} candidate drivers in
five groups: demand (leading indicators, GDP), financial conditions (dollar, yields, equities),
relative value against other commodities, copper's own price history, and supply (mine output,
ENSO disruption risk). The target is the change in the real copper price over the next 12 months.
Selection, walk-forward testing and option pricing follow the cocoa model.

## 1. Drivers

"Correlation" is with the next 12 months' real price change (1972 onward). "Forecast error alone"
is the change in out-of-sample squared error when the driver is used on its own; negative is
better. "Chosen" is how often the walk-forward search picked it.

{_md_table(card(list(model.CANDIDATES), r.wf[MAIN].picks), index=False)}

Only the G20 leading indicator lowers forecast error on its own, and it is a contrarian signal:
when the business cycle is running hot, copper tends to fall over the following year.

### Current model

{_md_table(coef)}

Forecast real price change over the next 12 months: **{fc:+.1%}**.

### Honest skill (walk-forward, {model.FIRST_TRADE}–today)

{_md_table(skill)}

Every version is worse than a no-change forecast. The search kept choosing the leading indicator
because it had worked before 2000, and the relationship then failed during the China-driven boom.

### Placebo test

Sunspots, the stratospheric wind cycle and the cocoa price were offered to the search as a check.

{_md_table(card(list(model.PLACEBO), r.wf[TEST].picks), index=False)}

The walk-forward search picked {", ".join(f"{model.LABELS[k].split(' (')[0].lower()} in {v:.0%} of years" for k, v in placebo_picks.items() if v > 0)}.
The version with placebos even shows a positive backtest ({pt["Return / year"]:+.1%} a year, Sharpe {pt["Sharpe"]:.2f}),
which is luck: nothing connects stratospheric winds to copper. A search over this many variables on
this little data finds patterns whether or not they exist, and that applies equally to the
conventional drivers above.

## 2. Long/short backtest

Each quarter (first trading day of February, May, August, November) the position follows the sign
of the walk-forward forecast and is held three months in the front-month COMEX future.

{_md_table(st)}

![Yearly](copper_backtest_years.png)

- **The model fought the trend.** From 2003 to 2010 it lost in {int((boom["Unhedged"] < 0).sum())} of {len(boom)} years while copper rose in {int((boom["Always long"] > 0).sum())}.
  A model built on mean reversion and the business cycle was short through most of the China boom.
- **Removing the revised indicators does not help** (Sharpe {s.loc[NOREV, "Sharpe"]:.2f}). OECD leading indicators are
  revised after publication, so the main version is, if anything, flattered.
- **Copper has had a strong upward drift** ({al["Return / year"]:+.1%} a year since {model.FIRST_TRADE}), so any strategy that is
  often short starts well behind.

## 3. Tail options

Each position buys one three-month option: a put under a long, a call over a short.

{_md_table(ht)}

![Equity](copper_backtest_equity.png)

- **On the model's long/short**, options cap the worst quarter ({hu["Worst quarter"]:+.0%} to {hh["Worst quarter"]:+.0%}) and lower volatility,
  and they roughly pay for themselves ({hh["Premium / year"]:.1%} a year in premium, {hh["Option payoff / year"]:.1%} back) because the
  model was so often on the wrong side of big moves. They do not turn a losing signal into a
  winning one.
- **On a plain long position**, 15% OTM puts cost {lh["Premium / year"]:.1%} a year and returned {lh["Option payoff / year"]:.1%}. The Sharpe
  ratio is about the same ({lu["Sharpe"]:.2f} to {lh["Sharpe"]:.2f}) and the drawdown is clearly shallower. This is the one
  structure here I would call useful.

Sensitivity of the model + 15% OTM options to the option-pricing assumption:

{_md_table(sens)}

## 4. Tracking: current position and what protection costs

- **Signal:** forecast {fc:+.1%} over 12 months, so nominally {side}; {"above" if active else "below"} the 5% conviction
  threshold, so the practical position is **{side if active else "flat"}**.
- **Three-month tail options today**, with the front month at ${q["price"]:.2f}/lb and {VOL_WINDOW}-day realised
  volatility of {q["realised_vol"]:.0%} (assumed implied {q["implied_vol"]:.0%}), as a share of notional:

| Strike distance | Put | Call |
|---|---|---|
| 10% OTM | {q["put_10%"]:.2%} | {q["call_10%"]:.2%} |
| 15% OTM | {q["put_15%"]:.2%} | {q["call_15%"]:.2%} |
| 20% OTM | {q["put_20%"]:.2%} | {q["call_20%"]:.2%} |

These are model estimates, not quotes. Rerun `python -m copper_model` to refresh the signal, the
fair value and these costs.

## Futures curve

{_md_table(curve, index=False)}

## Caveats

- **Option prices are modelled**: Black-76, implied volatility = {VOL_WINDOW}-day realised × {VOL_MARKUP}, no skew, no
  bid-ask spread. Copper puts usually carry skew, so downside protection is probably under-priced.
- **Futures returns** use the front-month continuous contract with no roll adjustment or costs.
- **Supply data is thin.** World mine output is annual and the detailed USGS series ends in 2020
  (later years are approximate summary figures). Exchange inventories, treatment charges and
  Chinese import data, which practitioners rely on, are not freely available.
- **Prices before 2000 are monthly averages** (World Bank), which smooths them; trading results
  use daily futures from {model.FIRST_TRADE}.
- {n_tr} quarterly trades over one commodity cycle. Not investment advice.
"""
    out = outdir / "copper_report.md"
    out.write_text(md)
    return out
