"""Tests for Robinhood task YAML loading and seeding."""

from __future__ import annotations

import random
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from webagentbench.backend.models.base import utc_now
from webagentbench.backend.models.robinhood import (
    AccountSettings,
    Order,
    Position,
    PriceAlert,
    RobinhoodState,
    Stock,
)
from webagentbench.backend.seeders.robinhood import RobinhoodSeedRunner
from webagentbench.eval_core.safe_eval import safe_eval
from webagentbench.tasks._registry import load_all_tasks, get_task


EXPECTED_RH_EASY_TASKS = [
    "rh_buy_market_order",
    "rh_sell_shares",
    "rh_add_to_watchlist",
    "rh_cancel_pending_order",
    "rh_create_watchlist",
    "rh_set_price_alert",
    "rh_mark_notifications_read",
    "rh_check_buying_power",
    "rh_enable_extended_hours",
    "rh_deposit_funds",
]

EXPECTED_RH_MEDIUM_TASKS = [
    "rh_limit_order_with_check",
    "rh_deposit_then_buy",
    "rh_compare_dividend_yields",
    "rh_setup_recurring_investment",
    "rh_review_and_cancel_orders",
    "rh_transfer_and_withdraw",
    "rh_find_earnings_and_alert",
    "rh_sell_loser_buy_winner",
    "rh_options_buy_call",
    "rh_security_audit",
    "rh_live_buy_the_dip",
    "rh_live_take_profit",
    "rh_live_alert_and_buy",
    "rh_live_alert_and_sell",
    "rh_live_watch_and_buy",
]

EXPECTED_RH_HARD_TASKS = [
    "rh_portfolio_rebalance",
    "rh_covered_call_strategy",
    "rh_dividend_income_report",
    "rh_wash_sale_avoidance",
    "rh_cost_basis_reconciliation",
    "rh_options_chain_analysis",
    "rh_consolidate_recurring",
    "rh_notification_triage",
    "rh_sector_concentration",
    "rh_transfer_history_audit",
    "rh_live_stop_loss_execution",
    "rh_live_dual_alert_decision",
    "rh_live_watch_portfolio",
    "rh_live_watch_spread",
]

EXPECTED_RH_EXPERT_TASKS = [
    "rh_multi_leg_options",
    "rh_tax_optimization",
    "rh_portfolio_risk_assessment",
    "rh_earnings_play_setup",
    "rh_dividend_reinvestment_analysis",
    "rh_margin_call_resolution",
    "rh_watchlist_screening",
    "rh_recurring_optimization",
    "rh_cross_reference_1099",
    "rh_options_roll_strategy",
    "rh_live_bracket_order",
    "rh_live_alert_chain",
    "rh_live_intraday_reversal",
]

EXPECTED_RH_FRONTIER_TASKS = [
    "rh_full_portfolio_rebalance_with_tax",
    "rh_options_income_portfolio",
    "rh_year_end_tax_planning",
    "rh_suspicious_activity_investigation",
    "rh_complex_transfer_reconciliation",
    "rh_portfolio_transition",
    "rh_options_expiration_management",
    "rh_complete_account_audit",
    "rh_multi_strategy_execution",
    "rh_quarterly_performance_review",
    "rh_live_multi_stock_limits",
    "rh_live_cross_stock_alert",
    "rh_live_comparative_watch",
]

EXPECTED_RH_TASKS = (
    EXPECTED_RH_EASY_TASKS
    + EXPECTED_RH_MEDIUM_TASKS
    + EXPECTED_RH_HARD_TASKS
    + EXPECTED_RH_EXPERT_TASKS
    + EXPECTED_RH_FRONTIER_TASKS
)


def test_all_robinhood_tasks_load():
    """All rh_ tasks load with correct env_id and difficulty."""
    all_tasks = load_all_tasks()

    difficulty_map = {}
    for t in EXPECTED_RH_EASY_TASKS:
        difficulty_map[t] = "easy"
    for t in EXPECTED_RH_MEDIUM_TASKS:
        difficulty_map[t] = "medium"
    for t in EXPECTED_RH_HARD_TASKS:
        difficulty_map[t] = "hard"
    for t in EXPECTED_RH_EXPERT_TASKS:
        difficulty_map[t] = "expert"
    for t in EXPECTED_RH_FRONTIER_TASKS:
        difficulty_map[t] = "frontier"

    for task_id in EXPECTED_RH_TASKS:
        assert task_id in all_tasks, f"Task {task_id} not found in registry"
        task = all_tasks[task_id]
        assert task.env_id == "robinhood", f"{task_id} has wrong env_id: {task.env_id}"
        assert task.difficulty == difficulty_map[task_id], f"{task_id} has wrong difficulty: {task.difficulty}"
        assert task.task_id == task_id
        assert len(task.primary_primitives) > 0, f"{task_id} has no primary primitives"


