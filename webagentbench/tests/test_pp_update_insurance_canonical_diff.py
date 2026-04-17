"""End-to-end tests for pp_update_insurance canonical_diff.

The task updates nested fields on ``state.patient.insurance_plan`` — but
``patient`` is a SINGLETON on ``PatientPortalState`` (not a list). ``compute_diff``
only iterates list-valued collections, so patient-field mutations don't produce
any ``Update`` entry in ``agent_diff``. The positive signal is therefore a set
of ``critical``-severity ``constraint`` entries on the insurance_plan fields;
invariants + additional constraints guard against collateral damage.

With ``total_weight == 0`` (no create/update/delete entries), the score is
``max(0.0, 1.0 - sum_penalties)``. Correct → 1.0; do-nothing → score drops by
three 0.3 critical penalties (floored at 0.0) with ``passed=False``.
"""

from webagentbench.backend.state import SessionManager
from webagentbench.evaluator_diff import compute_diff, match_diff
from webagentbench.tasks._registry import get_task


def _setup_session(seed: int = 42):
    """Fresh session + initial snapshot + live state."""
    sm = SessionManager()
    sid, targets, _ = sm.create_session(
        env_id='patient_portal',
        task_id='pp_update_insurance',
        seed=seed,
    )
    initial = sm.get_initial_snapshot(sid)
    state = sm.get_state(sid)
    return sm, sid, dict(targets), initial, state


def _apply_correct_update(state):
    """Apply the agent-equivalent update to all three target insurance fields."""
    state.patient.insurance_plan.plan_name = "Aetna PPO Silver"
    state.patient.insurance_plan.member_id = "AET-5529103"
    state.patient.insurance_plan.group_number = "GRP-77412"


def test_correct_trajectory_passes():
    """Agent updates all three insurance fields and touches nothing else.
    Expected: score == 1.0, passed == True, no failures."""
    sm, sid, targets, initial, state = _setup_session()

    _apply_correct_update(state)

    task = get_task('pp_update_insurance')
    agent_diff = compute_diff(initial, state)
    # Singleton-field change is invisible to compute_diff — expected.
    assert agent_diff == [], (
        f"patient is a singleton; insurance_plan change must not appear in "
        f"the list-based diff. Got: {agent_diff}"
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
    Expected: passed == False (three critical positive constraints fail)."""
    sm, sid, targets, initial, state = _setup_session()

    task = get_task('pp_update_insurance')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        f"do-nothing trajectory passed unexpectedly. failures: {report.failures}"
    )
    assert report.score < 1.0, f"expected < 1.0, got {report.score}"
    failing_descs = [nc["desc"] for nc in report.negative_checks if not nc["passed"]]
    assert any("plan name" in d.lower() for d in failing_descs), (
        f"expected plan-name constraint failure, got: {failing_descs}"
    )
    assert any("member id" in d.lower() for d in failing_descs), (
        f"expected member-id constraint failure, got: {failing_descs}"
    )
    assert any("group number" in d.lower() for d in failing_descs), (
        f"expected group-number constraint failure, got: {failing_descs}"
    )


def test_wrong_member_id_fails():
    """Agent updates plan_name + group_number correctly but uses the wrong
    member ID — a classic copy-paste slip.
    Expected: passed == False; member-id constraint flagged."""
    sm, sid, targets, initial, state = _setup_session()
    state.patient.insurance_plan.plan_name = "Aetna PPO Silver"
    state.patient.insurance_plan.member_id = "AET-0000000"  # wrong
    state.patient.insurance_plan.group_number = "GRP-77412"

    task = get_task('pp_update_insurance')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        f"wrong-member-id trajectory passed unexpectedly. "
        f"failures: {report.failures}"
    )
    failing_descs = [nc["desc"] for nc in report.negative_checks if not nc["passed"]]
    assert any("member id" in d.lower() for d in failing_descs), (
        f"expected member-id constraint failure, got: {failing_descs}"
    )


def test_phone_collateral_fails():
    """Agent updates insurance correctly BUT clears the phone number while
    editing the profile — the exact collateral the legacy negative_check guarded.
    Expected: passed == False; phone constraint flagged."""
    sm, sid, targets, initial, state = _setup_session()
    _apply_correct_update(state)
    state.patient.phone = ""  # collateral damage

    task = get_task('pp_update_insurance')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        f"phone-collateral trajectory passed unexpectedly. "
        f"failures: {report.failures}"
    )
    failing_descs = [nc["desc"] for nc in report.negative_checks if not nc["passed"]]
    assert any("phone" in d.lower() for d in failing_descs), (
        f"expected phone constraint failure, got: {failing_descs}"
    )


def test_email_tampering_fails():
    """Agent updates insurance correctly but also changes the email.
    Expected: passed == False; email constraint flagged."""
    sm, sid, targets, initial, state = _setup_session()
    _apply_correct_update(state)
    state.patient.email = "hacker@evil.com"

    task = get_task('pp_update_insurance')
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
