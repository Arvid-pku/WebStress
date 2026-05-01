"""End-to-end tests for pp_check_immunizations canonical_diff.

Task: "Check which vaccinations are due and schedule an appointment for the
first one that is due."

Verifies:
  - Correct trajectory (1 appointment whose reason mentions the vaccine)
    passes with score 1.0.
  - Wrong-reason trajectory (appointment whose reason does NOT mention the
    vaccine) fails.
  - Excess trajectory (2+ new appointments) fails via the unaccounted sweep.
"""

from datetime import datetime, timezone, timedelta

from webagentbench.backend.state import SessionManager
from webagentbench.backend.models.patient_portal import Appointment
from webagentbench.backend.models.base import utc_now
from webagentbench.eval_core import compute_diff, match_diff
from webagentbench.tasks._registry import get_task


def _setup_session(seed: int = 42):
    sm = SessionManager()
    sid, targets, _ = sm.create_session(
        env_id="patient_portal",
        task_id="pp_check_immunizations",
        seed=seed,
    )
    initial = sm.get_initial_snapshot(sid)
    state = sm.get_state(sid)
    return sm, sid, dict(targets), initial, state


def _future_datetime() -> datetime:
    return (datetime.now(timezone.utc) + timedelta(days=7)).replace(
        minute=0, second=0, microsecond=0,
    )


def _make_correct_appointment(state, targets, apt_id: str = "appt_correct") -> Appointment:
    """Build an Appointment whose `reason` mentions a due vaccine name."""
    vaccine_name = targets["due_vaccine_names"][0]
    pcp_providers = [p for p in state.providers if p.specialty == "pcp"]
    provider_id = pcp_providers[0].id if pcp_providers else state.providers[0].id
    return Appointment(
        id=apt_id,
        provider_id=provider_id,
        datetime=_future_datetime(),
        type="in-person",
        status="scheduled",
        reason=f"Immunization: {vaccine_name}",
        booked_at=utc_now(),
    )


def test_correct_trajectory_passes():
    sm, sid, targets, initial, state = _setup_session()
    state.appointments.append(_make_correct_appointment(state, targets))

    task = get_task("pp_check_immunizations")
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is True, f"failures: {report.failures}"
    assert report.score == 1.0, f"expected 1.0, got {report.score}"


def test_wrong_reason_fails():
    """Appointment booked but reason doesn't mention any due vaccine."""
    sm, sid, targets, initial, state = _setup_session()
    wrong = _make_correct_appointment(state, targets, apt_id="appt_wrong_reason")
    wrong.reason = "Annual physical checkup"  # no vaccine mention
    state.appointments.append(wrong)

    task = get_task("pp_check_immunizations")
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "wrong-reason trajectory should fail — the reason predicate must "
        "actually match a due vaccine name"
    )


def test_excess_fails():
    """Agent books the correct appointment PLUS an extra one."""
    sm, sid, targets, initial, state = _setup_session()
    state.appointments.append(_make_correct_appointment(state, targets, "appt_correct_1"))
    state.appointments.append(_make_correct_appointment(state, targets, "appt_extra"))

    task = get_task("pp_check_immunizations")
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "excess-appointment trajectory should fail via the unaccounted sweep"
    )
