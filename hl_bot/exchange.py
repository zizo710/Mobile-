"""Thin wrapper around the Hyperliquid SDK: only the calls the bot needs."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

from .config import INTERVAL_MS, Config
from .strategy import Candle

STOP_LIMIT_SLIPPAGE = 0.05  # worst acceptable fill once the stop trigger fires
ENTRY_SLIPPAGE = 0.01


class OrderError(RuntimeError):
    pass


@dataclass(frozen=True)
class Position:
    size: float  # signed: positive long, negative short
    entry_px: float
    unrealized_pnl: float

    @property
    def side(self) -> int:
        return (self.size > 0) - (self.size < 0)


FLAT = Position(0.0, 0.0, 0.0)


def round_price(px: float, sz_decimals: int) -> float:
    """Perp prices: at most 5 significant figures and (6 - szDecimals) decimals."""
    return round(float(f"{px:.5g}"), 6 - sz_decimals)


def round_size_down(sz: float, sz_decimals: int) -> float:
    factor = 10**sz_decimals
    return math.floor(sz * factor + 1e-9) / factor


def _check(response: dict, what: str) -> dict:
    """Raise unless the exchange accepted the request; return the first order status."""
    if response.get("status") != "ok":
        raise OrderError(f"{what} rejected: {response}")
    data = response.get("response", {}).get("data", {})
    statuses = data.get("statuses", [])
    for status in statuses:
        if isinstance(status, dict) and "error" in status:
            raise OrderError(f"{what} rejected: {status['error']}")
    return statuses[0] if statuses and isinstance(statuses[0], dict) else {}


class HyperliquidClient:
    def __init__(self, cfg: Config):
        from hyperliquid.info import Info
        from hyperliquid.utils import constants

        self.cfg = cfg
        self.base_url = constants.MAINNET_API_URL if cfg.network == "mainnet" else constants.TESTNET_API_URL
        self.info = Info(self.base_url, skip_ws=True)
        self.exchange = None
        if cfg.api_wallet_key:
            from eth_account import Account
            from hyperliquid.exchange import Exchange

            if not cfg.account_address:
                raise ValueError("HL_ACCOUNT_ADDRESS is required when HL_API_WALLET_KEY is set")
            wallet = Account.from_key(cfg.api_wallet_key)
            self.exchange = Exchange(wallet, self.base_url, account_address=cfg.account_address)
        asset = next((a for a in self.info.meta()["universe"] if a["name"] == cfg.coin), None)
        if asset is None:
            raise ValueError(f"{cfg.coin} is not a Hyperliquid perp")
        self.sz_decimals = int(asset["szDecimals"])

    # ---- read-only -------------------------------------------------------
    def candles(self, bars: int) -> list[Candle]:
        now = int(time.time() * 1000)
        start = now - bars * INTERVAL_MS[self.cfg.interval]
        raw = self.info.candles_snapshot(self.cfg.coin, self.cfg.interval, start, now)
        return sorted((Candle.from_api(r) for r in raw), key=lambda c: c.t)

    def mid(self) -> float:
        return float(self.info.all_mids()[self.cfg.coin])

    def position(self) -> Position:
        if not self.cfg.account_address:
            return FLAT
        state = self.info.user_state(self.cfg.account_address)
        for item in state.get("assetPositions", []):
            pos = item["position"]
            if pos["coin"] == self.cfg.coin and float(pos["szi"]) != 0:
                return Position(float(pos["szi"]), float(pos["entryPx"]), float(pos["unrealizedPnl"]))
        return FLAT

    def open_orders(self) -> list[dict]:
        if not self.cfg.account_address:
            return []
        orders = self.info.frontend_open_orders(self.cfg.account_address)
        return [o for o in orders if o["coin"] == self.cfg.coin]

    def realized_pnl_since(self, start_ms: int) -> float:
        """Closed PnL minus fees on this coin since the bot started."""
        if not self.cfg.account_address:
            return 0.0
        fills = self.info.user_fills_by_time(self.cfg.account_address, start_ms)
        return sum(
            float(f.get("closedPnl", 0)) - float(f.get("fee", 0)) for f in fills if f["coin"] == self.cfg.coin
        )

    # ---- trading ---------------------------------------------------------
    def _ex(self):
        if self.exchange is None:
            raise OrderError("No API wallet key configured; cannot place orders")
        return self.exchange

    def set_isolated_leverage(self) -> None:
        _check(self._ex().update_leverage(self.cfg.leverage, self.cfg.coin, is_cross=False), "leverage update")

    def market_open(self, side: int, size: float) -> float:
        """Open a position; return the filled size (IOC orders may fill partially or not at all)."""
        status = _check(self._ex().market_open(self.cfg.coin, side > 0, size, slippage=ENTRY_SLIPPAGE), "entry order")
        return float(status.get("filled", {}).get("totalSz", 0.0))

    def market_close(self) -> None:
        response = self._ex().market_close(self.cfg.coin)
        if response is not None:  # SDK returns None when there is nothing to close
            _check(response, "close order")

    def place_stop(self, position_side: int, size: float, trigger_px: float) -> None:
        trigger = round_price(trigger_px, self.sz_decimals)
        worst = trigger * (1 - STOP_LIMIT_SLIPPAGE) if position_side > 0 else trigger * (1 + STOP_LIMIT_SLIPPAGE)
        order_type = {"trigger": {"triggerPx": trigger, "isMarket": True, "tpsl": "sl"}}
        _check(
            self._ex().order(
                self.cfg.coin,
                position_side < 0,  # a stop on a long is a sell, and vice versa
                size,
                round_price(worst, self.sz_decimals),
                order_type,
                reduce_only=True,
            ),
            "stop order",
        )

    def cancel_all(self) -> None:
        for order in self.open_orders():
            _check(self._ex().cancel(self.cfg.coin, order["oid"]), "cancel")
