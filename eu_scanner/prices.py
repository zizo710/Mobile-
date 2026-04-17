"""Pre-market and overnight price moves.

European cash open is 08:00 London / 09:00 CET, so before that we use:
  - last close (regular session yesterday)
  - latest tick available (often pre-market quote, ETF proxy, or ADR)
yfinance returns intraday minute bars including pre-market when available
(`prepost=True`). For names without true pre-market in Europe we fall back
to the most recent tick versus prior close — this catches overnight gaps
driven by Asia / US sessions and overnight news.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import math
import warnings

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import yfinance as yf

from .universe import Underlying


@dataclass
class PriceSnapshot:
    underlying: Underlying
    last: float | None
    prev_close: float | None
    change_pct: float | None
    avg_vol_20d: float | None
    rel_volume: float | None  # today's traded volume / 20d avg (0 if no trades yet)
    range_pct_5d: float | None  # 5-day realised range as % — proxy for vol regime
    error: str | None = None

    @property
    def abs_change(self) -> float:
        return abs(self.change_pct) if self.change_pct is not None else 0.0


def _fetch_single(u: Underlying) -> PriceSnapshot:
    try:
        tk = yf.Ticker(u.ticker)
        # 6 days covers a long weekend; 1m bars include pre/post when available.
        hist = tk.history(period="6d", interval="1d", auto_adjust=False)
        if hist is None or hist.empty or len(hist) < 2:
            return PriceSnapshot(u, None, None, None, None, None, None, "no daily data")

        prev_close = float(hist["Close"].iloc[-2])
        last_daily_close = float(hist["Close"].iloc[-1])

        # Try to get the latest tick — pre-market or last trade.
        last = last_daily_close
        try:
            intraday = tk.history(period="1d", interval="1m", prepost=True)
            if intraday is not None and not intraday.empty:
                last = float(intraday["Close"].dropna().iloc[-1])
        except Exception:
            pass

        change_pct = (last / prev_close - 1.0) * 100.0 if prev_close else None

        avg_vol = float(hist["Volume"].tail(20).mean()) if "Volume" in hist else None
        today_vol = float(hist["Volume"].iloc[-1]) if "Volume" in hist else 0.0
        rel_vol = (today_vol / avg_vol) if (avg_vol and avg_vol > 0) else None

        # 5d realised range as proxy for current vol regime
        tail5 = hist.tail(5)
        if len(tail5) >= 2 and prev_close:
            hi = float(tail5["High"].max())
            lo = float(tail5["Low"].min())
            range_pct = (hi - lo) / prev_close * 100.0
        else:
            range_pct = None

        return PriceSnapshot(
            underlying=u,
            last=last,
            prev_close=prev_close,
            change_pct=change_pct,
            avg_vol_20d=avg_vol,
            rel_volume=rel_vol,
            range_pct_5d=range_pct,
        )
    except Exception as e:  # network errors, delistings etc.
        return PriceSnapshot(u, None, None, None, None, None, None, str(e)[:80])


def fetch_snapshots(
    underlyings: list[Underlying], max_workers: int = 12
) -> list[PriceSnapshot]:
    out: list[PriceSnapshot] = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(_fetch_single, u): u for u in underlyings}
        for f in as_completed(futs):
            out.append(f.result())
    return out


def is_valid(snap: PriceSnapshot) -> bool:
    return (
        snap.error is None
        and snap.change_pct is not None
        and not math.isnan(snap.change_pct)
    )
