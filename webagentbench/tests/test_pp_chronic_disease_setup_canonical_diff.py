"""End-to-end tests for pp_chronic_disease_setup canonical_diff.

Shape: five non-bijection creates on Appointment, one per monitoring action
(HbA1c, kidney function, PCP blood-pressure, cardiology, endocrinology)
with exact reason strings and specialty-pool / PCP-id predicates on the
last three.
"""

from datetime import datetime, timezone, timedelta

from webagentbench.backend.models.patient_portal import Appointment
from webagentbench.backend.state import SessionManager
from webagentbench.evaluator_diff import compute_diff, match_diff
from webagentbench.tasks._registry import get_task


def _setup_session(seed: int = 42):
    sm = SessionManager()
    sid, targets, _ = sm.create_session(
        env_id='patient_portal',
        task_id='pp_chronic_disease_setup',
        seed=seed,
    )
    initial = sm.get_initial_snapshot(sid)
    state = sm.get_state(sid)
    return sm, sid, dict(targets), initial, state


def _make_appt(**kwargs) -> Appointment:
    kwargs.setdefault("type", "in-person")
    kwargs.setdefault("status", "scheduled")
    kwargs.setdefault("datetime", datetime.now(timezone.utc) + timedelta(days=7))
    return Appointment(**kwargs)


def _seed_five_creates(targets, state):
    cardio_id = targets["cardio_provider_ids"][0]
    endo_id = targets["endo_provider_ids"][0]
    pcp_id = targets["pcp_id"]
    state.appointments.append(_make_appt(
        id="appt_hba1c",
        provider_id=pcp_id,
        reason="HbA1c monitoring",
    ))
    state.appointments.append(_make_appt(
        id="appt_kidney",
        provider_id=pcp_id,
        reason="Kidney function monitoring",
    ))
    state.appointments.append(_make_appt(
        id="appt_bp",
        provider_id=pcp_id,
        reason="Monthly blood pressure review",
    ))
    state.appointments.append(_make_appt(
        id="appt_cardio",
        provider_id=cardio_id,
        reason="Annual cardiology monitoring",
    ))
    state.appointments.append(_make_appt(
        id="appt_endo",
        provider_id=endo_id,
        reason="Annual endocrinology monitoring",
    ))


def _run_match(state, initial, targets):
    task = get_task('pp_chronic_disease_setup')
    agent_diff = compute_diff(initial, state)
    return match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )


def test_correct_trajectory_passes():
    sm, sid, targets, initial, state = _setup_session()
    _seed_five_creates(targets, state)
    report = _run_match(state, initial, targets)
    assert report.passed is True, f"failures: {report.failures}"
    assert report.score == 1.0, f"expected 1.0, got {report.score}"


def test_no_mutation_fails():
    sm, sid, targets, initial, state = _setup_session()
    report = _run_match(state, initial, targets)
    assert report.passed is False
    assert report.score == 0.0


def test_missing_cardiology_fails():
    """Drop the cardiology create → the matcher must reject."""
    sm, sid, targets, initial, state = _setup_session()
    pcp_id = targets["pcp_id"]
    endo_id = targets["endo_provider_ids"][0]
    state.appointments.append(_make_appt(
        id="appt_hba1c",
        provider_id=pcp_id,
        reason="HbA1c monitoring",
    ))
    state.appointments.append(_make_appt(
        id="appt_kidney",
        provider_id=pcp_id,
        reason="Kidney function monitoring",
    ))
    state.appointments.append(_make_appt(
        id="appt_bp",
        provider_id=pcp_id,
        reason="Monthly blood pressure review",
    ))
    state.appointments.append(_make_appt(
        id="appt_endo",
        provider_id=endo_id,
        reason="Annual endocrinology monitoring",
    ))
    report = _run_match(state, initial, targets)
    assert report.passed is False
    assert report.score < 1.0


def test_wrong_reason_fails():
    """Mutate the PCP bp review reason to something off-spec."""
    sm, sid, targets, initial, state = _setup_session()
    _seed_five_creates(targets, state)
    for a in state.appointments:
        if a.id == "appt_bp":
            a.reason = "BP checkup"
            break
    report = _run_match(state, initial, targets)
    assert report.passed is False


def test_wrong_specialty_for_cardio_fails():
    """Book the cardiology monitoring with an endo provider → specialty predicate rejects."""
    sm, sid, targets, initial, state = _setup_session()
    pcp_id = targets["pcp_id"]
    endo_id = targets["endo_provider_ids"][0]
    state.appointments.append(_make_appt(
        id="appt_hba1c",
        provider_id=pcp_id,
        reason="HbA1c monitoring",
    ))
    state.appointments.append(_make_appt(
        id="appt_kidney",
        provider_id=pcp_id,
        reason="Kidney function monitoring",
    ))
    state.appointments.append(_make_appt(
        id="appt_bp",
        provider_id=pcp_id,
        reason="Monthly blood pressure review",
    ))
    # Wrong specialty for cardiology
    state.appointments.append(_make_appt(
        id="appt_cardio_bad",
        provider_id=endo_id,
        reason="Annual cardiology monitoring",
    ))
    state.appointments.append(_make_appt(
        id="appt_endo",
        provider_id=endo_id,
        datetime=datetime.now(timezone.utc) + timedelta(days=14),
        reason="Annual endocrinology monitoring",
    ))
    report = _run_match(state, initial, targets)
    assert report.passed is False


def test_discontinued_rx_fails():
    """Discontinuing a prescription violates the prescriptions invariant."""
    sm, sid, targets, initial, state = _setup_session()
    _seed_five_creates(targets, state)
    if state.prescriptions:
        state.prescriptions[0].status = "discontinued"
    report = _run_match(state, initial, targets)
    assert report.passed is False


def test_sent_message_fails():
    """Sending any new clinical message violates the messages invariant."""
    sm, sid, targets, initial, state = _setup_session()
    _seed_five_creates(targets, state)
    from webagentbench.backend.models.patient_portal import ClinicalMessage
    state.messages.append(ClinicalMessage(
        id="msg_unwanted",
        from_type="patient",
        provider_id=targets["pcp_id"],
        subject="Question",
        body="ignore",
        thread_id="thr_unwanted",
    ))
    report = _run_match(state, initial, targets)
    assert report.passed is False
