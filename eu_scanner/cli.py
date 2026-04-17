"""CLI entry point: `python -m eu_scanner` or `eu-scan`."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console

from .briefing import render_briefing
from .news import fetch_macro_headlines, fetch_ticker_news
from .prices import fetch_snapshots
from .ranking import rank
from .universe import all_indices, all_single_names


def _export_csv(path: Path, ranked) -> None:
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            ["rank", "ticker", "name", "sector", "country", "change_pct", "rel_volume", "score", "reasons"]
        )
        for i, it in enumerate(ranked, 1):
            s = it.snap
            w.writerow(
                [
                    i,
                    s.underlying.ticker,
                    s.underlying.name,
                    s.underlying.sector,
                    s.underlying.country,
                    f"{s.change_pct:.4f}" if s.change_pct is not None else "",
                    f"{s.rel_volume:.4f}" if s.rel_volume is not None else "",
                    f"{it.score:.4f}",
                    "; ".join(it.reasons),
                ]
            )


def _export_json(path: Path, ranked, indices, macro) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "indices": [
            {
                "ticker": s.underlying.ticker,
                "name": s.underlying.name,
                "last": s.last,
                "prev_close": s.prev_close,
                "change_pct": s.change_pct,
            }
            for s in indices
        ],
        "watchlist": [
            {
                "rank": i,
                "ticker": it.snap.underlying.ticker,
                "name": it.snap.underlying.name,
                "sector": it.snap.underlying.sector,
                "country": it.snap.underlying.country,
                "change_pct": it.snap.change_pct,
                "rel_volume": it.snap.rel_volume,
                "score": it.score,
                "reasons": it.reasons,
                "headlines": [
                    {"title": h.title, "source": h.source, "link": h.link}
                    for h in it.news.headlines[:5]
                ],
            }
            for i, it in enumerate(ranked, 1)
        ],
        "macro": [
            {
                "title": h.title,
                "source": h.source,
                "published": h.published.isoformat() if h.published else None,
                "link": h.link,
            }
            for h in macro
        ],
    }
    path.write_text(json.dumps(payload, indent=2))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="eu-scan",
        description="Morning scanner for European equity markets — pre-market moves and overnight news.",
    )
    p.add_argument("--top", type=int, default=20, help="Watchlist size (default 20).")
    p.add_argument(
        "--lookback",
        type=int,
        default=18,
        help="Hours to look back for news (default 18 — covers overnight).",
    )
    p.add_argument(
        "--sector-cap",
        type=int,
        default=4,
        help="Max names per sector in the watchlist (default 4).",
    )
    p.add_argument("--workers", type=int, default=12, help="Concurrent fetch workers.")
    p.add_argument("--csv", type=Path, help="Also write watchlist to CSV.")
    p.add_argument("--json", type=Path, help="Also write full briefing to JSON.")
    p.add_argument(
        "--no-news",
        action="store_true",
        help="Skip news fetching (faster; relies on price moves only).",
    )
    args = p.parse_args(argv)

    console = Console()
    universe = all_single_names()
    indices = all_indices()

    with console.status("[bold cyan]Fetching pre-market prices..."):
        snaps = fetch_snapshots(universe, max_workers=args.workers)
        idx_snaps = fetch_snapshots(indices, max_workers=args.workers)

    if args.no_news:
        news_by_ticker = {}
        macro = []
    else:
        with console.status("[bold cyan]Fetching news (per-ticker + macro)..."):
            news_by_ticker = fetch_ticker_news(
                universe, lookback_hours=args.lookback, max_workers=args.workers
            )
            macro = fetch_macro_headlines(lookback_hours=args.lookback)

    ranked = rank(
        snaps,
        news_by_ticker,
        top_n=args.top,
        sector_cap=args.sector_cap,
    )

    render_briefing(idx_snaps, ranked, macro, console=console)

    if args.csv:
        _export_csv(args.csv, ranked)
        console.print(f"[dim]CSV written to {args.csv}[/dim]")
    if args.json:
        _export_json(args.json, ranked, idx_snaps, macro)
        console.print(f"[dim]JSON written to {args.json}[/dim]")

    return 0


if __name__ == "__main__":
    sys.exit(main())
