"""End-to-end tests for pp_complex_scheduling canonical_diff.

Task: schedule 3 appointments in sequence with required spacing:
  1) Blood work labs (scheduled first).
  2) Cardiology appointment at least 5 days after the labs,
     with an approved referral.
  3) PCP follow-up at least 3 days after the cardiology visit.

Shape: three creates + two gap constraints.

Trajectories covered:
- correct (all three appointments, 5+3-day spacing) -> passes 1.0
- cardiology gap < 5 days after labs -> fails constraint 0
- PCP gap < 3 days after cardiology -> fails constraint 1
- missing lab appointment -> create[0] unmatched, fails
- missing cardiology appointment -> create[1] unmatched, fails
- no mutation (do-nothing) -> fails
"""

from datetime import timedelta

from webagentbench.backend.models.patient_portal import Appointment
from webagentbench.backend.state import SessionManager
from webagentbench.eval_core import compute_diff, match_diff
from webagentbench.tasks._registry import get_task


def _setup_session(seed: int = 42):
    sm = SessionManager()
    sid, targets, _ = sm.create_session(
        env_id="patient_portal",
        task_id="pp_complex_scheduling",
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
    """Pick any non-PCP, non-cardio provider for the lab appointment."""
    pcp_id = targets["pcp_id"]
    cardio_ids = set(targets["cardio_provider_ids"])
    return next(
        p.id for p in state.providers
        if p.id != pcp_id and p.id not in cardio_ids
    )


def test_correct_trajectory_passes():
    """All three appointments in order with 5-day and 3-day gaps."""
    sm, sid, targets, initial, state = _setup_session()
    pcp_id = targets["pcp_id"]
    cardio_ids = list(targets["cardio_provider_ids"])
    approved_ref_ids = list(targets["approved_ref_ids"])

    lab_dt = _future_dt(initial, days_ahead=10)
    cardio_dt = lab_dt + timedelta(days=6)   # >= 5 days after lab
    pcp_dt = cardio_dt + timedelta(days=4)   # >= 3 days after cardio

    state.appointments.append(_make_appt(
        id="appt_new_lab",
        provider_id=_lab_provider_id(state, targets),
        datetime=lab_dt,
        reason="Blood work / pre-visit lab panel",
    ))
    state.appointments.append(_make_appt(
        id="appt_new_cardio",
        provider_id=cardio_ids[0],
        datetime=cardio_dt,
        reason="Cardiology consultation",
        linked_referral_id=approved_ref_ids[0],
    ))
    state.appointments.append(_make_appt(
        id="appt_new_pcp",
        provider_id=pcp_id,
        datetime=pcp_dt,
        reason="PCP follow-up visit",
    ))

    task = get_task("pp_complex_scheduling")
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is True, f"failures: {report.failures}"
    assert report.score == 1.0, f"expected 1.0, got {report.score}"


def test_cardiology_gap_too_small_fails():
    """Cardiology < 5 days after lab -> constraint[0] fails."""
    sm, sid, targets, initial, state = _setup_session()
    pcp_id = targets["pcp_id"]
    cardio_ids = list(targets["cardio_provider_ids"])
    approved_ref_ids = list(targets["approved_ref_ids"])

    lab_dt = _future_dt(initial, days_ahead=10)
    cardio_dt = lab_dt + timedelta(days=2)   # only 2 days — too tight
    pcp_dt = cardio_dt + timedelta(days=5)

    state.appointments.append(_make_appt(
        id="appt_new_lab",
        provider_id=_lab_provider_id(state, targets),
        datetime=lab_dt,
        reason="Blood work",
    ))
    state.appointments.append(_make_appt(
        id="appt_new_cardio",
        provider_id=cardio_ids[0],
        datetime=cardio_dt,
        reason="Cardiology consultation",
        linked_referral_id=approved_ref_ids[0],
    ))
    state.appointments.append(_make_appt(
        id="appt_new_pcp",
        provider_id=pcp_id,
        datetime=pcp_dt,
        reason="PCP follow-up",
    ))

    task = get_task("pp_complex_scheduling")
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "cardiology within 5 days of labs must fail constraint[0]"
    )


def test_pcp_gap_too_small_fails():
    """PCP < 3 days after cardiology -> constraint[1] fails."""
    sm, sid, targets, initial, state = _setup_session()
    pcp_id = targets["pcp_id"]
    cardio_ids = list(targets["cardio_provider_ids"])
    approved_ref_ids = list(targets["approved_ref_ids"])

    lab_dt = _future_dt(initial, days_ahead=10)
    cardio_dt = lab_dt + timedelta(days=7)
    pcp_dt = cardio_dt + timedelta(days=1)   # only 1 day — too tight

    state.appointments.append(_make_appt(
        id="appt_new_lab",
        provider_id=_lab_provider_id(state, targets),
        datetime=lab_dt,
        reason="Blood work",
    ))
    state.appointments.append(_make_appt(
        id="appt_new_cardio",
        provider_id=cardio_ids[0],
        datetime=cardio_dt,
        reason="Cardiology consultation",
        linked_referral_id=approved_ref_ids[0],
    ))
    state.appointments.append(_make_appt(
        id="appt_new_pcp",
        provider_id=pcp_id,
        datetime=pcp_dt,
        reason="PCP follow-up",
    ))

    task = get_task("pp_complex_scheduling")
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "PCP within 3 days of cardiology must fail constraint[1]"
    )


def test_missing_lab_fails():
    """Only cardiology + PCP scheduled, no lab -> create[0] unmatched."""
    sm, sid, targets, initial, state = _setup_session()
    pcp_id = targets["pcp_id"]
    cardio_ids = list(targets["cardio_provider_ids"])
    approved_ref_ids = list(targets["approved_ref_ids"])

    cardio_dt = _future_dt(initial, days_ahead=20)
    pcp_dt = cardio_dt + timedelta(days=5)

    state.appointments.append(_make_appt(
        id="appt_new_cardio",
        provider_id=cardio_ids[0],
        datetime=cardio_dt,
        reason="Cardiology consultation",
        linked_referral_id=approved_ref_ids[0],
    ))
    state.appointments.append(_make_appt(
        id="appt_new_pcp",
        provider_id=pcp_id,
        datetime=pcp_dt,
        reason="PCP follow-up",
    ))

    task = get_task("pp_complex_scheduling")
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, "missing lab must leave create[0] unmatched"
    assert report.score < 1.0


def test_missing_cardiology_fails():
    """Only lab + PCP scheduled, no cardiology -> create[1] unmatched."""
    sm, sid, targets, initial, state = _setup_session()
    pcp_id = targets["pcp_id"]

    lab_dt = _future_dt(initial, days_ahead=10)
    pcp_dt = lab_dt + timedelta(days=10)

    state.appointments.append(_make_appt(
        id="appt_new_lab",
        provider_id=_lab_provider_id(state, targets),
        datetime=lab_dt,
        reason="Blood work",
    ))
    state.appointments.append(_make_appt(
        id="appt_new_pcp",
        provider_id=pcp_id,
        datetime=pcp_dt,
        reason="PCP follow-up",
    ))

    task = get_task("pp_complex_scheduling")
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "missing cardiology must leave create[1] unmatched"
    )
    assert report.score < 1.0


def test_no_mutation_fails():
    """Do-nothing trajectory must not pass."""
    sm, sid, targets, initial, state = _setup_session()
    # no mutation

    task = get_task("pp_complex_scheduling")
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, "no-op trajectory must fail"
    assert report.score < 1.0
