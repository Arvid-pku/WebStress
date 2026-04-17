"""End-to-end tests for pp_coordinate_rx_transfer canonical_diff.

Task: "Your default pharmacy is closing. Transfer all of your active
prescriptions to another retail pharmacy in your pharmacy list, then update
that pharmacy as your new default."

Verifies:
  - Correct trajectory (all active rx pharmacy_id -> new retail; old default
    flipped to False; new retail flipped to True) passes with score 1.0.
  - Setting the mail-order pharmacy as the new default fails (mail-order is
    guarded by the filtered pharmacy invariant and the update predicate pins
    new_default_pharmacy_id).
  - Partial rx transfer (only some active rx re-pointed) fails via bijection
    under-saturation on update[0].
  - No pharmacy default change (transfer rx but skip is_default flips) fails
    via update[1] / update[2] non-bijection unsaturation.
  - No mutation (agent does nothing) fails — invariants alone must not
    saturate the positive pool (hazard Class 1 regression guard).
"""

from webagentbench.backend.state import SessionManager
from webagentbench.evaluator_diff import compute_diff, match_diff
from webagentbench.tasks._registry import get_task


def _setup_session(seed: int = 42):
    """Fresh session + initial snapshot + live state."""
    sm = SessionManager()
    sid, targets, _ = sm.create_session(
        env_id='patient_portal',
        task_id='pp_coordinate_rx_transfer',
        seed=seed,
    )
    initial = sm.get_initial_snapshot(sid)
    state = sm.get_state(sid)
    return sm, sid, dict(targets), initial, state


def _transfer(state, rx_id: str, pharmacy_id: str) -> None:
    """Simulate the backend transfer route: set rx.pharmacy_id = pharmacy_id."""
    for rx in state.prescriptions:
        if rx.id == rx_id:
            rx.pharmacy_id = pharmacy_id
            return
    raise ValueError(f"prescription {rx_id!r} not found")


def _set_is_default(state, pharmacy_id: str, value: bool) -> None:
    for p in state.pharmacies:
        if p.id == pharmacy_id:
            p.is_default = value
            return
    raise ValueError(f"pharmacy {pharmacy_id!r} not found in session state")


def _apply_correct(state, targets) -> None:
    """Canonical solution: move every active rx to new_default_pharmacy_id and
    flip is_default flags on the two pharmacies."""
    new_pharm = targets["new_default_pharmacy_id"]
    for rx_id in targets["active_rx_ids"]:
        _transfer(state, rx_id, new_pharm)
    _set_is_default(state, targets["default_pharmacy_id"], False)
    _set_is_default(state, new_pharm, True)


def test_correct_trajectory_passes():
    sm, sid, targets, initial, state = _setup_session()
    _apply_correct(state, targets)

    task = get_task('pp_coordinate_rx_transfer')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is True, f"failures: {report.failures}"
    assert report.score == 1.0, f"expected 1.0, got {report.score}"


def test_mail_order_set_as_default_fails():
    """Agent re-points every active rx AND flips is_default to the mail-order
    pharmacy instead of the retail pharmacy.

    Expected failures:
      - update[0] bijection underflows (changes require pharmacy_id ==
        new_default_pharmacy_id, mail-order id violates it).
      - update[2] non-bijection match fails (pins id == new_default_pharmacy_id
        with is_default=true, but agent flipped mail-order).
      - invariant[1] fires (filter excludes only {closing_default,
        new_default}, so mail-order mutation is flagged).
    """
    sm, sid, targets, initial, state = _setup_session()

    mail_order = targets["mail_order_pharmacy_id"]
    assert mail_order, "seed must emit mail_order_pharmacy_id for this test"

    for rx_id in targets["active_rx_ids"]:
        _transfer(state, rx_id, mail_order)
    _set_is_default(state, targets["default_pharmacy_id"], False)
    _set_is_default(state, mail_order, True)

    task = get_task('pp_coordinate_rx_transfer')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "mail-order-as-default must fail — update predicates and filtered "
        "pharmacy invariant should reject it."
    )
    assert report.score < 1.0, f"expected score<1.0, got {report.score}"


def test_partial_rx_transfer_fails():
    """Agent transfers only SOME active prescriptions to the new retail
    pharmacy, flips is_default correctly for both pharmacies.

    Expected: update[0] bijection unsaturated (not every target slot has a
    matching Update candidate), score < 1.0 and passed=False.
    """
    sm, sid, targets, initial, state = _setup_session()

    new_pharm = targets["new_default_pharmacy_id"]
    active_ids = list(targets["active_rx_ids"])
    assert len(active_ids) >= 2, "seed must produce >=2 active rx for this test"

    # Transfer only the first half, skip the rest
    for rx_id in active_ids[: len(active_ids) // 2]:
        _transfer(state, rx_id, new_pharm)
    _set_is_default(state, targets["default_pharmacy_id"], False)
    _set_is_default(state, new_pharm, True)

    task = get_task('pp_coordinate_rx_transfer')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "partial rx transfer must fail — update[0] bijection should be "
        "unsaturated since not every active rx got re-pointed."
    )
    assert report.score < 1.0, f"expected score<1.0, got {report.score}"


def test_no_pharmacy_default_change_fails():
    """Agent transfers every active rx correctly, but leaves is_default as-is
    (old default still flagged, new retail not flagged).

    Expected: update[1] (clear old) and update[2] (set new) both unmatched,
    score < 1.0 and passed=False.
    """
    sm, sid, targets, initial, state = _setup_session()

    new_pharm = targets["new_default_pharmacy_id"]
    for rx_id in targets["active_rx_ids"]:
        _transfer(state, rx_id, new_pharm)
    # Intentionally do NOT flip is_default on either pharmacy.

    task = get_task('pp_coordinate_rx_transfer')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "skipping the is_default flips must fail — update[1] and update[2] "
        "are non-bijection updates with no matching Update candidate."
    )
    assert report.score < 1.0, f"expected score<1.0, got {report.score}"


def test_no_mutation_fails():
    """Agent does nothing. Invariants trivially pass; update entries all
    unsaturated (hazard Class 1 regression guard)."""
    sm, sid, targets, initial, state = _setup_session()

    task = get_task('pp_coordinate_rx_transfer')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "no-op trajectory must fail — positive pool must not be saturated by "
        "invariants alone (hazard Class 1)."
    )
    assert report.score < 1.0, f"expected score<1.0, got {report.score}"
