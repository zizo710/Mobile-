"""Bar-by-bar replay of the strategy on historical candles, with fees and stops."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .config import Config
from .strategy import Candle, compute_signal

TAKER_FEE = 0.00045
SLIPPAGE = 0.0002


@dataclass
class Result:
    trades: int = 0
    wins: int = 0
    stops: int = 0
    pnl_usd: float = 0.0
    max_drawdown_usd: float = 0.0
    buy_hold_usd: float = 0.0
    halted: bool = False


def run_backtest(candles: Sequence[Candle], cfg: Config) -> Result:
    res = Result()
    notional = cfg.notional_usd
    cost = 2 * (TAKER_FEE + SLIPPAGE) * notional  # round trip
    side, entry, stop, blocked = 0, 0.0, 0.0, 0
    peak = 0.0
    warmup = cfg.slow * 2

    def close(exit_px: float, stopped: bool) -> None:
        nonlocal side, blocked, peak
        pnl = side * (exit_px - entry) / entry * notional - cost
        res.trades += 1
        res.wins += pnl > 0
        res.stops += stopped
        res.pnl_usd += pnl
        peak = max(peak, res.pnl_usd)
        res.max_drawdown_usd = max(res.max_drawdown_usd, peak - res.pnl_usd)
        if stopped:
            blocked = side
        side = 0

    for i in range(warmup, len(candles)):
        bar = candles[i]
        # Signal uses candles closed before this bar; act at this bar's open.
        sig = compute_signal(
            candles[max(0, i - cfg.slow * 6) : i],
            cfg.fast, cfg.slow, cfg.atr_period, cfg.atr_mult, cfg.min_stop_pct, cfg.max_stop_pct,
        )
        desired = sig.side if (sig.side > 0 or cfg.allow_short) else 0
        if blocked and desired != blocked:
            blocked = 0
        if side and side != desired:
            close(bar.o, stopped=False)
        if not side and desired and desired != blocked:
            side, entry = desired, bar.o
            stop = entry * (1 - side * sig.stop_pct)
        if side and ((side > 0 and bar.l <= stop) or (side < 0 and bar.h >= stop)):
            close(stop, stopped=True)
        if res.pnl_usd <= -cfg.max_loss_usd:
            res.halted = True
            break

    if side:
        close(candles[-1].c, stopped=False)
    if len(candles) > warmup:
        first, last = candles[warmup].o, candles[-1].c
        res.buy_hold_usd = (last - first) / first * notional
    return res
