"""Walk-forward long/short backtest on COMEX copper futures, with and without tail options.

Every quarter (first trading day of February, May, August and November) the walk-forward
model's 12-month forecast sets the position: long if it expects the real price to rise,
short if it expects a fall. Positions are held for three months in the front-month future.

Protected versions buy one three-month out-of-the-money option per position (put for a
long, call for a short), priced with Black-76 on trailing realised volatility times a
mark-up - the same modelled-premium approach as the cocoa backtest.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from cocoa_model.hedged import VOL_MARKUP, black76, realised_vol, trade_path

THRESHOLD = 0.05


@dataclass
class Backtest:
    trades: pd.DataFrame  # per quarter: dates, market move, positions and returns per strategy
    stats: pd.DataFrame
    equity: pd.DataFrame
    hedge_stats: pd.DataFrame
    markup_sens: pd.DataFrame
    yearly: pd.DataFrame  # calendar-year returns, unhedged vs headline hedge
    quote: dict
    headline: str


def _stats(ret: pd.Series, eq: pd.Series, prem: pd.Series | None = None, pay: pd.Series | None = None) -> dict:
    active = ret[ret != 0]
    ruined = bool((eq <= 0).any())
    out = {"Return / year": ret.mean() * 4, "Volatility": ret.std() * 2,
           "Sharpe": ret.mean() / ret.std() * 2, "t-stat": ret.mean() / ret.std() * np.sqrt(len(ret)),
           "Hit rate": (active > 0).mean(), "Compound / year": np.nan if ruined else eq.iloc[-1] ** (4 / len(ret)) - 1,
           "Worst quarter": ret.min(), "Max drawdown": max((eq / eq.cummax() - 1).min(), -1.0)}
    if prem is not None:
        out |= {"Premium / year": prem.mean() * 4, "Option payoff / year": pay.mean() * 4}
    return out


def _chain(fut, rv, trades, pos, otm, markup):
    rets, prem, pay, curve, eq = {}, {}, {}, [], 1.0
    for k, tr in trades.iterrows():
        path, p, q = trade_path(fut, rv, tr["entry_date"], tr["exit_date"], float(pos[k]), otm, "12m", markup)
        rets[k], prem[k], pay[k] = float(path.iloc[-1]), p, q
        curve.append(eq * (1 + path.iloc[1:]))
        eq *= 1 + path.iloc[-1]
    return pd.Series(rets), pd.Series(prem), pd.Series(pay), pd.concat(curve)


def run(fut: pd.Series, preds: dict[str, pd.Series]) -> Backtest:
    """preds: strategy name -> walk-forward forecasts indexed by month-end Period."""
    rv = realised_vol(fut).bfill()
    main = next(iter(preds))
    rows = []
    for p in preds[main].index:
        nxt = (p + 1).to_timestamp()
        days = fut.index[fut.index >= nxt]
        out = fut.index[fut.index >= (p + 4).to_timestamp()]
        if len(days) == 0 or len(out) == 0:
            continue
        rows.append({"origin": p, "entry_date": days[0], "exit_date": out[0],
                     "long_ret": float(fut[out[0]] / fut[days[0]] - 1)})
    tr = pd.DataFrame(rows).set_index("origin")
    pos = {name: np.sign(s.reindex(tr.index)).replace(0, 1.0) for name, s in preds.items()}
    thr = f"Model, trade only if forecast > {THRESHOLD:.0%}"
    pos[thr] = pos[main].where(preds[main].reindex(tr.index).abs() > THRESHOLD, 0.0)
    pos["Always long (benchmark)"] = pd.Series(1.0, index=tr.index)

    stats, equity = {}, {}
    for name, ps in pos.items():
        ret, _, _, eq = _chain(fut, rv, tr, ps, None, VOL_MARKUP)
        stats[name], equity[name] = _stats(ret, eq), eq
        tr[f"{name}|pos"], tr[f"{name}|ret"] = ps, ret
    tr["forecast"] = preds[main].reindex(tr.index)

    hedge, hret = {}, {}
    specs = {f"{main}, unhedged": (main, None), "+ options 10% OTM": (main, 0.10),
             "+ options 15% OTM": (main, 0.15), "+ options 20% OTM": (main, 0.20),
             "Always long, unhedged": ("Always long (benchmark)", None),
             "Always long + puts 15% OTM": ("Always long (benchmark)", 0.15)}
    for name, (src, otm) in specs.items():
        ret, prem, pay, eq = _chain(fut, rv, tr, pos[src], otm, VOL_MARKUP)
        hedge[name], hret[name] = _stats(ret, eq, prem, pay), ret
        equity[name] = eq
    headline = "+ options 15% OTM"
    sens = {}
    for mk in (1.0, 1.15, 1.3, 1.5):
        ret, prem, pay, eq = _chain(fut, rv, tr, pos[main], 0.15, mk)
        sens[f"{mk:.2f}×"] = _stats(ret, eq, prem, pay)
    yr = tr["entry_date"].dt.year
    yearly = pd.DataFrame({"Unhedged": (1 + hret[f"{main}, unhedged"]).groupby(yr).prod() - 1,
                           "Hedged": (1 + hret[headline]).groupby(yr).prod() - 1,
                           "Always long": (1 + tr["long_ret"]).groupby(yr).prod() - 1})
    F, vol = float(fut.iloc[-1]), float(rv.iloc[-1])
    quote = {"price": F, "realised_vol": vol, "implied_vol": vol * VOL_MARKUP}
    for otm in (0.10, 0.15, 0.20):
        quote[f"put_{otm:.0%}"] = black76(F, F * (1 - otm), 0.25, vol * VOL_MARKUP, False) / F
        quote[f"call_{otm:.0%}"] = black76(F, F * (1 + otm), 0.25, vol * VOL_MARKUP, True) / F
    return Backtest(tr, pd.DataFrame(stats).T, pd.DataFrame(equity), pd.DataFrame(hedge).T,
                    pd.DataFrame(sens).T, yearly, quote, headline)