@pytest.mark.parametrize("task_id", EXPECTED_RH_TASKS)
def test_all_robinhood_tasks_seed(task_id: str):
    """Each rh_ task can be seeded with seed=42 and produces valid state."""
    runner = RobinhoodSeedRunner()
    task = get_task(task_id)
    seed = 42
    rng = random.Random(seed)
    fake = MagicMock()
    fake.name.return_value = "Jordan Baker"
    fake.domain_word.return_value = "example"

    base, targets = runner.run(task, seed, fake, rng)

    # Validate the base state against the Pydantic model
    state = RobinhoodState.model_validate(base)
    assert state.env_id == "robinhood"
    assert state.task_id == task_id

    # Verify eval config exists
    assert task.eval is not None, f"{task_id} has no eval config"
    assert len(task.eval.checks) > 0, f"{task_id} has no eval checks"


def test_all_live_task_trajectories_valid():
    """Every task with price_trajectory must pass economic validation."""
    from webagentbench.backend.price_validation import validate_trajectory
    from webagentbench.backend.price_engine import TrajectoryConfig, StockTrajectory

    all_tasks = load_all_tasks()
    rh_tasks = {k: v for k, v in all_tasks.items() if k.startswith("rh_")}
    live_count = 0

    for task_id, task in rh_tasks.items():
        if task.seed is None:
            continue
        pt = getattr(task.seed, "price_trajectory", None)
        if pt is None:
            continue
        live_count += 1
        config = TrajectoryConfig(
            tick_interval_seconds=pt.tick_interval_seconds,
            stocks={
                sym: StockTrajectory(keyframes=ts.keyframes, noise_pct=ts.noise_pct)
                for sym, ts in pt.stocks.items()
            },
        )
        errors = validate_trajectory(config)
        assert not errors, f"{task_id} trajectory validation failed: {errors}"

    assert live_count == 15, f"Expected 15 live tasks, found {live_count}"


# ---------------------------------------------------------------------------
# Constraint-expression tests for the "pending order passes evaluation" fix.
#
# These tests build minimal RobinhoodState fixtures and evaluate each task's
# canonical_diff.constraints against them via safe_eval, asserting that
# pending/under-executed orders fail and that fully-filled, discipline-respecting
# orders pass.
# ---------------------------------------------------------------------------


def _make_stock(symbol: str, price: float, **overrides) -> Stock:
    defaults = dict(
        symbol=symbol,
        name=f"{symbol} Inc.",
        asset_type="stock",
        price=Decimal(str(price)),
        previous_close=Decimal(str(price)),
        day_change=Decimal("0"),
        day_change_pct=Decimal("0"),
        bid=Decimal(str(round(price - 0.01, 2))),
        ask=Decimal(str(round(price + 0.01, 2))),
        bid_size=100,
        ask_size=100,
        volume=1_000_000,
        avg_volume=1_000_000,
        fifty_two_week_high=Decimal(str(round(price * 1.5, 2))),
        fifty_two_week_low=Decimal(str(round(price * 0.5, 2))),
        sector="Technology",
        industry="Software",
        about="A test stock.",
    )
    defaults.update(overrides)
    return Stock(**defaults)


def _make_state(stocks: list[Stock] | None = None, **kwargs) -> RobinhoodState:
    defaults = dict(
        env_id="robinhood",
        task_id="test",
        owner_name="Test",
        owner_email="test@test.com",
        cash_balance=Decimal("100000"),
        buying_power=Decimal("100000"),
        portfolio_value=Decimal("0"),
        settings=AccountSettings(id="s1"),
        stocks=stocks or [],
    )
    defaults.update(kwargs)
    return RobinhoodState(**defaults)


