# Valuation-Anchored Alternative: Selected Trades with Live Strikes and Prices

*Companion to [`us-market-2026-vs-1998-2002.md`](us-market-2026-vs-1998-2002.md)
and [`single-name-convexity-2026.md`](single-name-convexity-2026.md).
Quotes are CBOE delayed data, 30 July 2026 ~21:25 UTC; prices are mid of
bid/ask and will have moved. Educational analysis, not investment advice or a
recommendation to transact.*

---

## Why an alternative book exists at all

Pulling live option chains changed the answer. The archetype book (doc #2)
was designed from fundamentals; repricing it against the actual July 30
market shows the crowd got there first:

| Name | Trade thesis | Live IV (Jan-28 tenor) | Verdict |
|---|---|---|---|
| CRWV | debt-spiral zero ticket | **~92–95%** | CDS at 50% default odds; a Jan-28 $35P costs $7.38 mid and pays only ~4.7x even if the equity goes to zero. The bust is priced |
| MU | memory-cycle unwind | **~82–84%** | A Jan-28 800/600 put spread costs ~$109 ($10,890/contract) — physically impossible in a $5k book and priced for the crash it predicts |
| ORCL | Lucent-shaped credit transmission | **~70–72%** | Stock already at ~$128.66 (multi-month lows, index at highs) and vol at distress levels; a Jan-28 110/80 put spread costs $13.47 to make at most $30 (2.2:1). The market agrees with the thesis — and charges for it |
| PLTR | multiple compression (41x sales) | ~59–62% | Expensive but tradeable via spreads — the one bear thesis where equity price hasn't followed |
| SMH | semis/cycle beta | ~49–53% | Half of MU's vol for correlated exposure |
| NVDA | stalled-general melt-up | ~41–42% | Reasonable vol on the lagging leader |
| GOOGL | quality repriced by capex panic | **~35%** | Cheapest megacap vol in the complex |
| XLE | energy: the 2000-style value rotation | **~24–27%** | Cheapest vol on the board, on the cheapest assets, with a live macro catalyst |

This is the inverse of 1999, when crash insurance on the bubble names was
almost free because nobody believed the bust. In 2026 the options market has
read the same history everyone else has: **you cannot buy the consensus bear
case at prices that pay**. Valuation discipline applied to the *options*
themselves pushes the book toward cheap vol on mispriced assets — long the
punished quality and the ignored value, short the true valuation extremes via
spreads that sell the inflated wing.

---

## What the quarterly reports actually say

The two most recent prints (both this week / last week) frame the divergence
the book trades:

**Microsoft (FQ4-26, 29 Jul):** EPS $4.74 vs $4.24 expected; Azure past
$100B annual revenue, +43%; backlog $678B; quarterly operating cash flow
$55.4B (+30%). FY26 capex $116B (+80% y/y) — and FY27 guided to **$255–260B**.
The market added ~$260B of value in an evening: proof that AI capex funded
from a cash machine of this size is (for now) rewarded, not punished.

**Alphabet (Q2-26, 22 Jul):** revenue $119.8B (+24%); Cloud +82% to $24.8B;
cloud backlog $514B; operating income $40.8B (+30%, 34% margin). Headline EPS
$9.11 was inflated by $98B of one-off equity gains — but the *operating*
print was excellent. The stock sold off anyway on the capex raise (to
$195–205B) and the first negative-FCF quarter in its history. At ~$334
(≈$4T), the market is paying roughly 25x annualized operating income for 24%
growth and the fastest-growing hyperscaler cloud — the cheapest
growth-adjusted franchise among the megacaps.

**The rest of the cast, latest reported quarters:** Oracle — FY26 FCF
−$23.7B, net debt $97.6B, ~$40B/yr of external funding needed, half the $638B
backlog one customer (already −60%-ish from its highs at $128.66; the market
has done much of the re-rating). Micron — revenue +346% y/y at $887.60 after
a +230–300% YTD run; peak-cycle earnings make trailing multiples *look* sane,
the classic commodity-top illusion (memory P/E is lowest at the top, because
E is the thing that mean-reverts). Palantir — revenue +85%, guidance +71%,
and still **~41x sales / ~84x forward earnings** at $122.83: the one name
where the equity price has not conceded anything to the bear case. Nvidia —
DC revenue +92%, ~30x forward, +3–9% YTD at $195.25: growth outrunning the
multiple all year. CoreWeave — revenue $2.08B/qtr (+112%) vs $7.7B/qtr capex,
$17.3B debt, CDS at ~50%: the bust already has a market price.

---

## The selected trades ($5,000 book, mid prices as of 30 Jul 2026)

| # | Trade | Legs (real quotes) | Cost/contract | Qty | Outlay | Max value | Payoff |
|---|---|---|---|---|---|---|---|
| 1 | **GOOGL bull call spread** — quality at panic prices | Buy 17-Jun-27 $380C @ $30.95 / Sell 17-Jun-27 $440C @ $16.65 | $14.30 → **$1,430** | 1 | $1,430 | $6,000 | 4.2 : 1 |
| 2 | **NVDA bull call spread** — the stalled general | Buy 19-Mar-27 $220C @ $18.38 / Sell 19-Mar-27 $260C @ $8.68 | $9.70 → **$970** | 1 | $970 | $4,000 | 4.1 : 1 |
| 3 | **XLE long calls** — the 2000 value-rotation, uncapped | Buy 21-Jan-28 $65C @ $5.65 (IV ~27%) | $5.65 → **$565** | 1 | $565 | uncapped | — |
| 4 | **PLTR bear put spread** — the multiple with no floor | Buy 21-Jan-28 $90P @ $14.15 / Sell 21-Jan-28 $70P @ $7.38 | $6.77 → **$677** | 1 | $677 | $2,000 | 3.0 : 1 |
| 5 | **SMH bear put spread** — the cycle, at half MU's vol | Buy 21-Jan-28 $380P @ $41.50 / Sell 21-Jan-28 $340P @ $30.50 | $11.00 → **$1,100** | 1 | $1,100 | $4,000 | 3.6 : 1 |
| | **Total** | | | **$4,742** | | ~$260 residual for fees/adjustment | |

### Breakevens and what each trade needs

1. **GOOGL 380/440 Jun-27** — breakeven $394.30 (+18% from $334.25), max at
   $440 (+32%). Needs: capex panic to fade or Cloud (+82%, $514B backlog) to
   keep converting. Four earnings cycles of runway. This replaces a
   generic "melt-up" leg with the megacap where the quarterly report and the
   stock price disagree most.
2. **NVDA 220/260 Mar-27** — breakeven $229.70 (+17.6%), max at $260 (+33%).
   The Act-3 trade: if the final leg comes, history says it runs through the
   biggest lagging general. Mar-27 expiry deliberately brackets the melt-up
   window (Sept-26 hike + ~6–9 months, the 1999→2000 clock) without paying
   for time the thesis doesn't use.
3. **XLE Jan-28 $65C** — breakeven $70.65 (+19.8%), no cap, 18 months. In
   1999–2000 oil tripled while tech monopolized attention; energy then
   outperformed through the entire bust. Oil is again rising on a Middle
   East conflict while energy trades at cycle-low valuations — and 25% IV
   means this is the only thesis on the board you can still buy cheaply
   *unspread*. Note it also quietly hedges the bear legs: the scenario that
   breaks tech (oil → inflation → hikes) is bullish this leg.
4. **PLTR 90/70 Jan-28** — breakeven $83.23 (−32% from $122.83), max at $70
   (−43%). Deliberately deep: at 41x sales, a −43% move still leaves ~23x
   sales, i.e. this pays only on a genuine multiple-regime change — which is
   the thesis. Its own 2022 precedent (−85% while revenue grew) covers the
   distance twice over. The only bear name where the stock hasn't conceded.
5. **SMH 380/340 Jan-28** — breakeven $369 (−32% from $543), max at $340
   (−37%). The memory/semis cycle bear at ~50% IV instead of MU's ~83%; the
   ETF wrapper is the concession to contract-size reality (one MU spread
   costs more than this entire book). Paired with leg 2 it is implicitly a
   relative-value position: the general (NVDA ~20% of SMH) outperforms the
   complex on the way up, and the complex falls harder on the way down.

### Scenario P&L (approximate, at expiries, before fees)

| Scenario (odds from doc #1) | Book outcome |
|---|---|
| Melt-up first (~50% path odds) | Legs 1–3 toward max: up to ~+$8,000 on $4,742; bear legs likely lose their $1,777 |
| Corrections/chop, no bust (35–40%) | The enemy: most legs bleed; expect −$3,000 to −$4,700. This remains a convexity book, not an income book |
| Serious bear (30–35%) | Legs 4–5 toward max (+$4,223 profit); longs lose $2,965; XLE depends on whether oil caused it — net roughly +$1,200 to +$2,500 |
| Full bust (10–15%) | Same as above but with legs 4–5 pinned at max; tilt bearward (drop leg 2, double leg 5) if the signposts fire first |

The two-sided structure means the bust pays *modestly*, not spectacularly —
that is the price of not being wrong alone in the ~50% melt-up world, and it
is the deliberate difference from doc #2's bear-heavy archetype book. The
signal list from doc #2 still governs adjustments: a failed rally at a lower
high or a 2027 capex guide-down converts this book bearward (roll leg 1's
profits into leg 5 size); a September hike taken badly shortens leg 2's leash.

### Execution notes

- All prices are **mids**; ORCL and MU quotes carry $1–15 bid/ask spreads —
  another tax on the consensus bear trades. GOOGL/NVDA/XLE/PLTR markets are
  tight and deep (OI in the thousands at every strike used).
- Work limits at mid, never market orders; on four-figure-premium spreads a
  $0.50 fill improvement is 3–5% of the sleeve.
- Earnings binaries inside the tenors: PLTR reports in early August — the
  put spread can be entered after the print to avoid one coin-flip, at the
  cost of chasing if it gaps down.
- Every leg is defined-risk; there are no naked short options anywhere, and
  the maximum loss of the entire book is the $4,742 paid.

---

## Sources

- CBOE delayed option chains (ORCL, PLTR, MU, GOOGL, XLE, NVDA, CRWV, SMH),
  30 Jul 2026 ~21:25 UTC, via cdn.cboe.com delayed-quotes API. Spots: ORCL
  $128.66, PLTR $122.83, MU $887.60, GOOGL $334.25, XLE $58.99, NVDA
  $195.25, CRWV $75.08, SMH $543.00.
- [CNBC — Alphabet Q2 2026 earnings: revenue beat, stock sinks on capex hike](https://www.cnbc.com/2026/07/22/google-earnings-q2-goog-live-updates.html)
- [Seeking Alpha — Alphabet Q2: cloud +82%, capex disappoints](https://seekingalpha.com/news/4616900-alphabet-delivers-q2-beat-with-cloud-revenue-surging-82-capex-disappoints)
- [Investing.com — Alphabet Q2 2026 earnings call transcript](https://www.investing.com/news/transcripts/earnings-call-transcript-alphabet-beats-q2-2026-estimates-shares-fall-on-capex-surge-93CH-4807140)
- [indmoney — Microsoft Q4 FY26 results: why MSFT jumped](https://www.indmoney.com/blog/us-stocks/microsoft-q4-results-why-msft-stock-jumped)
- [TradingKey — MSFT Q4 FY26 preview: Azure ~40%, FY27 capex $255–260B](https://www.tradingkey.com/analysis/stocks/us-stocks/262060902-microsoft-msft-q4-fy2026-earnings-preview-july-29-azure-capex-tradingkey)
- Prior-quarter figures for ORCL, MU, PLTR, NVDA, CRWV: sources as cited in
  [`single-name-convexity-2026.md`](single-name-convexity-2026.md).
