"""End-to-end tests for pp_pre_surgery_clearance canonical_diff.

Task: complete pre-surgery clearance workflow:
  1) Schedule pre-operative lab appointment (reason "Pre-operative lab work").
  2) Schedule PCP surgical-clearance appointment (reason "Surgical clearance visit").
  3) Verify surgery referral prior_auth is approved (seed-provided, read-only).
  4) Schedule orthopedic procedure appointment (reason "Orthopedic procedure clearance")
     at least 7 days after the lab appointment.

Shape: three non-bijection creates + one 7-day gap constraint + one read-only
referral-prior-auth constraint.
"""

from datetime import timedelta

from webagentbench.backend.models.patient_portal import Appointment
from webagentbench.backend.state import SessionManager
from webagentbench.evaluator_diff import compute_diff, match_diff
from webagentbench.tasks._registry import get_task


def _setup_session(seed: int = 42):
    sm = SessionManager()
    sid, targets, _ = sm.create_session(
        env_id="patient_portal",
        task_id="pp_pre_surgery_clearance",
        seed=seed,
    )
    initial = sm.get_initial_snapshot(sid)
    state = sm.get_state(sid)
    return sm, sid, dict(targets), initial, state


def _make_appt(**kwargs) -> Appointment:
    kwargs.setdefault("type", "in-person")
    kwargs.setdefault("status", "scheduled")
    return Appointment(**kwargs)


def _future_dt(initial, *, days_ahead: int):
    """Pick a future datetime based off the latest existing upcoming apt."""
    latest = max(
        (a.datetime for a in initial.appointments if a.status == "scheduled"),
        default=None,
    )
    if latest is None:
        latest = min(
            s.datetime for p in initial.providers for s in p.available_slots
        )
    return latest + timedelta(days=days_ahead)


def _lab_provider_id(state, targets) -> str:
    """Pick any non-PCP, non-ortho provider for the lab appointment."""
    pcp_id = targets["pcp_id"]
    ortho_ids = set(targets["ortho_provider_ids"])
    return next(
        p.id for p in state.providers
        if p.id != pcp_id and p.id not in ortho_ids
    )


def _seed_three_creates(state, initial, targets):
    lab_dt = _future_dt(initial, days_ahead=10)
    pcp_dt = lab_dt + timedelta(days=2)
    ortho_dt = lab_dt + timedelta(days=8)  # >= 7 days after lab

    state.appointments.append(_make_appt(
        id="appt_new_lab",
        provider_id=_lab_provider_id(state, targets),
        datetime=lab_dt,
        reason="Pre-operative lab work",
    ))
    state.appointments.append(_make_appt(
        id="appt_new_pcp",
        provider_id=targets["pcp_id"],
        datetime=pcp_dt,
        reason="Surgical clearance visit",
    ))
    state.appointments.append(_make_appt(
        id="appt_new_ortho",
        provider_id=targets["ortho_provider_ids"][0],
        datetime=ortho_dt,
        reason="Orthopedic procedure clearance",
        linked_referral_id=targets["prior_auth_ref_id"],
    ))


def _run_match(state, initial, targets):
    task = get_task("pp_pre_surgery_clearance")
    agent_diff = compute_diff(initial, state)
    return match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )


def test_correct_trajectory_passes():
    """All three appointments with 7-day lab→ortho gap, seeded prior-auth approved."""
    sm, sid, targets, initial, state = _setup_session()
    _seed_three_creates(state, initial, targets)
    report = _run_match(state, initial, targets)
    assert report.passed is True, f"failures: {report.failures}"
    assert report.score == 1.0, f"expected 1.0, got {report.score}"


def test_ortho_gap_too_small_fails():
    """Orthopedic procedure < 7 days after the lab -> gap constraint fails."""
    sm, sid, targets, initial, state = _setup_session()
    lab_dt = _future_dt(initial, days_ahead=10)
    pcp_dt = lab_dt + timedelta(days=2)
    ortho_dt = lab_dt + timedelta(days=3)  # only 3 days — too tight

    state.appointments.append(_make_appt(
        id="appt_new_lab",
        provider_id=_lab_provider_id(state, targets),
        datetime=lab_dt,
        reason="Pre-operative lab work",
    ))
    state.appointments.append(_make_appt(
        id="appt_new_pcp",
        provider_id=targets["pcp_id"],
        datetime=pcp_dt,
        reason="Surgical clearance visit",
    ))
    state.appointments.append(_make_appt(
        id="appt_new_ortho",
        provider_id=targets["ortho_provider_ids"][0],
        datetime=ortho_dt,
        reason="Orthopedic procedure clearance",
    ))
    report = _run_match(state, initial, targets)
    assert report.passed is False, (
        "orthopedic procedure within 7 days of lab must fail the gap constraint"
    )


