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
    a = p.parse_args(argv)
    warnings.filterwarnings("ignore", category=FutureWarning)

    from . import pipeline, report

    r = pipeline.run(refresh=a.refresh, overrides=dict(a.shock))
    path = report.build(r, Path(a.out))
    v, ve, t = r.val, r.val_enso, r.val.target_year
    print(f"Cocoa crop year {t - 1}/{t % 100:02d}")
    print(f"  weather->output skill   CV R2 {r.ym.cv_r2:+.2f}")
    print(f"  W. Africa supply nowcast {r.wa_nowcast[t]:+.1%} vs trend")
    print(f"  futures strip           ${v.futures_strip:,.0f}/t")
    print(f"  fair value              ${v.fair_value:,.0f}/t  (68%: ${v.band68[0]:,.0f}-${v.band68[1]:,.0f})"
          f"  -> {v.verdict} ({v.mispricing_pct:+.1%}, z {v.z:+.2f})")
    print(f"  fair value incl. ENSO   ${ve.fair_value:,.0f}/t  -> {ve.verdict} ({ve.mispricing_pct:+.1%}, z {ve.z:+.2f})")
    print(f"  report: {path}")
    return 0
