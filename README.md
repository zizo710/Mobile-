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

---

# Cocoa Model

Is the cocoa futures market over- or undervalued given the West African crop?
`cocoa_model` chains three steps using only free public data:

1. **Weather → harvest.** NASA POWER daily weather at 16 cocoa-belt points in
   Côte d'Ivoire, Ghana, Nigeria and Cameroon is turned into seasonal anomalies
   around the crop calendar. Together with climate indices and farm economics
   these are candidate drivers of FAOSTAT production deviations from trend.
   Each country gets its own ridge model, built by forward selection and scored
   by nested leave-one-year-out cross-validation; a country without
   out-of-sample skill is held at trend.
2. **Harvest → price.** Crop-year real cocoa prices (World Bank / ICCO) are
   regressed on current and lagged West African supply shocks plus mean
   reversion. Extra market variables are added only if they lower
   out-of-sample forecast error.
3. **Valuation.** The model's fair value for the coming crop year is compared
   with the live ICE New York futures strip, with a forecast band and z-score.

The report includes a scorecard for 20 added data points (weather extremes,
Atlantic and Indian Ocean indices, fertiliser and cocoa prices, rest-of-world
output, GDP, sugar, palm oil, volatility) and a test of 5 unconventional ones
(sunspots, QBO, gold, rubber, Easter date), which are never used in the
headline model.

```bash
python -m cocoa_model                    # writes reports/cocoa_report.md + charts
python -m cocoa_model --refresh          # ignore the 24h data cache
python -m cocoa_model --shock 2027=-0.08 # your own crop view: 2026/27 8% below trend
python -m cocoa_model --backtest         # also run the futures backtests (unhedged and with options)
```

The latest run is in [`reports/cocoa_report.md`](reports/cocoa_report.md), and the
walk-forward backtest of a long/short futures strategy on the model's signal is in
[`reports/backtest_report.md`](reports/backtest_report.md). The same strategy with
protective puts and calls is in [`reports/hedged_report.md`](reports/hedged_report.md). Read its
caveats: on public annual data the weather signal is weak, and the model has no
stocks, demand or positioning data. Not investment advice.
