"""Regression audit for task-standard coverage on previously weak tasks.

These checks are intentionally high-signal and task-specific. They lock in
the outcome-grading and wrong-trajectory requirements from
``share_docs/TASK_GENERATION_STANDARD.md`` for tasks that previously allowed
partial or collateral completions to slip through.
"""

from __future__ import annotations

from typing import Any

from webagentbench.tasks._registry import load_all_tasks


def _task(task_id: str) -> Any:
    return load_all_tasks()[task_id]


def _exprs(task_id: str, phase: str | None = None) -> list[str]:
    task = _task(task_id)
    ev = getattr(task, "eval", None)
    if ev is None:
        return []

    if phase == "checks":
        items = getattr(ev, "checks", []) or []
    elif phase == "negative_checks":
        items = getattr(ev, "negative_checks", []) or []
    else:
        items = (getattr(ev, "checks", []) or []) + (getattr(ev, "negative_checks", []) or [])
    return [item.expr for item in items]


def _descs(task_id: str, phase: str | None = None) -> list[str]:
    task = _task(task_id)
    ev = getattr(task, "eval", None)
    if ev is None:
        return []

    if phase == "checks":
        items = getattr(ev, "checks", []) or []
    elif phase == "negative_checks":
        items = getattr(ev, "negative_checks", []) or []
    else:
        items = (getattr(ev, "checks", []) or []) + (getattr(ev, "negative_checks", []) or [])
    return [item.desc for item in items]


def _instruction(task_id: str) -> str:
    task = _task(task_id)
    return (
        getattr(task, "instruction_template", None)
        or getattr(task, "instruction", None)
        or ""
    ).lower()


def test_every_task_has_wrong_trajectory_coverage() -> None:
    """Every legacy-eval task should have at least one explicit negative guard.

    Skips tasks migrated to canonical_diff — negative-trajectory coverage there
    is enforced by the adversarial battery and per-task canonical_diff tests.
    """
    for task_id, task in load_all_tasks().items():
        if getattr(task, "eval", None) is None:
            continue
        assert _exprs(task_id, "negative_checks"), f"{task_id} is missing negative coverage"


def test_exclusive_instructions_have_cardinality_or_exclusion_guards() -> None:
    """Tasks with exclusivity language should grade exclusivity explicitly."""
    keywords = (" exactly ", " only ", " none ", " do not ", " leave ", " no other ")
    guard_tokens = (
        "len(",
        "sum(",
        "count(",
        "not any",
        "not in",
        "!=",
        "id ==",
        "set(",
        "forwarded_from_id",
        "linked_entity_id",
        "decoy",
        "unchanged",
        "not accidentally",
        "not modified",
        "no extra",
        "wrong",
        "collateral",
    )
    for task_id, task in load_all_tasks().items():
        if getattr(task, "eval", None) is None:
            continue
        instruction = f" {_instruction(task_id)} "
        if not any(keyword in instruction for keyword in keywords):
            continue

        exprs = _exprs(task_id)
        neg_exprs = _exprs(task_id, "negative_checks")
        blob = "\n".join(exprs + _descs(task_id)).lower()
        assert neg_exprs, f"{task_id} uses exclusivity language but has no negative coverage"
        assert len(exprs) >= 3 or any(token in blob for token in guard_tokens), (
            f"{task_id} uses exclusivity language but lacks explicit exclusion/cardinality grounding "
            "or enough independent checks"
        )


def test_reddit_frontier_workflows_have_specific_collateral_guards() -> None:
    """Large Reddit workflows must guard more than generic message/post counts."""
    task_ids = [
        "reddit_platform_migration",
        "reddit_full_platform_overhaul",
        "reddit_community_builder",
        "reddit_messaging_workflow",
        "reddit_search_and_engage",
        "reddit_thread_participation",
    ]
    for task_id in task_ids:
        neg_exprs = _exprs(task_id, "negative_checks")
        neg_blob = "\n".join(neg_exprs + _descs(task_id, "negative_checks")).lower()
        assert len(neg_exprs) >= 2, f"{task_id} should keep multiple negative guards"
        assert any(
            token in neg_blob
            for token in (
                "saved_post_ids",
                "is_subscribed",
                "vote_direction",
                "sent_messages",
                "state.messages",
                "to_user",
                "notifications",
                "comments",
            )
        ), f"{task_id} still lacks object-specific negative coverage"


