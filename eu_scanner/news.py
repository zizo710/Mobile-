"""News scanner — pulls overnight headlines and matches them to underlyings.

Two layers:
  1) Yahoo Finance per-ticker news (works for most EU listings).
  2) Broad Reuters / FT / Bloomberg-style aggregator feeds for macro headlines
     (so we surface ECB / data prints / Asia overnight that don't tag a ticker).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import re
import warnings

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import yfinance as yf

import feedparser

from .universe import Underlying


# Macro / aggregator feeds — light footprint, no auth required.
MACRO_FEEDS = [
    "https://www.ecb.europa.eu/rss/press.html",
    "https://www.ecb.europa.eu/rss/fie.html",  # Financial / monetary stats
    "https://www.bankofengland.co.uk/rss/news",
    "https://www.bundesbank.de/service/rss/en/633286/feed.rss",
    "https://feeds.reuters.com/reuters/businessNews",
    "https://feeds.reuters.com/reuters/UKBusinessNews",
    "https://www.ft.com/markets?format=rss",
    "https://www.investing.com/rss/news_25.rss",  # economic indicators
]


@dataclass
class Headline:
    title: str
    source: str
    published: datetime | None
    link: str

    def age_hours(self, now: datetime) -> float:
        if self.published is None:
            return 999.0
        return (now - self.published).total_seconds() / 3600.0


@dataclass
class TickerNews:
    ticker: str
    headlines: list[Headline] = field(default_factory=list)


def _parse_dt(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        val = entry.get(key)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                continue
    return None


def fetch_macro_headlines(lookback_hours: int = 18) -> list[Headline]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    out: list[Headline] = []

    def pull(url: str) -> list[Headline]:
        try:
            d = feedparser.parse(url)
            src = (d.feed.get("title") or url)[:40]
            items: list[Headline] = []
            for e in d.entries[:30]:
                dt = _parse_dt(e)
                if dt is None or dt >= cutoff:
                    items.append(
                        Headline(
                            title=e.get("title", "").strip(),
                            source=src,
                            published=dt,
                            link=e.get("link", ""),
                        )
                    )
            return items
        except Exception:
            return []

    with ThreadPoolExecutor(max_workers=6) as ex:
        for items in ex.map(pull, MACRO_FEEDS):
            out.extend(items)

    # Dedupe by title
    seen: set[str] = set()
    deduped: list[Headline] = []
    for h in out:
        key = h.title.lower()
        if key and key not in seen:
            seen.add(key)
            deduped.append(h)
    deduped.sort(
        key=lambda h: h.published or datetime(1970, 1, 1, tzinfo=timezone.utc),
        reverse=True,
    )
    return deduped


def _yahoo_news_for(u: Underlying, lookback_hours: int) -> TickerNews:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    try:
        raw = yf.Ticker(u.ticker).news or []
    except Exception:
        raw = []

    headlines: list[Headline] = []
    for item in raw:
        # Yahoo's schema has shifted: support both old and new shape.
        title = item.get("title") or item.get("content", {}).get("title", "")
        link = item.get("link") or item.get("content", {}).get("canonicalUrl", {}).get("url", "")
        ts = item.get("providerPublishTime")
        published: datetime | None = None
        if ts:
            try:
                published = datetime.fromtimestamp(int(ts), tz=timezone.utc)
            except Exception:
                published = None
        else:
            pub_str = item.get("content", {}).get("pubDate")
            if pub_str:
                try:
                    published = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                except Exception:
                    published = None
        if published is None or published >= cutoff:
            headlines.append(
                Headline(
                    title=str(title).strip(),
                    source=item.get("publisher", "Yahoo"),
                    published=published,
                    link=str(link),
                )
            )
    return TickerNews(ticker=u.ticker, headlines=headlines)


def fetch_ticker_news(
    underlyings: list[Underlying],
    lookback_hours: int = 18,
    max_workers: int = 12,
) -> dict[str, TickerNews]:
    out: dict[str, TickerNews] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(_yahoo_news_for, u, lookback_hours): u for u in underlyings}
        for f in as_completed(futs):
            tn = f.result()
            out[tn.ticker] = tn
    return out


# Words that suggest a market-moving catalyst — used to upweight a name.
CATALYST_KEYWORDS = re.compile(
    r"\b("
    r"earnings|results|guidance|profit warning|trading update|preliminary|"
    r"upgrade|downgrade|rating|target price|"
    r"acquisition|merger|takeover|bid|offer|buyback|dividend|"
    r"strike|recall|lawsuit|investigation|fine|sanction|"
    r"approval|launch|contract|deal|partnership|spin[- ]?off|ipo|"
    r"ceo|cfo|resigns|appoint|"
    r"raises|cuts|beats|misses|warns|downgrades|upgrades"
    r")\b",
    re.IGNORECASE,
)


def has_catalyst(text: str) -> bool:
    return bool(CATALYST_KEYWORDS.search(text or ""))
