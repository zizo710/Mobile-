# EU Morning Scanner

A pre-open scanner for European equity markets. Pulls overnight price moves
and news headlines across ~100 large-cap names from the UK, Germany, France,
Netherlands, Switzerland, Italy, Spain, and the Nordics, then ranks them
into a **20-name watchlist** to focus on when you sit down at the desk.

## What it gives you

1. **Index context** — overnight moves on Euro Stoxx 50, Stoxx 600, FTSE 100,
   DAX, CAC, IBEX, FTSE MIB, AEX, SMI.
2. **Top 20 watchlist** — ranked by:
   - gap size (normalised by recent range, so noise is filtered)
   - relative volume vs 20-day average
   - presence of a news catalyst (earnings, M&A, guidance, ratings, etc.)
   - number and freshness of overnight headlines
   - sector cap so the list stays diversified
3. **Per-name headlines** — top 2 catalysts per ranked name.
4. **Macro / overnight headlines** — ECB, BoE, Bundesbank, Reuters, FT.

## Install

```bash
pip install -r requirements.txt
# or as a package:
pip install -e .
```

## Run

```bash
# Default: top 20 names, 18-hour news lookback, sector cap 4
python -m eu_scanner

# Or via the installed entry point
eu-scan

# Common variants
eu-scan --top 25 --lookback 24
eu-scan --no-news               # quick, prices only
eu-scan --csv watchlist.csv     # export the table
eu-scan --json briefing.json    # full machine-readable briefing
```

Run it as part of your morning routine — kick it off while the kettle's on,
the briefing prints in 15-30 seconds depending on network.

## How the score works

```
score = 1.5 * normalised_gap            # |move %| / (recent 5d range / 5)
      + 0.6 * min(rel_volume, 5)        # confirming volume
      + 0.4 * min(news_count, 5)        # information density
      + 1.5 + 0.3 * catalyst_count      # bonus if a catalyst keyword hits
```

A sector cap (default 4 names per GICS-style sector) is applied after the
sort so you don't end up with a watchlist of eight banks.

## Universe

~100 European single names, plus 9 indices for context. See
[`eu_scanner/universe.py`](eu_scanner/universe.py) — edit freely to match
your book.

## Caveats

- Prices come from Yahoo Finance (yfinance). True pre-market on European
  cash equities is thin; the scanner uses the latest available tick vs.
  prior close, which captures overnight gaps from Asia / US sessions and
  any pre-open quote when present.
- News uses Yahoo's per-ticker feed plus a handful of public RSS feeds.
  This is a starting point — for a real desk, swap in your Bloomberg /
  Reuters / RNS terminal feed by extending `eu_scanner/news.py`.
- Not investment advice. Use as a triage tool, not a signal.
