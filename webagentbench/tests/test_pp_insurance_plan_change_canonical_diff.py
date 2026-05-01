"""End-to-end tests for pp_insurance_plan_change canonical_diff.

Task: update insurance plan details (plan_name, member_id, group_number) to
specific new values AND flip the default-pharmacy flag from the current
default onto the mail-order pharmacy.

Shape: pharmacy update (is_default flip, two entries) + singleton-state
constraints (three insurance fields — patient is a SINGLETON so these
do not appear in compute_diff, they must be checked via `constraints:`).

Trajectories covered:
- correct (plan+member+group updated, mail-order becomes default) -> 1.0
- wrong_plan_name (one insurance field wrong) -> fails
- wrong_member_id -> fails
- mail_order_not_default (plan updated, old default not flipped) -> fails
- prescription_discontinued (active rx flipped to discontinued) -> fails
- no_mutation -> fails, score 0.0
"""

from webagentbench.backend.models.patient_portal import InsurancePlan
from webagentbench.backend.state import SessionManager
from webagentbench.eval_core import compute_diff, match_diff
from webagentbench.tasks._registry import get_task


NEW_PLAN_NAME = "Aetna PPO Silver"
NEW_MEMBER_ID = "AET-5529103"
NEW_GROUP_NUMBER = "GRP-88914"


def _setup_session(seed: int = 42):
    sm = SessionManager()
    sid, targets, _ = sm.create_session(
        env_id="patient_portal",
        task_id="pp_insurance_plan_change",
        seed=seed,
    )
    initial = sm.get_initial_snapshot(sid)
    state = sm.get_state(sid)
    return sm, sid, dict(targets), initial, state


def _apply_new_insurance(state, **overrides):
    """Mutate state.patient.insurance_plan to the new plan values."""
    current = state.patient.insurance_plan
    new_plan = InsurancePlan(
        plan_name=overrides.get("plan_name", NEW_PLAN_NAME),
        member_id=overrides.get("member_id", NEW_MEMBER_ID),
        group_number=overrides.get("group_number", NEW_GROUP_NUMBER),
        copay=current.copay,
        deductible=current.deductible,
        deductible_met=current.deductible_met,
    )
    state.patient.insurance_plan = new_plan


def _flip_mail_order_to_default(state, targets):
    """Set the mail-order pharmacy as the new default; unset the old one."""
    mail_order_id = targets["mail_order_pharmacy_id"]
    old_default_id = targets["default_pharmacy_id"]
    for pharm in state.pharmacies:
        if pharm.id == mail_order_id:
            pharm.is_default = True
        elif pharm.id == old_default_id:
            pharm.is_default = False


def _run_match(state, initial, targets):
    task = get_task("pp_insurance_plan_change")
    agent_diff = compute_diff(initial, state)
    return match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )


def test_correct_trajectory_passes():
    sm, sid, targets, initial, state = _setup_session()
    _apply_new_insurance(state)
    _flip_mail_order_to_default(state, targets)
    report = _run_match(state, initial, targets)
    assert report.passed is True, f"failures: {report.failures}"
    assert report.score == 1.0, f"expected 1.0, got {report.score}"


def test_wrong_plan_name_fails():
    """Agent updated the member ID/group but used the wrong plan name."""
    sm, sid, targets, initial, state = _setup_session()
    _apply_new_insurance(state, plan_name="Aetna PPO Gold")
    _flip_mail_order_to_default(state, targets)
    report = _run_match(state, initial, targets)
    assert report.passed is False


def test_wrong_member_id_fails():
    """Plan name + group correct; member ID wrong."""
    sm, sid, targets, initial, state = _setup_session()
    _apply_new_insurance(state, member_id="AET-0000000")
    _flip_mail_order_to_default(state, targets)
    report = _run_match(state, initial, targets)
    assert report.passed is False


def test_mail_order_not_default_fails():
    """Insurance plan updated correctly but pharmacy default not flipped."""
    sm, sid, targets, initial, state = _setup_session()
    _apply_new_insurance(state)
    # Do not flip pharmacies — mail-order remains non-default.
    report = _run_match(state, initial, targets)
    assert report.passed is False


def test_prescription_discontinued_fails():
    """Everything correct but an active rx was discontinued -> invariant fails."""
    sm, sid, targets, initial, state = _setup_session()
    _apply_new_insurance(state)
    _flip_mail_order_to_default(state, targets)
    active_ids = targets["active_rx_ids"]
    assert active_ids, "seed must produce at least one active rx for this test"
    for rx in state.prescriptions:
        if rx.id == active_ids[0]:
            rx.status = "discontinued"
            break
    report = _run_match(state, initial, targets)
    assert report.passed is False


def test_no_mutation_fails():
    """Do-nothing trajectory must not pass."""
    sm, sid, targets, initial, state = _setup_session()
    report = _run_match(state, initial, targets)
    assert report.passed is False
    assert report.score == 0.0, f"expected 0.0 (no-op), got {report.score}"