def test_amazon_order_integrity_tasks_require_exact_order_contents() -> None:
    """Purchase workflows must reject collateral items riding along in the order."""
    task_ids = [
        "amazon_compare_and_buy_cheapest",
        "amazon_wishlist_to_cart",
        "amazon_multi_order_workflow",
        "amazon_account_overhaul_and_shop",
    ]
    for task_id in task_ids:
        blob = "\n".join(_exprs(task_id)).lower()
        assert (
            "order.items" in blob or "o.items" in blob
        ), f"{task_id} should inspect order item membership directly"
        assert (
            "len(order.items)" in blob
            or "len(o.items)" in blob
            or "set(item.product_id" in blob
            or "sorted(item.product_id" in blob
        ), f"{task_id} should enforce exact order contents, not supersets"


def test_lms_reporting_tasks_bind_recipient_and_required_facts() -> None:
    """LMS reporting tasks must prove the message went to the right recipient."""
    recipient_bound = {
        "lms_check_assignment_grade": ("target_assignment_id", "announcement"),
        "lms_check_course_grade": ("target_course_id", "announcement"),
        "lms_calculate_weighted_grade": ("target_course_id", "announcement"),
        "lms_compare_course_grades": ("lower_grade_course_id", "dropped"),
        "lms_find_next_deadline": ("next_deadline_assignment_id", "early_draft"),
        "lms_grade_with_curve": ("exam_assignment_id", "curve"),
    }
    for task_id, required_tokens in recipient_bound.items():
        blob = "\n".join(_exprs(task_id)).lower()
        for token in required_tokens:
            assert token.lower() in blob, f"{task_id} is missing required eval grounding token: {token}"


def test_booking_rebooking_tasks_bind_exact_reservation_identity() -> None:
    """Booking workflows must lock onto the exact room/cardinality outcome.

    Obsolete post canonical_diff migration: both tasks now use canonical_diff
    bindings (room_type_name / payment_method_id / reservation cardinality)
    enforced by their per-task canonical_diff tests + the adversarial battery.
    Retained as a skip so git blame still surfaces the original intent.
    """
    for task_id in ("booking_cancel_rebook_cheaper", "booking_find_genius_deal"):
        assert _task(task_id).eval is None, (
            f"{task_id} still has legacy eval — this audit should be re-enabled"
        )


def test_robinhood_alert_and_limit_tasks_bind_trigger_math_and_order_timing() -> None:
    """Robinhood evaluators must prove the requested price math and sequence."""
    checks = {
            "rh_limit_order_with_check": ("limit_price", "decimal('0.95')", "exactly one amzn"),
            "rh_find_earnings_and_alert": ("portfolio_symbols_with_earnings_within(7)", "decimal('0.95')"),
            "rh_live_alert_and_buy": ("triggered_at", "created_at > a.triggered_at"),
            "rh_live_alert_and_sell": ("triggered_at",),
            "rh_live_alert_chain": ("sector_pct('technology')", "nvda"),
            "rh_live_cross_stock_alert": ("triggered_at", "max(a.triggered_at"),
            "rh_live_watch_portfolio": ("portfolio_value >= decimal('15000')", "get_position('{target.best_symbol}') is none"),
            "rh_live_buy_the_dip": ("filled_tick", "filled_price is not none and o.filled_price <= decimal('180')"),
            "rh_live_watch_and_buy": ("filled_tick", "price_at_tick('aapl', o.filled_tick) < decimal('182')"),
        "rh_live_watch_spread": ("filled_tick", "price_at_tick('tsla', o.filled_tick) >"),
        "rh_live_intraday_reversal": ("filled_tick", "price_at_tick('nvda', o.filled_tick - 1) < decimal('845')"),
        }
    for task_id, required_tokens in checks.items():
        blob = "\n".join(_exprs(task_id) + _descs(task_id)).lower()
        for token in required_tokens:
            assert token.lower() in blob, f"{task_id} is missing trigger/timing token: {token}"


def test_patient_portal_claim_and_screening_tasks_bind_exact_target_sets() -> None:
    """Patient portal tasks must reject partial or wrong-claim completions."""
    checks = {
        "pp_pay_claim": ("state._initial_snapshot['claims']", "approved_claim_ids"),
        "pp_dispute_claim": ("state._initial_snapshot['claims']", "denied_claim_ids"),
        "pp_reconcile_billing": ("appointment_id", "completed_ids", "category == 'billing'"),
        "pp_preventive_screening_review": ("screening_name.lower() in m.body.lower()", "next_due"),
    }
    for task_id, required_tokens in checks.items():
        blob = "\n".join(_exprs(task_id)).lower()
        for token in required_tokens:
            assert token.lower() in blob, f"{task_id} is missing target-set coverage token: {token}"
