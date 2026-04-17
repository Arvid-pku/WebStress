"""End-to-end tests for pp_update_default_pharmacy canonical_diff.

Task: "Change your default pharmacy to {target.pharmacy_name}."

Verifies:
  - Correct trajectory (target pharmacy is_default=True, original=False) passes 1.0.
  - Only-new-set-old-unchanged (both default) fails.
  - Wrong-pharmacy-set-default (a third pharmacy flipped to default) fails.
  - No-mutation trajectory fails (update entries unsaturated).
"""

from webagentbench.backend.state import SessionManager
from webagentbench.evaluator_diff import compute_diff, match_diff
from webagentbench.tasks._registry import get_task


def _setup_session(seed: int = 42):
    sm = SessionManager()
    sid, targets, _ = sm.create_session(
        env_id='patient_portal',
        task_id='pp_update_default_pharmacy',
        seed=seed,
    )
    initial = sm.get_initial_snapshot(sid)
    state = sm.get_state(sid)
    return sm, sid, dict(targets), initial, state


def _set_is_default(state, pharmacy_id: str, value: bool) -> None:
    for p in state.pharmacies:
        if p.id == pharmacy_id:
            p.is_default = value
            return
    raise ValueError(f"pharmacy {pharmacy_id!r} not found in session state")


def test_correct_trajectory_passes():
    sm, sid, targets, initial, state = _setup_session()
    _set_is_default(state, targets["target_pharmacy_id"], True)
    _set_is_default(state, targets["original_default_id"], False)

    task = get_task('pp_update_default_pharmacy')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is True, f"failures: {report.failures}"
    assert report.score == 1.0, f"expected 1.0, got {report.score}"


def test_only_new_set_old_unchanged_fails():
    """Agent sets target pharmacy default=True but forgets to unset the old one.

    Both pharmacies now have is_default=True. The second update entry (clear
    original default) is unsaturated because the original still has
    is_default=True, violating the {eq: false} predicate on the changed value.
    """
    sm, sid, targets, initial, state = _setup_session()
    _set_is_default(state, targets["target_pharmacy_id"], True)
    # NOTE: intentionally do NOT flip the original default back to False

    task = get_task('pp_update_default_pharmacy')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "leaving the original default flagged True should fail the second "
        "update entry (predicate is_default=={eq: false})"
    )
    assert report.score < 1.0, f"expected partial credit < 1.0, got {report.score}"


def test_wrong_pharmacy_set_default_fails():
    """Agent flips a THIRD pharmacy to default (neither target nor original).

    Expected failures: the filtered invariant on non-target pharmacies fires
    (a third pharmacy's is_default changed), and the first update entry is
    unsaturated (target_pharmacy_id still not default).
    """
    sm, sid, targets, initial, state = _setup_session()
    # Find a pharmacy that isn't the target or the original default
    third = next(
        (p for p in state.pharmacies
         if p.id != targets["target_pharmacy_id"]
         and p.id != targets["original_default_id"]),
        None,
    )
    assert third is not None, "seed must produce ≥3 pharmacies for this test"
    _set_is_default(state, targets["original_default_id"], False)
    _set_is_default(state, third.id, True)

    task = get_task('pp_update_default_pharmacy')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "flipping a third pharmacy's is_default should violate the filtered "
        "invariant on non-target pharmacies"
    )


def test_no_mutation_fails():
    """Agent does nothing — both update entries unsaturated."""
    sm, sid, targets, initial, state = _setup_session()
    # No mutations

    task = get_task('pp_update_default_pharmacy')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "no-op trajectory must fail — positive pool must not be saturated by "
        "invariants alone (hazard Class 1)"
    )
