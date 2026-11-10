import pytest

from hl_bot.backtest import run_backtest
from hl_bot.bot import Bot, State, stop_price, target_size
from hl_bot.config import Config
from hl_bot.exchange import FLAT, OrderError, Position, _check, round_price, round_size_down
from hl_bot.strategy import Candle, closed_candles, compute_signal

HOUR = 3_600_000


def make_candles(closes):
    return [Candle(i * HOUR, (i + 1) * HOUR - 1, c, c * 1.002, c * 0.998, c) for i, c in enumerate(closes)]


UP = make_candles([100 + i for i in range(150)])
DOWN = make_candles([300 - i for i in range(150)])


class FakeClient:
    sz_decimals = 5

    def __init__(self, candles, position=FLAT, orders=None, realized=0.0):
        self._candles, self.pos, self.orders, self.realized = candles, position, orders or [], realized
        self.calls = []

    def candles(self, bars):
        return self._candles

    def position(self):
        return self.pos

    def open_orders(self):
        return self.orders

    def realized_pnl_since(self, start_ms):
        return self.realized

    def set_isolated_leverage(self):
        self.calls.append(("leverage",))

    def market_open(self, side, size):
        self.calls.append(("open", side, size))
        self.pos = Position(side * size, self._candles[-1].c, 0.0)
        return size

    def market_close(self):
        self.calls.append(("close",))
        self.pos = FLAT

    def place_stop(self, side, size, trigger):
        self.calls.append(("stop", side, size, trigger))

    def cancel_all(self):
        self.calls.append(("cancel_all",))


def make_bot(client, live=True, **state):
    return Bot(Config(), client, State(start_ms=1, **state), live)


def test_signal_follows_trend_and_ignores_forming_candle():
    assert compute_signal(UP).side == 1
    assert compute_signal(DOWN).side == -1
    assert compute_signal(UP[:20]).side == 0
    assert len(closed_candles(UP, UP[-1].T)) == len(UP) - 1


def test_stop_distance_is_clamped():
    assert 0.01 <= compute_signal(UP).stop_pct <= 0.04
    wild = [Candle(c.t, c.T, c.o, c.c * 1.5, c.c * 0.5, c.c) for c in UP]
    assert compute_signal(wild).stop_pct == 0.04


def test_rounding_and_sizing():
    assert round_price(103456.78, 5) == 103460.0
    assert round_price(3456.789, 4) == 3456.8
    assert round_size_down(0.000179, 5) == 0.00017
    cfg = Config()
    size = target_size(cfg, 100_000.0, 5)
    assert size * 100_000.0 <= cfg.budget_usd * cfg.leverage
    assert target_size(cfg, 100_000.0, 3) == 0.0  # would round below the $10 minimum
    assert stop_price(1, 100.0, 0.02) == 98.0
    assert stop_price(-1, 100.0, 0.02) == 102.0


def test_config_rejects_unsafe_settings():
    with pytest.raises(ValueError):
        Config(leverage=10).validate()
    with pytest.raises(ValueError):
        Config(budget_usd=5.0).validate()


def test_enters_with_stop_when_flat():
    client = FakeClient(UP)
    bot = make_bot(client)
    bot.tick()
    kinds = [c[0] for c in client.calls]
    assert kinds == ["leverage", "open", "stop"]
    opened, stop = client.calls[1], client.calls[2]
    assert opened[1] == 1 and opened[2] * UP[-1].c <= 20.0
    assert stop[3] < UP[-1].c
    assert bot.state.expected_side == 1


def test_dry_run_sends_nothing():
    client = FakeClient(UP)
    make_bot(client, live=False).tick()
    assert client.calls == []


def test_flips_when_signal_reverses():
    client = FakeClient(DOWN, position=Position(0.0001, 200.0, 0.0))
    make_bot(client, expected_side=1).tick()
    assert [c[0] for c in client.calls] == ["cancel_all", "close", "leverage", "open", "stop"]
    assert client.calls[3][1] == -1


def test_no_reentry_after_stop_out_until_signal_flips():
    client = FakeClient(UP)
    bot = make_bot(client, expected_side=1)
    bot.tick()
    assert client.calls == [] and bot.state.blocked_side == 1
    client._candles = DOWN
    bot.tick()
    assert client.calls[1][:2] == ("open", -1) and bot.state.blocked_side == 0


def test_replaces_missing_stop_but_keeps_existing_one():
    held = Position(0.0001, 240.0, 0.0)
    client = FakeClient(UP, position=held)
    make_bot(client, expected_side=1).tick()
    assert [c[0] for c in client.calls] == ["stop"]
    client = FakeClient(UP, position=held, orders=[{"isTrigger": True, "reduceOnly": True}])
    make_bot(client, expected_side=1).tick()
    assert client.calls == []


def test_loss_limit_flattens_and_halts():
    client = FakeClient(UP, position=Position(0.0001, 240.0, -1.0), realized=-2.5)
    bot = make_bot(client, expected_side=1)
    bot.tick()
    assert [c[0] for c in client.calls] == ["cancel_all", "close"] and bot.state.halted
    client.calls.clear()
    bot.tick()
    assert client.calls == []


def test_leaves_oversized_foreign_position_alone():
    client = FakeClient(DOWN, position=Position(1.0, 200.0, 0.0))
    make_bot(client).tick()
    assert client.calls == []


def test_check_raises_on_exchange_errors():
    ok = {"status": "ok", "response": {"data": {"statuses": [{"filled": {"totalSz": "0.1"}}]}}}
    assert _check(ok, "x")["filled"]["totalSz"] == "0.1"
    with pytest.raises(OrderError):
        _check({"status": "err", "response": "bad"}, "x")
    with pytest.raises(OrderError):
        _check({"status": "ok", "response": {"data": {"statuses": [{"error": "Insufficient margin"}]}}}, "x")


def test_backtest_profits_in_a_trend_and_charges_costs():
    res = run_backtest(make_candles([100 * 1.004**i for i in range(400)]), Config())
    assert res.trades == 1 and res.pnl_usd > 0
    assert res.pnl_usd < res.buy_hold_usd * 1.01
