"""CLI entry point: `python -m hl_bot` or `hl-bot`."""

from __future__ import annotations

import argparse
import logging
import sys

from .backtest import run_backtest
from .bot import Bot, State
from .config import Config, load_dotenv
from .exchange import HyperliquidClient


def _cmd_run(cfg: Config, args) -> int:
    live = args.live
    if live and not (cfg.api_wallet_key and cfg.account_address):
        print("--live needs HL_ACCOUNT_ADDRESS and HL_API_WALLET_KEY (see .env.example).", file=sys.stderr)
        return 2
    client = HyperliquidClient(cfg)
    mode = "LIVE" if live else "DRY-RUN (no orders will be sent)"
    logging.getLogger("hl_bot").info(
        "%s on %s: %s %s, budget $%.2f, %dx isolated, position ~$%.2f, loss limit $%.2f",
        mode, cfg.network, cfg.coin, cfg.interval, cfg.budget_usd, cfg.leverage, cfg.notional_usd, cfg.max_loss_usd,
    )
    Bot(cfg, client, State.load(cfg.state_path), live).run(once=args.once)
    return 0


def _cmd_status(cfg: Config, args) -> int:
    client = HyperliquidClient(cfg)
    bot = Bot(cfg, client, State.load(cfg.state_path), live=False)
    sig, pos = bot.signal(), client.position()
    print(f"network   : {cfg.network}")
    print(f"signal    : {'LONG' if sig.side > 0 else 'SHORT' if sig.side < 0 else 'n/a'} ({cfg.coin} {cfg.interval})")
    print(f"price     : {sig.price:.1f}   stop distance: {sig.stop_pct:.2%}")
    print(f"position  : {pos.size:g} @ {pos.entry_px:.1f}   unrealized ${pos.unrealized_pnl:.2f}")
    print(f"open orders on {cfg.coin}: {len(client.open_orders())}")
    print(f"halted    : {bot.state.halted}")
    return 0


def _cmd_backtest(cfg: Config, args) -> int:
    client = HyperliquidClient(cfg)
    candles = client.candles(args.bars)
    res = run_backtest(candles[:-1], cfg)  # drop the still-forming candle
    days = (candles[-1].t - candles[0].t) / 86_400_000
    print(f"{cfg.coin} {cfg.interval}, {len(candles)} candles (~{days:.0f} days), position ${cfg.notional_usd:.2f}")
    print(f"trades        : {res.trades} ({res.wins} winners, {res.stops} stopped out)")
    print(f"net PnL       : ${res.pnl_usd:+.2f} after fees and slippage")
    print(f"max drawdown  : ${res.max_drawdown_usd:.2f}")
    print(f"buy and hold  : ${res.buy_hold_usd:+.2f} on the same position size")
    if res.halted:
        print(f"NOTE: the ${cfg.max_loss_usd:.2f} loss limit was hit and the run stopped early.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hl-bot", description="Small-book trend bot for Hyperliquid perps.")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run the bot (dry-run unless --live)")
    run.add_argument("--live", action="store_true", help="actually send orders")
    run.add_argument("--once", action="store_true", help="evaluate once and exit (for cron)")
    sub.add_parser("status", help="show the current signal, position and orders")
    bt = sub.add_parser("backtest", help="replay the strategy on recent history")
    bt.add_argument("--bars", type=int, default=2000, help="number of candles to replay")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    load_dotenv()
    try:
        cfg = Config.from_env()
    except ValueError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2
    return {"run": _cmd_run, "status": _cmd_status, "backtest": _cmd_backtest}[args.command](cfg, args)


if __name__ == "__main__":
    raise SystemExit(main())
