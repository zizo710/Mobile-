"""Long/short strategy with protective options on every position.

Long futures  -> buy an out-of-the-money put.
Short futures -> buy an out-of-the-money call.

No historical cocoa option prices are freely available, so premiums are modelled:
Black-76 on the front-month future, with implied volatility taken as trailing 60-day
realised volatility times a mark-up (options usually trade above realised vol, and
out-of-the-money cocoa calls carry extra skew). The mark-up is a stated assumption and
the results are shown for a range of it.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import norm

from .backtest import Backtest

VOL_WINDOW = 60
VOL_MARKUP = 1.15


def black76(F: float, K: float, T: float, sigma: float, call: bool) -> float:
    """Undiscounted Black-76 option value on a future."""
    if T <= 0 or sigma <= 0:
        return max(F - K, 0.0) if call else max(K - F, 0.0)
    d1 = (np.log(F / K) + 0.5 * sigma**2 * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return float(F * norm.cdf(d1) - K * norm.cdf(d2)) if call else float(K * norm.cdf(-d2) - F * norm.cdf(-d1))


def realised_vol(fut: pd.Series) -> pd.Series:
    return np.log(fut).diff().rolling(VOL_WINDOW).std() * np.sqrt(252)


def _periods(days: pd.DatetimeIndex, tenor: str) -> list[pd.DatetimeIndex]:
    if tenor == "12m":
        return [days]
    key = np.array([(d.month - 11) % 12 // 3 for d in days])  # 0: Nov-Jan, 1: Feb-Apr, 2: May-Jul, 3: Aug-Oct
    return [days[key == k] for k in range(4) if (key == k).any()]


def trade_path(fut: pd.Series, rv: pd.Series, entry: pd.Timestamp, exit_: pd.Timestamp, pos: float,
               otm: float | None, tenor: str, markup: float) -> tuple[pd.Series, float, float]:
    """Daily cumulative return on entry notional, plus total premium paid and option payoff
    (both as fractions of entry notional). otm=None means unhedged."""
    px = fut.loc[entry:exit_]
    F0 = float(px.iloc[0])
    pnl = pos * (px - F0)
    prem_total = payoff_total = 0.0
    if otm is not None and pos != 0:
        call = pos < 0
        opt = pd.Series(0.0, index=px.index)
        for days in _periods(px.index, tenor):
            start, end = days[0], days[-1]
            # the option is bought at the close before the period (entry day for the first)
            buy_day = px.index[max(px.index.get_loc(start) - 1, 0)]
            Fs = float(px[buy_day])
            K = Fs * (1 + otm) if call else Fs * (1 - otm)
            T = max((end - buy_day).days, 1) / 365
            prem = black76(Fs, K, T, float(rv[buy_day]) * markup, call)
            leg = pd.Series({d: black76(float(px[d]), K, (end - d).days / 365, float(rv[d]) * markup, call) - prem
                             for d in days})
            opt.loc[days] += leg
            opt.loc[px.index > end] += leg[end]  # realised option P&L carries forward
            prem_total += prem
            payoff_total += leg[end] + prem
        pnl = pnl + opt
    return pnl / F0, prem_total / F0, payoff_total / F0


@dataclass
class Hedged:
    stats: pd.DataFrame
    trades: pd.DataFrame  # per-trade returns for each structure
    equity: pd.DataFrame
    markup_sens: pd.DataFrame
    quote: dict  # indicative hedge cost today


def _run(bt: Backtest, fut: pd.Series, rv: pd.Series, pos_col: str | None, otm, tenor, markup):
    rets, prem, pay, curve, eq = {}, {}, {}, [], 1.0
    for H, tr in bt.trades.iterrows():
        pos = 1.0 if pos_col is None else float(tr[pos_col])
        exit_ = fut.loc[:pd.Timestamp(H, 10, 31)].index[-1]
        path, p, q = trade_path(fut, rv, tr["entry_date"], exit_, pos, otm, tenor, markup)
        rets[H], prem[H], pay[H] = float(path.iloc[-1]), p, q
        curve.append(eq * (1 + path.iloc[1:]))
        eq *= 1 + path.iloc[-1]
    return pd.Series(rets), pd.Series(prem), pd.Series(pay), pd.concat(curve)


def _stats(ret: pd.Series, prem: pd.Series, pay: pd.Series, eq: pd.Series) -> dict:
    ruined = bool((eq <= 0).any())  # an unhedged short can lose more than the capital behind it
    return {"Average return / year": ret.mean(), "Volatility": ret.std(), "Sharpe": ret.mean() / ret.std(),
            "Compound return / year": np.nan if ruined else eq.iloc[-1] ** (1 / len(ret)) - 1,
            "Worst year": ret.min(), "Max drawdown": max((eq / eq.cummax() - 1).min(), -1.0),
            "Premium / year": prem.mean(), "Option payoff / year": pay.mean()}


def run(bt: Backtest, fut: pd.Series) -> Hedged:
    rv = realised_vol(fut).bfill()
    specs = {"Model long/short, unhedged": ("model_pos", None, "12m"),
             "+ quarterly options, 10% OTM": ("model_pos", 0.10, "3m"),
             "+ quarterly options, 20% OTM": ("model_pos", 0.20, "3m"),
             "+ 12-month option, 10% OTM": ("model_pos", 0.10, "12m"),
             "+ 12-month option, 20% OTM": ("model_pos", 0.20, "12m"),
             "+ 12-month option, 30% OTM": ("model_pos", 0.30, "12m"),
             "Always long, unhedged": (None, None, "12m"),
             "Always long + 12-month put, 20% OTM": (None, 0.20, "12m")}
    stats, trades, equity = {}, {}, {}
    for name, (col, otm, tenor) in specs.items():
        ret, prem, pay, eq = _run(bt, fut, rv, col, otm, tenor, VOL_MARKUP)
        stats[name], trades[name], equity[name] = _stats(ret, prem, pay, eq), ret, eq
    sens = {}
    for mk in (1.0, 1.15, 1.3, 1.5):
        ret, prem, pay, eq = _run(bt, fut, rv, "model_pos", 0.20, "3m", mk)
        sens[f"{mk:.2f}×"] = _stats(ret, prem, pay, eq)
    F, vol = float(fut.iloc[-1]), float(rv.iloc[-1])
    quote = {"price": F, "realised_vol": vol, "implied_vol": vol * VOL_MARKUP}
    for otm in (0.10, 0.20):
        for tenor, T in (("3m", 0.25), ("12m", 1.0)):
            quote[f"put_{otm:.0%}_{tenor}"] = black76(F, F * (1 - otm), T, vol * VOL_MARKUP, False) / F
            quote[f"call_{otm:.0%}_{tenor}"] = black76(F, F * (1 + otm), T, vol * VOL_MARKUP, True) / F
    return Hedged(pd.DataFrame(stats).T, pd.DataFrame(trades), pd.DataFrame(equity),
                  pd.DataFrame(sens).T, quote)
