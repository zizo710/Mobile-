"""Command line entry point: python -m copper_model"""
from __future__ import annotations

import argparse
import warnings
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="copper-model", description=__doc__)
    p.add_argument("--refresh", action="store_true", help="ignore the data cache and re-download")
    p.add_argument("--out", default="reports", help="output directory (default: reports)")
    a = p.parse_args(argv)
    warnings.filterwarnings("ignore")

    from . import pipeline, report

    r = pipeline.run(refresh=a.refresh)
    path = report.build(r, Path(a.out))
    print(f"Copper  front ${r.spot:.2f}/lb   {r.fut12_contract} ${r.fut12:.2f}   fair value (12m) ${r.fair:.2f}"
          f"  -> {r.verdict} ({r.gap:+.1%}, z {r.z:+.2f})")
    print(f"  drivers in model: {', '.join(r.live.selected) or 'none'}   forecast {r.live.forecast:+.1%}")
    print(f"  walk-forward skill: R2 {r.wf[pipeline.MAIN].r2:+.2f}")
    print(r.bt.hedge_stats[["Return / year", "Sharpe", "Worst quarter", "Max drawdown"]].round(3).to_string())
    print(f"  report: {path}")
    return 0