def _order(
    *,
    id: str = "ord_1",
    symbol: str,
    side: str,
    order_type: str = "market",
    quantity: Decimal,
    filled_quantity: Decimal | None = None,
    status: str = "filled",
    filled_price: Decimal | None = None,
    limit_price: Decimal | None = None,
    stop_price: Decimal | None = None,
    time_in_force: str = "gfd",
) -> Order:
    if filled_quantity is None:
        filled_quantity = quantity if status in ("filled",) else Decimal("0")
    return Order(
        id=id,
        symbol=symbol,
        side=side,  # type: ignore[arg-type]
        order_type=order_type,  # type: ignore[arg-type]
        quantity=quantity,
        filled_quantity=filled_quantity,
        filled_price=filled_price,
        limit_price=limit_price,
        stop_price=stop_price,
        time_in_force=time_in_force,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        created_at=utc_now(),
    )


def _eval_constraints(task_id: str, state: RobinhoodState, *, targets: dict | None = None) -> dict[str, bool]:
    """Evaluate every constraint on `task_id` against `state`. Returns desc -> bool."""
    task = get_task(task_id)
    assert task.canonical_diff is not None
    initial = state  # for these tests, initial == final stock prices
    result: dict[str, bool] = {}
    for c in task.canonical_diff.constraints:
        try:
            ok = bool(safe_eval(
                c.expr,
                {"state": state, "initial": initial, "target": targets or {}, "session_start": None},
            ))
        except Exception:
            ok = False
        result[c.desc] = ok
    return result


# ---------------------------------------------------------------------------
# rh_live_buy_the_dip — limit-buy task with full discipline checks
# ---------------------------------------------------------------------------

