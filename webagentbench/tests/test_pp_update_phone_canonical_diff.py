"""End-to-end tests for pp_update_phone canonical_diff.

The task updates ``state.patient.phone`` — but ``patient`` is a SINGLETON
on ``PatientPortalState`` (not a list). ``compute_diff`` only iterates
list-valued collections, so patient-field mutations don't produce any
``Update`` entry in ``agent_diff``. The positive signal is therefore
a ``critical``-severity ``constraint`` on ``state.patient.phone``;
invariants + other constraints provide the negative signal.

With ``total_weight == 0`` (no create/update/delete entries), the score
is ``max(0.0, 1.0 - sum_penalties)``. Correct → 1.0; do-nothing → 0.7
(critical penalty 0.3 from the phone constraint) with ``passed=False``.
"""

from webagentbench.backend.state import SessionManager
from webagentbench.evaluator_diff import compute_diff, match_diff
from webagentbench.tasks._registry import get_task


def _setup_session(seed: int = 42):
    """Fresh session + initial snapshot + live state."""
    sm = SessionManager()
    sid, targets, _ = sm.create_session(
        env_id='patient_portal',
        task_id='pp_update_phone',
        seed=seed,
    )
    initial = sm.get_initial_snapshot(sid)
    state = sm.get_state(sid)
    return sm, sid, dict(targets), initial, state


def test_correct_trajectory_passes():
    """Agent updates patient.phone to target['new_phone'] and touches nothing else.
    Expected: score == 1.0, passed == True, no failures."""
    sm, sid, targets, initial, state = _setup_session()

    # Apply the agent-equivalent mutation directly on the singleton patient.
    state.patient.phone = targets["new_phone"]

    task = get_task('pp_update_phone')
    agent_diff = compute_diff(initial, state)
    # Singleton-field change is invisible to compute_diff — expected.
    assert agent_diff == [], (
        f"patient is a singleton; phone change must not appear in the "
        f"list-based diff. Got: {agent_diff}"
    )

    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is True, f"failures: {report.failures}"
    assert report.score == 1.0, f"expected 1.0, got {report.score}"


def test_do_nothing_fails():
    """Agent leaves state untouched.
    Expected: passed == False (positive constraint fails with critical severity);
    score drops by the 0.3 critical penalty."""
    sm, sid, targets, initial, state = _setup_session()

    task = get_task('pp_update_phone')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        f"do-nothing trajectory passed unexpectedly. failures: {report.failures}"
    )
    # 1.0 raw - 0.3 (critical penalty from failing phone constraint) = 0.7
    assert report.score < 1.0, f"expected < 1.0, got {report.score}"
    # Confirm the phone constraint is the specifically-failing check.
    failing_descs = [nc["desc"] for nc in report.negative_checks if not nc["passed"]]
    assert any("phone was updated" in d for d in failing_descs), (
        f"expected phone-update constraint failure, got: {failing_descs}"
    )


def test_wrong_phone_value_fails():
    """Agent sets the phone to something that isn't the target value.
    Expected: passed == False; critical phone-update constraint fails."""
    sm, sid, targets, initial, state = _setup_session()
    state.patient.phone = "(555) 999-0000"  # not targets['new_phone']

    task = get_task('pp_update_phone')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        f"wrong-phone trajectory passed unexpectedly. failures: {report.failures}"
    )
    failing_descs = [nc["desc"] for nc in report.negative_checks if not nc["passed"]]
    assert any("phone was updated" in d for d in failing_descs), (
        f"expected phone-update constraint failure, got: {failing_descs}"
    )


def test_emergency_contact_collateral_fails():
    """Agent updates patient.phone correctly BUT also changes the emergency
    contact phone — a common mis-click in the Profile UI.
    Expected: passed == False; emergency-contact constraint flagged."""
    sm, sid, targets, initial, state = _setup_session()
    state.patient.phone = targets["new_phone"]
    state.patient.emergency_contact.phone = targets["new_phone"]  # collateral

    task = get_task('pp_update_phone')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        f"emergency-contact collateral trajectory passed unexpectedly. "
        f"failures: {report.failures}"
    )
    failing_descs = [nc["desc"] for nc in report.negative_checks if not nc["passed"]]
    assert any("Emergency contact" in d for d in failing_descs), (
        f"expected emergency-contact constraint failure, got: {failing_descs}"
    )


def test_email_tampering_fails():
    """Agent updates phone correctly but also changes the email.
    Expected: passed == False; email constraint flagged."""
    sm, sid, targets, initial, state = _setup_session()
    state.patient.phone = targets["new_phone"]
    state.patient.email = "hacker@evil.com"

    task = get_task('pp_update_phone')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        f"email-tampering trajectory passed unexpectedly. "
        f"failures: {report.failures}"
    )
    failing_descs = [nc["desc"] for nc in report.negative_checks if not nc["passed"]]
    assert any("email" in d.lower() for d in failing_descs), (
        f"expected email constraint failure, got: {failing_descs}"
    )
