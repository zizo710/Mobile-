"""Decision logic: reconcile the live position with the strategy signal."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import MIN_ORDER_USD, Config
from .exchange import round_size_down
from .strategy import Signal, closed_candles, compute_signal

log = logging.getLogger("hl_bot")


@dataclass
class State:
    start_ms: int = 0  # when the bot first ran; PnL is measured from here
    expected_side: int = 0  # side of the position the bot believes it holds
    blocked_side: int = 0  # side that was stopped out; no re-entry until the signal flips
    halted: bool = False

    @classmethod
    def load(cls, path: str) -> "State":
        p = Path(path)
        if p.exists():
            return cls(**json.loads(p.read_text()))
        return cls(start_ms=int(time.time() * 1000))

    def save(self, path: str) -> None:
        Path(path).write_text(json.dumps(asdict(self), indent=2))


def target_size(cfg: Config, price: float, sz_decimals: int) -> float:
    """Position size in coins, capped by the budget. 0.0 if below the exchange minimum."""
    size = round_size_down(cfg.notional_usd / price, sz_decimals)
    return size if size * price >= MIN_ORDER_USD else 0.0


def stop_price(side: int, entry_px: float, stop_pct: float) -> float:
    return entry_px * (1 - stop_pct) if side > 0 else entry_px * (1 + stop_pct)


def has_stop(orders: list[dict]) -> bool:
    return any(o.get("isTrigger") and o.get("reduceOnly") for o in orders)


class Bot:
    def __init__(self, cfg: Config, client, state: State, live: bool):
        self.cfg, self.client, self.state, self.live = cfg, client, state, live

    def _do(self, description: str, action) -> None:
        if self.live:
            log.info("%s", description)
            action()
        else:
            log.info("[dry-run] would %s", description)

    def signal(self) -> Signal:
        cfg = self.cfg
        candles = closed_candles(self.client.candles(cfg.slow * 6), int(time.time() * 1000))
        return compute_signal(
            candles, cfg.fast, cfg.slow, cfg.atr_period, cfg.atr_mult, cfg.min_stop_pct, cfg.max_stop_pct
        )

    def tick(self) -> None:
        cfg, state, client = self.cfg, self.state, self.client
        if state.halted:
            log.warning("Bot is halted (loss limit hit). Delete %s to reset.", cfg.state_path)
            return

        pos = client.position()
        pnl = client.realized_pnl_since(state.start_ms) + pos.unrealized_pnl
        if pnl <= -cfg.max_loss_usd:
            log.warning("Loss limit hit (PnL $%.2f). Flattening and halting.", pnl)
            self._do("cancel open orders and close the position", self._flatten)
            if self.live:
                state.halted, state.expected_side = True, 0
            return

        sig = self.signal()
        desired = sig.side if (sig.side > 0 or cfg.allow_short) else 0
        log.info(
            "%s %s signal=%+d price=%.1f stop=%.2f%% position=%g pnl=$%.2f",
            cfg.coin, cfg.interval, sig.side, sig.price, sig.stop_pct * 100, pos.size, pnl,
        )
        if sig.side == 0:
            log.info("Not enough candle history yet; doing nothing.")
            return

        max_size = target_size(cfg, sig.price, client.sz_decimals)
        if pos.side and abs(pos.size) > max_size * 1.5:
            log.error(
                "Existing %s position (%g) is larger than this bot would ever open (%g). "
                "Not touching it — close it manually or use a different coin.",
                cfg.coin, pos.size, max_size,
            )
            return

        if state.expected_side and not pos.side:  # position vanished: the stop fired
            log.info("Position was stopped out; waiting for the signal to flip before re-entering.")
            state.blocked_side, state.expected_side = state.expected_side, 0
        if state.blocked_side and desired != state.blocked_side:
            state.blocked_side = 0

        cur = pos.side
        if cur and cur != desired:
            self._do("cancel open orders and close the position (signal flipped)", self._flatten)
            if self.live:
                state.expected_side = 0
            cur = 0

        if not cur and desired and desired != state.blocked_side:
            if max_size <= 0:
                log.error("Budget too small for the $%.0f minimum order.", MIN_ORDER_USD)
                return
            self._do(
                f"open {'LONG' if desired > 0 else 'SHORT'} {max_size:g} {cfg.coin} "
                f"(~${max_size * sig.price:.2f}) with a {sig.stop_pct:.2%} stop",
                lambda: self._enter(desired, max_size, sig),
            )
        elif cur and not has_stop(client.open_orders()):
            trigger = stop_price(cur, pos.entry_px, sig.stop_pct)
            self._do(
                f"place missing stop at {trigger:.1f}",
                lambda: client.place_stop(cur, abs(pos.size), trigger),
            )

    def _flatten(self) -> None:
        self.client.cancel_all()
        self.client.market_close()

    def _enter(self, side: int, size: float, sig: Signal) -> None:
        client = self.client
        client.set_isolated_leverage()
        filled = client.market_open(side, size)
        if filled <= 0:
            log.warning("Entry order did not fill; will retry next tick.")
            return
        self.state.expected_side = side
        pos = client.position()
        entry = pos.entry_px or sig.price
        client.place_stop(side, filled, stop_price(side, entry, sig.stop_pct))

    def run(self, once: bool = False) -> None:
        while True:
            try:
                self.tick()
            except Exception:  # keep running through API hiccups; the exchange-side stop stays in place
                log.exception("Tick failed")
            if self.live:
                self.state.save(self.cfg.state_path)
            if once or self.state.halted:
                return
            time.sleep(self.cfg.poll_seconds)