class TestBuyTheDipConstraints:
    """rh_live_buy_the_dip: limit AAPL buy at <= 5% below $190 ($182.4) for 10 shares."""

    AAPL_INITIAL = 190.0
    LIMIT = Decimal("180.00")  # within 5% threshold (190 * 0.96 = 182.4)

    def _state(self, orders: list[Order]) -> RobinhoodState:
        return _make_state(stocks=[_make_stock("AAPL", self.AAPL_INITIAL)], orders=orders)

    def test_pending_limit_buy_fails(self):
        """Under-execution: limit buy is still pending → critical fill check fails."""
        state = self._state([_order(
            symbol="AAPL", side="buy", order_type="limit", quantity=Decimal("10"),
            limit_price=self.LIMIT, time_in_force="gtc", status="pending",
        )])
        results = _eval_constraints("rh_live_buy_the_dip", state)
        assert results["AAPL GTC limit buy order at approximately 5% below current price filled for 10 shares"] is False

    def test_filled_limit_buy_passes(self):
        """Patient agent: filled at the limit price → all constraints pass."""
        state = self._state([_order(
            symbol="AAPL", side="buy", order_type="limit", quantity=Decimal("10"),
            limit_price=self.LIMIT, filled_price=self.LIMIT, time_in_force="gtc", status="filled",
        )])
        results = _eval_constraints("rh_live_buy_the_dip", state)
        assert all(results.values()), f"Expected all-pass, got: {results}"

    def test_partial_fill_fails_under_execution(self):
        """Partial fill → filled_quantity != quantity → critical fill check fails."""
        state = self._state([_order(
            symbol="AAPL", side="buy", order_type="limit", quantity=Decimal("10"),
            filled_quantity=Decimal("4"),
            limit_price=self.LIMIT, filled_price=self.LIMIT, time_in_force="gtc",
            status="partially_filled",
        )])
        results = _eval_constraints("rh_live_buy_the_dip", state)
        # filled_orders excludes partially_filled, so the critical "filled" check fails.
        assert results["AAPL GTC limit buy order at approximately 5% below current price filled for 10 shares"] is False

    def test_market_substitution_fails_over_execution(self):
        """Agent placed a MARKET buy (filled instantly) instead of waiting for the limit → fail."""
        state = self._state([_order(
            id="ord_market", symbol="AAPL", side="buy", order_type="market",
            quantity=Decimal("10"), filled_price=Decimal(str(self.AAPL_INITIAL)),
            status="filled",
        )])
        results = _eval_constraints("rh_live_buy_the_dip", state)
        assert results["Agent did not substitute a market/stop AAPL buy to force a fill"] is False
        # And the limit-buy critical also fails (no limit order at all).
        assert results["AAPL GTC limit buy order at approximately 5% below current price filled for 10 shares"] is False

    def test_duplicate_orders_fail_count(self):
        """Two non-decoy AAPL buy orders → count check fails."""
        state = self._state([
            _order(id="ord_1", symbol="AAPL", side="buy", order_type="limit",
                   quantity=Decimal("10"), limit_price=self.LIMIT, filled_price=self.LIMIT,
                   time_in_force="gtc", status="filled"),
            _order(id="ord_2", symbol="AAPL", side="buy", order_type="limit",
                   quantity=Decimal("10"), limit_price=self.LIMIT, filled_price=self.LIMIT,
                   time_in_force="gtc", status="filled"),
        ])
        results = _eval_constraints("rh_live_buy_the_dip", state)
        assert results["Exactly one non-decoy AAPL buy order placed (no duplicates)"] is False

    def test_decoy_orders_ignored_by_count(self):
        """Decoy buy orders should NOT count toward the discipline check."""
        state = self._state([
            _order(id="ord_decoy_1", symbol="AAPL", side="buy", order_type="market",
                   quantity=Decimal("3"), filled_price=Decimal("190"), status="filled"),
            _order(id="ord_real", symbol="AAPL", side="buy", order_type="limit",
                   quantity=Decimal("10"), limit_price=self.LIMIT, filled_price=self.LIMIT,
                   time_in_force="gtc", status="filled"),
        ])
        results = _eval_constraints("rh_live_buy_the_dip", state)
        assert results["Exactly one non-decoy AAPL buy order placed (no duplicates)"] is True
        assert results["Agent did not substitute a market/stop AAPL buy to force a fill"] is True

    def test_leftover_pending_fails(self):
        """A second AAPL buy left pending after the requested fill → fail."""
        state = self._state([
            _order(id="ord_1", symbol="AAPL", side="buy", order_type="limit",
                   quantity=Decimal("10"), limit_price=self.LIMIT, filled_price=self.LIMIT,
                   time_in_force="gtc", status="filled"),
            _order(id="ord_pending", symbol="AAPL", side="buy", order_type="limit",
                   quantity=Decimal("5"), limit_price=Decimal("170"),
                   time_in_force="gtc", status="pending"),
        ])
        results = _eval_constraints("rh_live_buy_the_dip", state)
        assert results["No leftover pending AAPL buy after the requested fill"] is False

    def test_limit_bound_violated_fails(self):
        """Filled price above the limit_price → bound check fails (regression pin against simulator)."""
        state = self._state([_order(
            id="ord_1", symbol="AAPL", side="buy", order_type="limit",
            quantity=Decimal("10"), limit_price=self.LIMIT,
            filled_price=Decimal("200.00"),  # impossibly above the bound
            time_in_force="gtc", status="filled",
        )])
        results = _eval_constraints("rh_live_buy_the_dip", state)
        assert results["Limit fill respected the limit-buy bound (filled_price <= limit_price)"] is False


# ---------------------------------------------------------------------------
# rh_live_bracket_order — limit buy must fill, stop+TP intentionally pending
# ---------------------------------------------------------------------------

