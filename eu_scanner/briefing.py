"""Renders the morning briefing to the terminal."""

from __future__ import annotations

from datetime import datetime, timezone

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .news import Headline
from .prices import PriceSnapshot
from .ranking import RankedItem


def _color_pct(pct: float | None) -> Text:
    if pct is None:
        return Text("n/a", style="dim")
    style = "bold green" if pct > 0 else ("bold red" if pct < 0 else "white")
    return Text(f"{pct:+.2f}%", style=style)


def render_briefing(
    indices: list[PriceSnapshot],
    watchlist: list[RankedItem],
    macro: list[Headline],
    console: Console | None = None,
) -> None:
    console = console or Console()
    now = datetime.now(timezone.utc)

    header = Text(
        f"  EUROPEAN MORNING SCANNER  —  {now.strftime('%a %d %b %Y, %H:%M UTC')}",
        style="bold white on blue",
    )
    console.print(header)
    console.print()

    # ---------- 1) Macro / index context ----------
    idx_table = Table(
        title="Index context",
        title_style="bold cyan",
        header_style="bold",
        expand=True,
    )
    idx_table.add_column("Index", style="cyan")
    idx_table.add_column("Last", justify="right")
    idx_table.add_column("Prev close", justify="right")
    idx_table.add_column("Move", justify="right")
    for s in sorted(indices, key=lambda x: x.underlying.country):
        if s.last is None or s.prev_close is None:
            continue
        idx_table.add_row(
            s.underlying.name,
            f"{s.last:,.2f}",
            f"{s.prev_close:,.2f}",
            _color_pct(s.change_pct),
        )
    console.print(idx_table)
    console.print()

    # ---------- 2) Top 20 watchlist ----------
    wl_table = Table(
        title=f"Top {len(watchlist)} to track on the desk",
        title_style="bold yellow",
        header_style="bold",
        expand=True,
    )
    wl_table.add_column("#", justify="right", style="dim")
    wl_table.add_column("Ticker", style="bold")
    wl_table.add_column("Name")
    wl_table.add_column("Sec", style="dim")
    wl_table.add_column("Cty", style="dim")
    wl_table.add_column("Move", justify="right")
    wl_table.add_column("RelVol", justify="right")
    wl_table.add_column("Score", justify="right")
    wl_table.add_column("Why")

    for i, it in enumerate(watchlist, 1):
        s = it.snap
        rv = f"{s.rel_volume:.1f}x" if s.rel_volume else "—"
        wl_table.add_row(
            str(i),
            s.underlying.ticker,
            s.underlying.name,
            s.underlying.sector,
            s.underlying.country,
            _color_pct(s.change_pct),
            rv,
            f"{it.score:.2f}",
            ", ".join(it.reasons) or "—",
        )
    console.print(wl_table)
    console.print()

    # ---------- 3) Top headlines per name (compact) ----------
    news_table = Table(
        title="Headlines on watchlist names",
        title_style="bold magenta",
        header_style="bold",
        expand=True,
    )
    news_table.add_column("Ticker", style="bold")
    news_table.add_column("Age", justify="right", style="dim")
    news_table.add_column("Source", style="dim")
    news_table.add_column("Headline")

    any_news = False
    for it in watchlist:
        for h in it.news.headlines[:2]:
            any_news = True
            age = f"{h.age_hours(now):.1f}h" if h.published else "—"
            news_table.add_row(it.snap.underlying.ticker, age, h.source[:18], h.title[:110])
    if any_news:
        console.print(news_table)
        console.print()

    # ---------- 4) Macro headlines ----------
    macro_panel_lines = []
    for h in macro[:12]:
        age = f"[{h.age_hours(now):.1f}h]" if h.published else "[—]"
        macro_panel_lines.append(f"{age:>6} {h.source[:22]:<22}  {h.title[:110]}")
    if macro_panel_lines:
        console.print(
            Panel(
                "\n".join(macro_panel_lines),
                title="Macro / overnight headlines",
                title_align="left",
                border_style="green",
            )
        )

    console.print()
    console.print(
        Text(
            "Coffee. Check the levels. Trade the plan.",
            style="italic dim",
        )
    )
