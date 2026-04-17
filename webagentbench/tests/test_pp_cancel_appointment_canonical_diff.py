"""End-to-end tests for pp_cancel_appointment canonical_diff.

Task: "Cancel your upcoming appointment with <provider> on <date>."

Verifies:
  - Correct trajectory (target appointment's status mutates to 'cancelled')
    passes with score 1.0.
  - Wrong-target trajectory (cancels a different appointment) fails.
  - Extra-mutation trajectory (cancels target + modifies another) fails.
"""

from webagentbench.backend.state import SessionManager
from webagentbench.evaluator_diff import compute_diff, match_diff
from webagentbench.tasks._registry import get_task


def _setup_session(seed: int = 42):
    sm = SessionManager()
    sid, targets, _ = sm.create_session(
        env_id="patient_portal",
        task_id="pp_cancel_appointment",
        seed=seed,
    )
    initial = sm.get_initial_snapshot(sid)
    state = sm.get_state(sid)
    return sm, sid, dict(targets), initial, state


def _cancel_apt(state, apt_id: str) -> None:
    for apt in state.appointments:
        if apt.id == apt_id:
            apt.status = "cancelled"
            return
    raise ValueError(f"appointment {apt_id!r} not found in session state")


def test_correct_trajectory_passes():
    sm, sid, targets, initial, state = _setup_session()
    _cancel_apt(state, targets["target_apt_id"])

    task = get_task("pp_cancel_appointment")
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is True, f"failures: {report.failures}"
    assert report.score == 1.0, f"expected 1.0, got {report.score}"


def test_wrong_appointment_cancelled_fails():
    """Agent cancels an appointment, but not the one the task specified."""
    sm, sid, targets, initial, state = _setup_session()
    other = next(
        (a for a in state.appointments
         if a.id != targets["target_apt_id"] and a.status == "scheduled"),
        None,
    )
    assert other is not None, "seed must produce >=2 upcoming appointments for this test"
    _cancel_apt(state, other.id)

    task = get_task("pp_cancel_appointment")
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "cancelling the wrong appointment should fail — the where selector "
        "on the target apt id must reject a different id"
    )


def test_extra_mutation_fails():
    """Agent correctly cancels the target AND also cancels another appointment."""
    sm, sid, targets, initial, state = _setup_session()
    _cancel_apt(state, targets["target_apt_id"])
    other = next(
        (a for a in state.appointments
         if a.id != targets["target_apt_id"] and a.status == "scheduled"),
        None,
    )
    if other is not None:
        _cancel_apt(state, other.id)

    task = get_task("pp_cancel_appointment")
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "cancelling an extra appointment should violate the filtered invariant "
        "on non-target appointments"
    )
