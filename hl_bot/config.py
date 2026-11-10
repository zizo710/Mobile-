"""Settings, read from the environment (optionally via a local .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

MIN_ORDER_USD = 10.0  # Hyperliquid rejects orders below $10 notional

INTERVAL_MS = {
    "15m": 15 * 60_000,
    "1h": 60 * 60_000,
    "4h": 4 * 60 * 60_000,
    "1d": 24 * 60 * 60_000,
}


def load_dotenv(path: Path = Path(".env")) -> None:
    """Minimal .env loader; real environment variables win."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def _flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Config:
    network: str = "testnet"  # "testnet" or "mainnet"
    account_address: str = ""  # main wallet address (public)
    api_wallet_key: str = ""  # API/agent wallet private key (can trade, cannot withdraw)

    coin: str = "BTC"
    interval: str = "4h"
    budget_usd: float = 10.0  # margin the bot is allowed to commit
    leverage: int = 2
    margin_use: float = 0.9  # fraction of budget used as margin, leaves room for fees
    max_loss_usd: float = 3.0  # kill switch: flatten and halt once the bot is down this much
    allow_short: bool = True

    fast: int = 20
    slow: int = 50
    atr_period: int = 14
    atr_mult: float = 2.0
    min_stop_pct: float = 0.01
    max_stop_pct: float = 0.04

    poll_seconds: int = 60
    state_path: str = "hl_bot_state.json"

    @property
    def notional_usd(self) -> float:
        return self.budget_usd * self.margin_use * self.leverage

    def validate(self) -> None:
        if self.network not in {"testnet", "mainnet"}:
            raise ValueError("HL_NETWORK must be 'testnet' or 'mainnet'")
        if self.interval not in INTERVAL_MS:
            raise ValueError(f"HL_INTERVAL must be one of {sorted(INTERVAL_MS)}")
        if self.leverage < 1 or self.leverage > 5:
            raise ValueError("HL_LEVERAGE must be between 1 and 5")
        if self.fast >= self.slow:
            raise ValueError("fast EMA period must be shorter than slow")
        if self.notional_usd < MIN_ORDER_USD * 1.1:
            raise ValueError(
                f"Position size ${self.notional_usd:.2f} is too close to Hyperliquid's "
                f"${MIN_ORDER_USD:.0f} minimum order; raise HL_BUDGET_USD or HL_LEVERAGE"
            )

    @classmethod
    def from_env(cls) -> "Config":
        env = os.environ
        d = cls()
        cfg = cls(
            network=env.get("HL_NETWORK", d.network).lower(),
            account_address=env.get("HL_ACCOUNT_ADDRESS", ""),
            api_wallet_key=env.get("HL_API_WALLET_KEY", ""),
            coin=env.get("HL_COIN", d.coin).upper(),
            interval=env.get("HL_INTERVAL", d.interval),
            budget_usd=float(env.get("HL_BUDGET_USD", d.budget_usd)),
            leverage=int(env.get("HL_LEVERAGE", d.leverage)),
            max_loss_usd=float(env.get("HL_MAX_LOSS_USD", d.max_loss_usd)),
            allow_short=_flag("HL_ALLOW_SHORT", d.allow_short),
            poll_seconds=int(env.get("HL_POLL_SECONDS", d.poll_seconds)),
            state_path=env.get("HL_STATE_PATH", d.state_path),
        )
        cfg.validate()
        return cfg
