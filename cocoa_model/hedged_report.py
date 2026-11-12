"""Markdown report + charts for the options-hedged backtest."""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .backtest import Backtest
from .hedged import VOL_MARKUP, VOL_WINDOW, Hedged
from .report import AQUA, BLUE, INK2, ORANGE, SURFACE, _md_table, _season

UNHEDGED, HEADLINE, LONG = ("Model long/short, unhedged", "+ quarterly options, 20% OTM", "Always long, unhedged")


def chart_equity(h: Hedged, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.4))
    for name, colour, label in ((UNHEDGED, BLUE, "Long/short, unhedged"),
                                (HEADLINE, AQUA, "Long/short + quarterly 20% OTM options"),
                                (LONG, ORANGE, "Always long, unhedged")):
        eq = h.equity[name]
        dead = eq[eq <= 0.05]
        if len(dead):  # capital exhausted: stop the line there
            eq = eq.loc[:dead.index[0]].clip(lower=0.05)
            ax.annotate("capital wiped out\n(short, Apr 2024)", (eq.index[-1], 0.05), xytext=(-120, 8),
                        textcoords="offset points", color=INK2, fontsize=9,
                        arrowprops={"arrowstyle": "-", "color": INK2})
        else:
            ax.annotate(f"{eq.iloc[-1]:.1f}×", (eq.index[-1], eq.iloc[-1]), xytext=(5, 0),
                        textcoords="offset points", va="center", color=INK2, fontsize=9)
        ax.plot(eq.index, eq, color=colour, label=label)
    ax.set_yscale("log")
    ax.set_yticks([0.05, 0.25, 1, 4, 16], ["0", "0.25×", "1×", "4×", "16×"])
    ax.minorticks_off()
    ax.axhline(1, color=INK2, linewidth=0.8)
    ax.set_ylabel("Growth of 1 (log scale)")
    ax.set_title("Protective options: growth of 1, positions held within each year")
    ax.legend(loc="lower left")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def chart_trades(h: Hedged, path: Path) -> None:
    t = h.trades
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.set_axisbelow(True)
    w = 0.38
    ax.bar(t.index - w / 2, t[UNHEDGED] * 100, width=w, color=BLUE, label="Unhedged", edgecolor=SURFACE)
    ax.bar(t.index + w / 2, t[HEADLINE] * 100, width=w, color=AQUA, label="With quarterly 20% OTM options",
           edgecolor=SURFACE)
    ax.axhline(0, color=INK2, linewidth=0.8)
    ax.set_xticks(t.index[::2], [_season(y) for y in t.index[::2]], rotation=45, ha="right")
    ax.yaxis.set_major_formatter(lambda y, _: f"{y:+.0f}%")
    ax.set_title("Return of each one-year trade, with and without protection")
    ax.legend(loc="lower left")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _fmt(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    out["Avg return / year"] = df["Average return / year"].map("{:+.1%}".format)
    out["Volatility"] = df["Volatility"].map("{:.0%}".format)
    out["Sharpe"] = df["Sharpe"].map("{:.2f}".format)
    out["Compound / year"] = df["Compound return / year"].map(lambda x: "wiped out" if pd.isna(x) else f"{x:+.1%}")
    out["Worst year"] = df["Worst year"].map("{:+.0%}".format)
    out["Max drawdown"] = df["Max drawdown"].map(lambda x: "-100% (wiped out)" if x <= -1 else f"{x:+.0%}")
    out["Premium / year"] = df["Premium / year"].map(lambda x: "–" if x == 0 else f"{x:.1%}")
    out["Option payoff / year"] = df["Option payoff / year"].map(lambda x: "–" if x == 0 else f"{x:.1%}")
    return out


def build(h: Hedged, bt: Backtest, outdir: Path) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    chart_equity(h, outdir / "hedged_equity.png")
    chart_trades(h, outdir / "hedged_trades.png")
    s, t, q = h.stats, h.trades, h.quote
    u, hd, al = s.loc[UNHEDGED], s.loc[HEADLINE], s.loc[LONG]
    st = _fmt(s)
    st.index.name = "Strategy"
    sens = _fmt(h.markup_sens)[["Avg return / year", "Sharpe", "Compound / year", "Premium / year"]]
    sens.index.name = "Implied vol ÷ realised vol"

    worst = t[UNHEDGED].idxmin()
    helped = t[HEADLINE] - t[UNHEDGED]
    n_help = int((helped > 0.005).sum())
    big = helped.sort_values(ascending=False).head(3)
    cost_years = helped[helped < 0]
    pos = bt.trades["model_pos"]
    log = pd.DataFrame({"Position": pos.map({1.0: "long + put", -1.0: "short + call"}),
                        "Unhedged": t[UNHEDGED].map("{:+.0%}".format),
                        "Hedged": t[HEADLINE].map("{:+.0%}".format),
                        "Difference": helped.map("{:+.0%}".format)})
    log.index = [_season(y) for y in t.index]
    log.index.name = "Crop year"

    md = f"""# Backtest: long/short with protective puts and calls

Each long futures position buys an out-of-the-money put; each short buys an out-of-the-money call.
Signals and trade dates are the same as in [the unhedged backtest](backtest_report.md).

## Result

**Protection does what you want on the tail and roughly pays for itself, but it does not create an
edge.** With options 20% out of the money, rolled quarterly, the worst year improves from
{u["Worst year"]:+.0%} to {hd["Worst year"]:+.0%} and the average return is about unchanged ({u["Average return / year"]:+.1%} to {hd["Average return / year"]:+.1%}), so the
Sharpe ratio rises from {u["Sharpe"]:.2f} to {hd["Sharpe"]:.2f}. That is still no better than simply holding cocoa
unhedged ({al["Sharpe"]:.2f}).

{_md_table(st)}

Returns are per one-year trade on the entry notional, with the position held (not rebalanced)
through the year, so the unhedged drawdown is worse here than in the first backtest. "Premium" and "Option payoff" are averages
per year as a share of notional. Option prices are modelled, not historical – see the assumptions.

![Equity](hedged_equity.png)

## What the numbers say

- **The tail is fixed.** The unhedged short in {_season(worst)} lost {-t.loc[worst, UNHEDGED]:.0%} by year end, and at the April
  2024 peak the loss exceeded the capital behind it. With calls 20% above the market, rolled
  quarterly, the year's loss is {-t.loc[worst, HEADLINE]:.0%}.
- **Protection costs {hd["Premium / year"]:.1%} of notional a year and paid back {hd["Option payoff / year"]:.1%}.** It is close to break-even
  only because of a few large reversals: it helped in {n_help} of {len(t)} years, most in
  {", ".join(f"{_season(y)} ({v:+.0%})" for y, v in big.items())}, and cost an average of {-cost_years.mean():.1%} in the other {len(cost_years)}.
- **Strike distance matters more than tenor.** Options 10% out of the money cost
  {s.loc["+ quarterly options, 10% OTM", "Premium / year"]:.0%} a year and drag the average return down to {s.loc["+ quarterly options, 10% OTM", "Average return / year"]:+.1%}. At 20–30% the cost is
  {s.loc["+ 12-month option, 30% OTM", "Premium / year"]:.0%}–{hd["Premium / year"]:.0%} and most of the tail protection is kept.
- **Quarterly rolling beat a single 12-month option here** (Sharpe {hd["Sharpe"]:.2f} vs {s.loc["+ 12-month option, 20% OTM", "Sharpe"]:.2f}) because strikes
  reset after big moves and pay again if the move continues. That gap rests on a handful of years
  and I would not rely on it.
- **Protection is most expensive exactly when you want it.** After the 2024 spike, volatility
  above 60% made a one-year 20% call cost about a quarter of notional, turning the profitable
  {_season(2025)} short into a loss with the 12-month structure.
- **Hedging does not rescue a strategy without an edge.** Always-long with a 12-month put does
  worse than always-long without ({s.loc["Always long + 12-month put, 20% OTM", "Sharpe"]:.2f} vs {al["Sharpe"]:.2f}): on average you pay more for
  options than they return.

![Trades](hedged_trades.png)

## Sensitivity to the option-pricing assumption

The headline structure (quarterly, 20% OTM) at different ratios of implied to realised volatility:

{_md_table(sens)}

If cocoa options really cost 30% more than realised volatility implies, the hedged strategy is no
better than the unhedged one on Sharpe, though the tail protection remains.

## What protection would cost today

With the front-month future at ${q["price"]:,.0f} and {VOL_WINDOW}-day realised volatility of {q["realised_vol"]:.0%} (assumed implied
{q["implied_vol"]:.0%}), as a share of notional:

| Option | 3 months | 12 months |
|---|---|---|
| Put, 10% OTM | {q["put_10%_3m"]:.1%} | {q["put_10%_12m"]:.1%} |
| Put, 20% OTM | {q["put_20%_3m"]:.1%} | {q["put_20%_12m"]:.1%} |
| Call, 10% OTM | {q["call_10%_3m"]:.1%} | {q["call_10%_12m"]:.1%} |
| Call, 20% OTM | {q["call_20%_3m"]:.1%} | {q["call_20%_12m"]:.1%} |

These are model estimates; check live ICE quotes before acting. The model's current signal is
flat, so there is no position to protect at the moment.

## Trade log (quarterly, 20% OTM)

{_md_table(log)}

## Assumptions and caveats

- **Option prices are modelled.** Black-76 on the front-month future, implied volatility =
  {VOL_WINDOW}-day realised volatility × {VOL_MARKUP}, no skew, no bid-ask spread, no interest. Real cocoa calls
  usually carry extra skew, so short-side protection is probably under-priced here.
- **The headline structure was chosen after seeing the results** of six alternatives, so its
  advantage over the others is overstated.
- Options are held to expiry at each quarter end and re-struck at the then-current price. The
  futures leg is the front-month continuous contract with no roll adjustment or costs.
- {len(t)} one-year trades; nothing here is statistically significant. Not investment advice.
"""
    out = outdir / "hedged_report.md"
    out.write_text(md)
    return out
