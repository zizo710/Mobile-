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

# Hyperliquid small-book bot (`hl_bot`)

A trend-following bot that runs a **$10 book** on a Hyperliquid perpetual.
It is separate from the scanner above and runs on your own machine.

## Strategy

- **Market:** BTC perp, 4-hour candles (the most liquid market, so fees and
  slippage take the smallest bite out of a tiny account).
- **Signal:** long when the 20-period EMA is above the 50-period EMA, short
  when below. Evaluated on closed candles only.
- **Size:** about $18 of BTC (2x isolated leverage on $9 of margin). $10 is
  Hyperliquid's minimum order, so 1x leaves no room to trade.
- **Stop:** a stop-loss of 2x ATR (clamped to 1-4%) is placed on the exchange
  with every entry, so it protects the position even if the bot is offline.
  After a stop-out the bot waits for the signal to flip before re-entering.
- **Loss limit:** once the bot is down $3 in total it flattens and halts.
- **Isolated margin:** a liquidation can only take the margin on this
  position, not the rest of the account.

## Setup

1. `pip install -r requirements.txt`
2. On Hyperliquid, open **More → API**, create an API wallet and authorise it.
   Copy its private key. An API wallet can trade but cannot withdraw.
3. `cp .env.example .env` and fill in your main wallet **address** and the
   **API wallet key**. Never use your main wallet key or seed phrase.
4. Fund the perp account with at least $10 of USDC.

## Run

```bash
python -m hl_bot backtest        # replay on recent history (no account needed)
python -m hl_bot status          # current signal and position
python -m hl_bot run             # dry-run: logs what it would do, sends nothing
python -m hl_bot run --live      # sends real orders on HL_NETWORK
python -m hl_bot run --live --once   # single evaluation, for cron
```

`HL_NETWORK` defaults to `testnet`; set it to `mainnet` to trade real money.
Leave the process running (or schedule `--once` every few minutes).

## Caveats

- Don't trade the same coin by hand on the same account: the bot treats any
  position and open orders on that coin as its own.
- A backtest is not a forecast. EMA crossovers lose money in sideways
  markets, and on a $10 book a few stop-outs are a meaningful share of it.
- Not investment advice.
