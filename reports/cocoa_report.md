# West African cocoa: weather, harvest and futures valuation

*Run date 12 Nov 2026 · futures as of 11 Nov 2026 18:29 UTC · target crop year 2026/27 (Oct 2026 – Sep 2027)*

## Verdict

**ICE New York cocoa futures for 2026/27 average $5,074/t; the model's fair value is
$5,065/t (68% band $4,053 – $6,330). The market is roughly fairly valued
(+0.2% vs fair value, z = +0.01).**

Adding the current ENSO state (ONI +2.0) lifts fair value to $5,580/t, which would make
futures roughly fairly valued (-9.1%, z = -0.44). Neither gap is statistically
meaningful: one standard deviation of the forecast is about ±22%.

| Model | Fair value | 68% band | 90% band | Futures vs fair | z-score | Verdict |
|---|---|---|---|---|---|---|
| Supply + mean reversion (headline) | $5,065 | $4,053 – $6,330 | $3,510 – $7,309 | +0.2% | +0.01 | roughly fairly valued |
| …plus ENSO term (sensitivity) | $5,580 | $4,486 – $6,940 | $3,897 – $7,989 | -9.1% | -0.44 | roughly fairly valued |

![Price and fair value](price_fair_value.png)

## 1. Weather → harvest

Production data: FAOSTAT, 1961–2024, for Côte d'Ivoire, Ghana, Nigeria, Cameroon.
Target is each country's output deviation from its HP trend. Weather is NASA POWER daily data
averaged over 16 cocoa-belt points, turned into seasonal anomalies (σ) around the crop calendar:

- **dry0** – Dry season before flowering (Nov H-2 – Mar H-1): tree stress / carry-over
- **rains1** – Main rains (Apr–Jul H-1): flowering and pod set of the main crop
- **aug** – Little dry season (Aug H-1): pod filling
- **rains2** – Short rains (Sep–Oct H-1): pod maturation; excess → black pod
- **dry1** – Harmattan dry season (Nov H-1 – Mar H): main-crop tail, mid-crop set
- **rains3** – Apr–Jun H: mid-crop development

| Weather feature | CIV | GHA | NGA | CMR | Pooled |
|---|---|---|---|---|---|
| Rain, prior dry season (Nov–Mar) | -0.05 | -0.02 | +0.14 | -0.00 | +0.03 |
| Max temp, prior dry season | +0.08 | -0.07 | -0.14 | -0.37 | -0.10 |
| Rain, main rains (Apr–Jul) | -0.04 | -0.15 | -0.01 | +0.14 | -0.03 |
| Rain extremes, main rains | +0.01 | -0.10 | +0.07 | -0.07 | -0.00 |
| Soil moisture, main rains | -0.11 | -0.09 | +0.18 | +0.34 | +0.07 |
| Rain, August | +0.47 | -0.05 | +0.02 | +0.42 | +0.15 |
| Rain, short rains (Sep–Oct) | -0.01 | +0.34 | -0.01 | +0.07 | +0.11 |
| Rain extremes, short rains | -0.22 | -0.02 | +0.18 | -0.16 | -0.06 |
| Sunshine, short rains | +0.27 | +0.27 | +0.00 | -0.01 | +0.13 |
| Rain, harmattan (Nov–Mar) | -0.21 | -0.08 | -0.07 | +0.04 | -0.08 |
| Max temp, harmattan | -0.04 | -0.27 | +0.22 | -0.12 | -0.05 |
| Humidity, harmattan | +0.05 | +0.24 | -0.08 | +0.08 | +0.07 |
| Rain, Apr–Jun of harvest year | -0.09 | -0.22 | +0.04 | +0.33 | +0.00 |
| ENSO (ONI, Jun–Oct) | -0.14 | -0.11 | +0.18 | +0.20 | +0.03 |

![Correlations](weather_yield_correlations.png)

**Reading it.** A handful of links have the agronomically expected sign – a wet August and a sunny
Sep–Oct help Côte d'Ivoire, a hot prior dry season hurts Cameroon, short-rains rainfall helps Ghana –
but correlations are small (|r| mostly < 0.3 on ~40 years per country) and inconsistent
across countries.