def test_missing_lab_fails():
    """Only PCP + ortho scheduled, no lab -> create[0] unmatched + gap fails."""
    sm, sid, targets, initial, state = _setup_session()
    pcp_dt = _future_dt(initial, days_ahead=12)
    ortho_dt = _future_dt(initial, days_ahead=20)

    state.appointments.append(_make_appt(
        id="appt_new_pcp",
        provider_id=targets["pcp_id"],
        datetime=pcp_dt,
        reason="Surgical clearance visit",
    ))
    state.appointments.append(_make_appt(
        id="appt_new_ortho",
        provider_id=targets["ortho_provider_ids"][0],
        datetime=ortho_dt,
        reason="Orthopedic procedure clearance",
    ))
    report = _run_match(state, initial, targets)
    assert report.passed is False, "missing lab must leave create[0] unmatched"
    assert report.score < 1.0


def test_wrong_ortho_reason_fails():
    """Ortho appointment with wrong reason string -> create[2] unmatched."""
    sm, sid, targets, initial, state = _setup_session()
    lab_dt = _future_dt(initial, days_ahead=10)
    pcp_dt = lab_dt + timedelta(days=2)
    ortho_dt = lab_dt + timedelta(days=8)

    state.appointments.append(_make_appt(
        id="appt_new_lab",
        provider_id=_lab_provider_id(state, targets),
        datetime=lab_dt,
        reason="Pre-operative lab work",
    ))
    state.appointments.append(_make_appt(
        id="appt_new_pcp",
        provider_id=targets["pcp_id"],
        datetime=pcp_dt,
        reason="Surgical clearance visit",
    ))
    state.appointments.append(_make_appt(
        id="appt_new_ortho",
        provider_id=targets["ortho_provider_ids"][0],
        datetime=ortho_dt,
        reason="Orthopedic consult",  # wrong — not "Orthopedic procedure clearance"
    ))
    report = _run_match(state, initial, targets)
    assert report.passed is False, "wrong ortho reason must leave create[2] unmatched"


def test_ortho_wrong_specialty_fails():
    """Ortho slot filled by a non-ortho provider -> predicate fails."""
    sm, sid, targets, initial, state = _setup_session()
    lab_dt = _future_dt(initial, days_ahead=10)
    pcp_dt = lab_dt + timedelta(days=2)
    ortho_dt = lab_dt + timedelta(days=8)

    state.appointments.append(_make_appt(
        id="appt_new_lab",
        provider_id=_lab_provider_id(state, targets),
        datetime=lab_dt,
        reason="Pre-operative lab work",
    ))
    state.appointments.append(_make_appt(
        id="appt_new_pcp",
        provider_id=targets["pcp_id"],
        datetime=pcp_dt,
        reason="Surgical clearance visit",
    ))
    state.appointments.append(_make_appt(
        id="appt_wrong_specialty",
        provider_id=targets["pcp_id"],  # PCP instead of ortho
        datetime=ortho_dt,
        reason="Orthopedic procedure clearance",
    ))
    report = _run_match(state, initial, targets)
    assert report.passed is False, (
        "non-ortho provider for orthopedic procedure must fail create[2]"
    )


def test_sent_message_fails():
    """Agent sends a patient message -> violates messages invariant."""
    sm, sid, targets, initial, state = _setup_session()
    _seed_three_creates(state, initial, targets)
    # Send a patient message
    from webagentbench.backend.models.patient_portal import ClinicalMessage
    from datetime import datetime, timezone
    state.messages.append(ClinicalMessage(
        id="msg_patient_extra",
        from_type="patient",
        provider_id=targets["pcp_id"],
        subject="Surgery question",
        body="Any pre-op advice?",
        thread_id="thread_new",
        timestamp=datetime.now(timezone.utc),
    ))
    report = _run_match(state, initial, targets)
    assert report.passed is False, (
        "sending a patient message must violate the messages invariant"
    )


def test_no_mutation_fails():
    """Do-nothing trajectory must not pass."""
    sm, sid, targets, initial, state = _setup_session()
    report = _run_match(state, initial, targets)
    assert report.passed is False, "no-op trajectory must fail"
    assert report.score < 1.0
