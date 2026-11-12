"""Markdown report + charts for the walk-forward backtest."""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

from .backtest import Backtest
from .report import AQUA, BLUE, INK, INK2, ORANGE, SURFACE, _md_table, _season


def chart_equity(bt: Backtest, path: Path) -> None:
    eq = (1 + bt.daily).cumprod()
    cols = [c for c in eq.columns if c.startswith(("Model long/short", "Model, trade only", "Always long"))]
    fig, ax = plt.subplots(figsize=(9, 4.4))
    for c, colour in zip(cols, (BLUE, AQUA, ORANGE)):
        ax.plot(eq.index, eq[c], color=colour, label=c)
        ax.annotate(f"{eq[c].iloc[-1]:.1f}×", (eq.index[-1], eq[c].iloc[-1]), xytext=(5, 0),
                    textcoords="offset points", va="center", color=INK2, fontsize=9)
    ax.set_yscale("log")
    ax.set_yticks([0.25, 0.5, 1, 2, 4, 8], ["0.25×", "0.5×", "1×", "2×", "4×", "8×"])
    ax.minorticks_off()
    ax.axhline(1, color=INK2, linewidth=0.8)
    ax.set_ylabel("Growth of 1 (log scale)")
    ax.set_title("Walk-forward backtest: model strategy vs always holding cocoa")
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def chart_trades(bt: Backtest, path: Path) -> None:
    t = bt.trades
    fig, ax = plt.subplots(figsize=(9, 4.2))
    colours = [BLUE if p > 0 else ORANGE for p in t["model_pos"]]
    ax.bar(t.index, t["model_ret"] * 100, color=colours, width=0.7, edgecolor=SURFACE, linewidth=1)
    ax.set_axisbelow(True)
    ax.axhline(0, color=INK2, linewidth=0.8)
    ax.set_xticks(t.index[::2], [_season(h) for h in t.index[::2]], rotation=45, ha="right")
    ax.yaxis.set_major_formatter(lambda y, _: f"{y:+.0f}%")
    ax.set_title("Return of each one-year trade (model long/short)")
    ax.legend(handles=[Patch(color=BLUE, label="Long"), Patch(color=ORANGE, label="Short")], loc="lower left")
    worst = t["model_ret"].idxmin()
    ax.annotate(f"short into the {_season(worst)} squeeze", (worst, t["model_ret"].min() * 100),
                xytext=(-190, 14), textcoords="offset points", color=INK,
                arrowprops={"arrowstyle": "-", "color": INK2})
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def build(bt: Backtest, latest_price: float, outdir: Path) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    chart_equity(bt, outdir / "backtest_equity.png")
    chart_trades(bt, outdir / "backtest_trades.png")
    t, s, c = bt.trades, bt.stats, bt.current

    pct = ["Average return / year", "Volatility", "Hit rate", "Compound return / year", "Max drawdown",
           "Worst year", "Best year"]
    st = s.copy()
    for col in pct:
        st[col] = s[col].map("{:+.0%}".format if col != "Hit rate" and col != "Volatility" else "{:.0%}".format)
    st["Trades"] = s["Trades"].astype(int)
    st["Sharpe"] = s["Sharpe"].map("{:.2f}".format)
    st["t-stat"] = s["t-stat"].map("{:.1f}".format)
    st = st[["Average return / year", "Volatility", "Sharpe", "t-stat", "Hit rate", "Compound return / year",
             "Max drawdown", "Worst year"]]
    st.index.name = "Strategy"

    log = pd.DataFrame({
        "Entry": t["entry_date"].dt.strftime("%d %b %Y"),
        "Futures": t["entry"].map("${:,.0f}".format),
        "Fair value": t["model_fair"].map("${:,.0f}".format),
        "Gap": t["model_gap"].map("{:+.0%}".format),
        "Position": t["model_pos"].map({1.0: "long", -1.0: "short"}),
        "Market move": t["long_ret"].map("{:+.0%}".format),
        "Trade return": t["model_ret"].map("{:+.0%}".format),
    })
    log.index = [_season(h) for h in t.index]
    log.index.name = "Crop year"

    m, al = s.loc["Model long/short"], s.loc["Always long (benchmark)"]
    ic = float(np.corrcoef(t["model_gap"], t["long_ret"])[0, 1])
    worst = t["model_ret"].idxmin()
    ex = t.drop(index=worst)["model_ret"]
    n_long = int((t["model_pos"] > 0).sum())
    longs, shorts = t[t["model_pos"] > 0]["model_ret"], t[t["model_pos"] < 0]["model_ret"]
    same = bool((t["model_pos"] == t["no_weather_pos"]).all())
    gap_now = float(np.log(c["model_fair"] / latest_price))
    thr = [k for k in s.index if k.startswith("Model, trade only")][0]
    n_thr = int((t["threshold_pos"] != 0).sum())
    side = lambda g: "long" if g > 0 else "short"  # noqa: E731

    md = f"""# Backtest: long/short cocoa futures on the model's signal

## Result

**The strategy made money but did not beat simply holding cocoa, and its edge is not statistically
distinguishable from zero.** Over {int(m["Trades"])} one-year trades ({_season(t.index[0])} to {_season(t.index[-1])}) it averaged
{m["Average return / year"]:+.0%} a year with a Sharpe ratio of {m["Sharpe"]:.2f} (t-stat {m["t-stat"]:.1f}); always being long averaged
{al["Average return / year"]:+.0%} with a Sharpe of {al["Sharpe"]:.2f}. Its worst trade, a short into the {_season(worst)} price
squeeze, lost {-t.loc[worst, "model_ret"]:.0%}.

{_md_table(st)}

![Equity](backtest_equity.png)

## What the numbers say

- **Direction was right {m["Hit rate"]:.0%} of the time**, against {al["Hit rate"]:.0%} for always-long. The {n_long} long trades
  averaged {longs.mean():+.0%}; the {len(shorts)} shorts averaged {shorts.mean():+.0%} ({shorts.drop(index=worst).mean():+.0%} excluding {_season(worst)}).
- **One trade dominates.** Without {_season(worst)} the strategy averages {ex.mean():+.0%} a year with a Sharpe of
  {ex.mean() / ex.std():.2f}. But a valuation model that shorts a market 5% above fair value has no defence
  against a supply squeeze, so that loss is a feature of the approach, not bad luck.
- **The size of the gap carries little information.** The correlation between the model's gap and
  the following year's price move is {ic:+.2f}. Trading only when the gap exceeds 10% ({n_thr} of {len(t)} years)
  cuts volatility and drawdown but not enough to change the conclusion (Sharpe {s.loc[thr, "Sharpe"]:.2f}).
- **Weather added nothing in real time.** {"The positions are identical with the weather nowcast switched off" if same else "Positions barely change with the weather nowcast switched off"}:
  with only 15–40 years of history at each decision date, the country output models rarely
  passed their own skill test, so the walk-forward nowcast sat close to trend. The signal is, in
  effect, mean reversion plus last season's crop shortfall.
- **Data timing matters.** If the previous season's crop size is only known a year late (closer to
  how FAOSTAT is actually published), the Sharpe ratio falls to {s.loc["Model, crop data one year late", "Sharpe"]:.2f}.

![Trades](backtest_trades.png)

## Current signal

On the {c["entry_date"]:%d %b %Y} entry date the future was ${c["entry"]:,.0f} against a walk-forward fair value of
${c["model_fair"]:,.0f}: a gap of {c["model_gap"]:+.1%}, nominally {side(c["model_gap"])}. Against the current futures strip (${latest_price:,.0f}) the gap is
{gap_now:+.1%}, nominally {side(gap_now)}. Both are inside the 10% no-trade band, so the practical position is **flat**.

## Trade log

{_md_table(log)}

## How the test was run

- Each 1 November the whole model is rebuilt from data up to that date: trend and cycle of
  production through the season just ended, output models re-selected, price equation re-estimated
  on prices to September. Weather windows still in the future are blanked.
- Long if fair value is above the futures price, short if below; held twelve months; one unit of
  notional, no leverage. Daily returns are from the front-month continuous contract.
- The fair value here (${c["model_fair"]:,.0f}) differs slightly from the main report's because this version
  standardises inputs only on data available at the time.

## Caveats

- **{len(t)} trades is a very small sample.** A Sharpe ratio of {m["Sharpe"]:.2f} over {len(t)} years has a standard error
  of about {1 / np.sqrt(len(t)):.2f}; nothing here is statistically significant.
- **Roll yield and costs are excluded.** The continuous front-month series is not roll-adjusted, so
  the cost or gain of rolling contracts (large in 2024's backwardation), commissions and
  collateral interest are not in these returns.
- **Some hindsight remains.** The model's design (variables, windows, per-country structure) was
  chosen with the full history in view, and FAOSTAT figures are today's revised values, assumed
  known one month after the season ends. Real-time results would likely be somewhat worse.
- Not investment advice.
"""
    out = outdir / "backtest_report.md"
    out.write_text(md)
    return out
