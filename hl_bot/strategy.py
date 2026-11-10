"""EMA-crossover trend signal with an ATR-based stop distance. Pure functions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class Candle:
    t: int  # open time, ms
    T: int  # close time, ms
    o: float
    h: float
    l: float
    c: float

    @classmethod
    def from_api(cls, raw: dict) -> "Candle":
        return cls(int(raw["t"]), int(raw["T"]), float(raw["o"]), float(raw["h"]), float(raw["l"]), float(raw["c"]))


@dataclass(frozen=True)
class Signal:
    side: int  # +1 long, -1 short, 0 not enough data
    stop_pct: float  # stop distance as a fraction of entry price
    price: float  # close of the candle the signal was computed on
    candle_time: int


def closed_candles(candles: Sequence[Candle], now_ms: int) -> list[Candle]:
    """Drop the still-forming candle so the signal never repaints."""
    return [c for c in candles if c.T < now_ms]


def ema(values: Sequence[float], period: int) -> list[float]:
    k = 2.0 / (period + 1)
    out: list[float] = []
    for v in values:
        out.append(v if not out else out[-1] + k * (v - out[-1]))
    return out


def atr(candles: Sequence[Candle], period: int) -> float:
    trs = [
        max(cur.h - cur.l, abs(cur.h - prev.c), abs(cur.l - prev.c))
        for prev, cur in zip(candles, candles[1:])
    ]
    window = trs[-period:]
    return sum(window) / len(window) if window else 0.0


def compute_signal(
    candles: Sequence[Candle],
    fast: int = 20,
    slow: int = 50,
    atr_period: int = 14,
    atr_mult: float = 2.0,
    min_stop_pct: float = 0.01,
    max_stop_pct: float = 0.04,
) -> Signal:
    """`candles` must be closed candles, oldest first."""
    if len(candles) < slow * 2:
        last = candles[-1] if candles else None
        return Signal(0, max_stop_pct, last.c if last else 0.0, last.t if last else 0)
    closes = [c.c for c in candles]
    f, s = ema(closes, fast)[-1], ema(closes, slow)[-1]
    price = closes[-1]
    raw_stop = atr_mult * atr(candles, atr_period) / price
    stop_pct = min(max(raw_stop, min_stop_pct), max_stop_pct)
    return Signal(1 if f > s else -1, stop_pct, price, candles[-1].t)
