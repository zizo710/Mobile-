"""Command line entry point: python -m cocoa_model"""
from __future__ import annotations

import argparse
import warnings
from pathlib import Path


def _shock(text: str) -> tuple[int, float]:
    year, val = text.split("=")
    return int(year), float(val)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="cocoa-model", description=__doc__)
    p.add_argument("--refresh", action="store_true", help="ignore the data cache and re-download")
    p.add_argument("--out", default="reports", help="output directory (default: reports)")
    p.add_argument("--shock", type=_shock, action="append", default=[], metavar="YEAR=X",
                   help="override the West African supply shock for harvest year YEAR "
                        "(log deviation from trend, e.g. 2027=-0.08 for a crop 8%% below trend)")
    p.add_argument("--backtest", action="store_true",
                   help="also run the walk-forward long/short futures backtests, unhedged and with protective options (about a minute)")
    a = p.parse_args(argv)
    warnings.filterwarnings("ignore", category=FutureWarning)

    from . import pipeline, report

    r = pipeline.run(refresh=a.refresh, overrides=dict(a.shock))
    path = report.build(r, Path(a.out))
    t = r.val.target_year
    print(f"Cocoa crop year {t - 1}/{t % 100:02d}   futures strip ${r.val.futures_strip:,.0f}/t")
    for var in (r.base, r.main, r.test):
        v = var.val
        print(f"  {var.name:<34} W.Africa skill r={var.wa_corr:+.2f}  nowcast {var.wa_nowcast[t]:+.1%}  "
              f"fair ${v.fair_value:,.0f} -> {v.verdict} ({v.mispricing_pct:+.1%}, z {v.z:+.2f})")
    print(f"  report: {path}")
    if a.backtest:
        from . import backtest, backtest_report, data

        fut = data.futures_daily(a.refresh)
        bt = backtest.run(r.prod, r.feats, r.price_cy, fut, r.ypool, t)
        bpath = backtest_report.build(bt, r.val.futures_strip, Path(a.out))
        print(bt.stats[["Average return / year", "Sharpe", "Hit rate", "Max drawdown"]].round(2).to_string())
        print(f"  report: {bpath}")
        from . import hedged, hedged_report

        hg = hedged.run(bt, fut)
        hpath = hedged_report.build(hg, bt, Path(a.out))
        print(hg.stats[["Average return / year", "Sharpe", "Worst year", "Premium / year"]].round(3).to_string())
        print(f"  report: {hpath}")
    return 0