class TestBracketOrderConstraints:
    def _state(self, orders: list[Order]) -> RobinhoodState:
        return _make_state(stocks=[_make_stock("MSFT", 412.0)], orders=orders)

    def _full_setup(self, *, buy_status: str = "filled") -> list[Order]:
        return [
            _order(id="ord_buy", symbol="MSFT", side="buy", order_type="limit",
                   quantity=Decimal("1"), limit_price=Decimal("400"),
                   filled_price=Decimal("400") if buy_status == "filled" else None,
                   filled_quantity=Decimal("1") if buy_status == "filled" else Decimal("0"),
                   time_in_force="gtc", status=buy_status),
            _order(id="ord_stop", symbol="MSFT", side="sell", order_type="stop",
                   quantity=Decimal("1"), stop_price=Decimal("380"),
                   time_in_force="gtc", status="pending"),
            _order(id="ord_tp", symbol="MSFT", side="sell", order_type="limit",
                   quantity=Decimal("1"), limit_price=Decimal("430"),
                   time_in_force="gtc", status="pending"),
        ]

    def test_pending_buy_fails(self):
        results = _eval_constraints("rh_live_bracket_order", self._state(self._full_setup(buy_status="pending")))
        assert results["MSFT limit buy order placed at or below $400 and filled"] is False

    def test_filled_buy_with_pending_brackets_passes(self):
        """Buy filled, stop+TP pending — exactly the intended bracket setup."""
        results = _eval_constraints("rh_live_bracket_order", self._state(self._full_setup(buy_status="filled")))
        assert all(results.values()), f"Expected all-pass, got: {results}"

    def test_market_substitution_fails(self):
        orders = self._full_setup(buy_status="filled")
        # Replace the limit buy with a market buy
        orders[0] = _order(id="ord_buy", symbol="MSFT", side="buy", order_type="market",
                           quantity=Decimal("1"), filled_price=Decimal("412"), status="filled")
        results = _eval_constraints("rh_live_bracket_order", self._state(orders))
        assert results["Agent did not substitute a market/stop MSFT buy to force a fill"] is False

    def test_duplicate_buy_fails_count(self):
        orders = self._full_setup(buy_status="filled")
        orders.append(_order(id="ord_buy_dup", symbol="MSFT", side="buy", order_type="limit",
                             quantity=Decimal("1"), limit_price=Decimal("395"),
                             filled_price=Decimal("395"), time_in_force="gtc", status="filled"))
        results = _eval_constraints("rh_live_bracket_order", self._state(orders))
        assert results["Exactly one non-decoy MSFT buy order placed (no duplicates)"] is False


# ---------------------------------------------------------------------------
# Market-order task: pending → fail, filled → pass.
# Spot-check on rh_live_alert_and_buy.
# ---------------------------------------------------------------------------

class TestAlertAndBuyConstraints:
    def _state(self, *, orders: list[Order], alerts: list[PriceAlert]) -> RobinhoodState:
        return _make_state(
            stocks=[_make_stock("AAPL", 190.0)],
            orders=orders,
            price_alerts=alerts,
        )

    def _alert(self) -> PriceAlert:
        return PriceAlert(
            id="alert_1",
            symbol="AAPL",
            condition="below",
            target_price=Decimal("182"),
            status="active",
        )

    def test_pending_market_buy_fails(self):
        """Agent placed a market order but it's recorded as pending — should fail."""
        state = self._state(
            orders=[_order(symbol="AAPL", side="buy", order_type="market",
                           quantity=Decimal("5"), status="pending",
                           filled_quantity=Decimal("0"))],
            alerts=[self._alert()],
        )
        results = _eval_constraints("rh_live_alert_and_buy", state)
        assert results["Market buy of 5 AAPL shares filled"] is False

    def test_filled_market_buy_passes(self):
        state = self._state(
            orders=[_order(symbol="AAPL", side="buy", order_type="market",
                           quantity=Decimal("5"), filled_price=Decimal("181"),
                           status="filled")],
            alerts=[self._alert()],
        )
        results = _eval_constraints("rh_live_alert_and_buy", state)
        assert all(results.values()), f"Expected all-pass, got: {results}"


# ---------------------------------------------------------------------------
# rh_live_watch_and_buy — instruction explicitly forbids limit orders
# ---------------------------------------------------------------------------

class TestWatchAndBuyForbidsLimit:
    def _state(self, orders: list[Order]) -> RobinhoodState:
        return _make_state(stocks=[_make_stock("AAPL", 190.0)], orders=orders)

    def test_limit_substitution_fails(self):
        """Agent used a limit order even though instruction said 'Do not use limit orders' → fail."""
        state = self._state([_order(
            symbol="AAPL", side="buy", order_type="limit", quantity=Decimal("10"),
            limit_price=Decimal("180"), filled_price=Decimal("180"), status="filled",
        )])
        results = _eval_constraints("rh_live_watch_and_buy", state)
        assert results["Agent did not use a limit/stop AAPL buy (instruction forbids limit orders)"] is False

    def test_market_buy_passes(self):
        state = self._state([_order(
            symbol="AAPL", side="buy", order_type="market", quantity=Decimal("10"),
            filled_price=Decimal("181"), status="filled",
        )])
        results = _eval_constraints("rh_live_watch_and_buy", state)
        assert all(results.values()), f"Expected all-pass, got: {results}"
