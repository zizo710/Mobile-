"""Score and rank underlyings to produce the morning watchlist.

Scoring philosophy: we want names that will *trade* today, not just any mover.
The signal that matters most is a real overnight gap with a catalyst attached
and confirming volume. The score combines:

  - |gap %| relative to the name's recent range  (move quality)
  - rel-volume vs 20d average                    (real interest)
  - news catalyst flag                           (a reason to move)
  - news recency / count                         (information density)
  - sector concentration cap                     (avoid 8 banks in top 20)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .news import TickerNews, has_catalyst
from .prices import PriceSnapshot, is_valid


@dataclass
class RankedItem:
    snap: PriceSnapshot
    news: TickerNews
    score: float
    reasons: list[str]


def _normalised_gap(snap: PriceSnapshot) -> float:
    """Gap size scaled by the name's recent range. >1 means an outsized move."""
    if snap.change_pct is None:
        return 0.0
    range_5d = snap.range_pct_5d or 5.0
    if range_5d <= 0:
        range_5d = 5.0
    return abs(snap.change_pct) / (range_5d / 5.0)  # 5d range normalised to ~1.0


def score_one(snap: PriceSnapshot, news: TickerNews) -> RankedItem:
    reasons: list[str] = []
    score = 0.0

    if snap.change_pct is not None:
        ng = _normalised_gap(snap)
        gap_score = min(ng, 6.0) * 1.5  # cap so a 10% rip doesn't dominate
        score += gap_score
        if abs(snap.change_pct) >= 1.0:
            reasons.append(f"gap {snap.change_pct:+.2f}%")

    if snap.rel_volume and snap.rel_volume > 1.2:
        score += min(snap.rel_volume, 5.0) * 0.6
        reasons.append(f"rel vol {snap.rel_volume:.1f}x")

    now = datetime.now(timezone.utc)
    fresh = [h for h in news.headlines if h.age_hours(now) <= 18]
    if fresh:
        score += min(len(fresh), 5) * 0.4
        reasons.append(f"{len(fresh)} headlines")

    cat_count = sum(1 for h in fresh if has_catalyst(h.title))
    if cat_count:
        score += 1.5 + min(cat_count, 3) * 0.3
        reasons.append("catalyst")

    return RankedItem(snap=snap, news=news, score=score, reasons=reasons)


def rank(
    snapshots: list[PriceSnapshot],
    news_by_ticker: dict[str, TickerNews],
    top_n: int = 20,
    sector_cap: int = 4,
) -> list[RankedItem]:
    items: list[RankedItem] = []
    for s in snapshots:
        if not is_valid(s):
            continue
        tn = news_by_ticker.get(s.underlying.ticker, TickerNews(s.underlying.ticker))
        items.append(score_one(s, tn))

    # Drop names with no signal at all.
    items = [it for it in items if it.score > 0.5]
    items.sort(key=lambda it: it.score, reverse=True)

    # Apply sector cap so the watchlist is diversified.
    selected: list[RankedItem] = []
    sector_counts: dict[str, int] = {}
    overflow: list[RankedItem] = []
    for it in items:
        sec = it.snap.underlying.sector
        if sector_counts.get(sec, 0) < sector_cap:
            selected.append(it)
            sector_counts[sec] = sector_counts.get(sec, 0) + 1
            if len(selected) == top_n:
                break
        else:
            overflow.append(it)

    # If sector cap left us short, top up with the highest-scoring overflow.
    if len(selected) < top_n:
        for it in overflow:
            selected.append(it)
            if len(selected) == top_n:
                break

    return selected