**Predictive skill.** Pooled ridge regression (160 country-years, leave-one-year-out):
cross-validated R² = -0.01, correlation of predicted vs actual West African output = -0.13.
That is **no measurable out-of-sample skill**: on public annual data, seasonal weather does not forecast output deviations.
Structural drivers (swollen-shoot virus, ageing trees, farm-gate prices, smuggling, illegal mining
in Ghana) and FAOSTAT measurement noise dominate.

![Supply](west_africa_supply.png)

### Current season

| Observed so far for 2026/27 | CIV | GHA | NGA | CMR |
|---|---|---|---|---|
| Rain, prior dry season (Nov–Mar) | +2.1σ | +3.2σ | +0.2σ | -0.6σ |
| Max temp, prior dry season | +0.2σ | -1.6σ | +2.3σ | +2.2σ |
| Rain, main rains (Apr–Jul) | +0.1σ | +3.4σ | +2.2σ | -0.1σ |
| Soil moisture, main rains | +0.1σ | +2.7σ | +1.3σ | -1.2σ |
| Rain, August | -1.4σ | +0.3σ | -0.4σ | -0.4σ |
| Rain, short rains (Sep–Oct) | -1.0σ | -1.1σ | -0.3σ | +0.4σ |
| Sunshine, short rains | +0.6σ | +0.9σ | +0.8σ | +0.1σ |

| Crop year | CIV | GHA | NGA | CMR | W. Africa | weather observed |
|---|---|---|---|---|---|---|
| 2024/25 | -0.2% | +0.3% | -0.9% | -1.4% | -0.3% | 100% |
| 2025/26 | -0.9% | -0.3% | -1.4% | -1.5% | -0.9% | 100% |
| 2026/27 | -0.2% | +0.5% | -0.0% | -0.2% | -0.1% | 71% |

Windows not yet observed are set to climatology. Because the weather model has no proven skill, the
nowcast is deliberately shrunk to ≈ trend; it carries a ±7% standard error.

## 2. Harvest → price

Crop-year average real price (World Bank / ICCO, CPI-deflated), 63 years:
`Δlog P = a + b1·S + b2·S(-1) + g·log P(-1)` where S is West African output vs trend.

| Term | coef | t-stat |
|---|---|---|
| Constant | +0.837 | +2.0 |
| Supply shock, current crop | -0.777 | -2.5 |
| Supply shock, previous crop | -1.151 | -3.6 |
| Lagged log real price | -0.098 | -2.0 |

R² = 0.31. A West African crop 10% below trend raises the real price by about
8% that season and a further 12% the next. Prices revert towards a long-run real
level of about $5,057/t at 10% a year. In expanding-window tests since 1990
this beats a no-change forecast by roughly 10% in RMSE.

With ENSO added (R² = 0.33):

| Term | coef | t-stat |
|---|---|---|
| Constant | +0.809 | +2.0 |
| Supply shock, current crop | -0.789 | -2.5 |
| Supply shock, previous crop | -1.001 | -3.0 |
| Lagged log real price | -0.095 | -1.9 |
| ENSO (ONI) | +0.051 | +1.3 |

El Niño years have tended to precede higher prices, but the term is not significant once supply
shocks are controlled for – treat it as an upside-risk scenario, not a forecast.

## 3. Futures curve

| contract | expiry | price |
|---|---|---|
| CCZ26 | 2026-12 | $4,923 |
| CCH27 | 2027-03 | $5,061 |
| CCK27 | 2027-05 | $5,110 |
| CCN27 | 2027-07 | $5,140 |
| CCU27 | 2027-09 | $5,138 |
| CCZ27 | 2027-12 | $5,113 |
| CCH28 | 2028-03 | $5,103 |
| CCK28 | 2028-05 | $5,001 |

Strip for 2026/27 = average of contracts expiring Oct 2026 – Sep 2027: **$5,074/t**.
Last completed crop year (2025/26) averaged $4,882/t.

## Caveats

- The weather → output link is not established by this data; the valuation rests mainly on the
  price-vs-supply relationship and mean reversion, starting from last season's price.
- FAOSTAT is calendar-year, revised late and ends in 2024; output for later seasons is the
  model's near-trend nowcast, not reported data. Use `--shock` to feed in your own crop estimate.
- No stocks, grindings/demand, currency, farm-gate price policy or speculative positioning.
  ICCO stocks-to-grindings would be the most valuable addition.
- ICCO price history is spliced with ICE front-month futures for the latest months.
- Forecast error is ±22% (1σ) on a one-year view. Not investment advice.
