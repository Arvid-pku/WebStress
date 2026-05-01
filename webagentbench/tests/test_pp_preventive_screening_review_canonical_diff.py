"""End-to-end tests for pp_preventive_screening_review canonical_diff.

Bijection CREATE pattern: one Appointment per overdue screening name,
provider = PCP, reason = screening name (exact match).
"""

from datetime import datetime, timezone, timedelta

from webagentbench.backend.state import SessionManager
from webagentbench.backend.models.patient_portal import Appointment
from webagentbench.eval_core import compute_diff, match_diff
from webagentbench.tasks._registry import get_task


def _setup_session(seed: int = 42):
    sm = SessionManager()
    sid, targets, _ = sm.create_session(
        env_id="patient_portal",
        task_id="pp_preventive_screening_review",
        seed=seed,
    )
    initial = sm.get_initial_snapshot(sid)
    state = sm.get_state(sid)
    return sm, sid, dict(targets), initial, state


def _snapshot_dict(snap):
    return snap.model_dump() if hasattr(snap, "model_dump") else snap


def _make_appt(*, id: str, provider_id: str, reason: str, offset_days: int = 7) -> Appointment:
    when = datetime.now(timezone.utc) + timedelta(days=offset_days)
    return Appointment(
        id=id,
        provider_id=provider_id,
        datetime=when,
        type="in-person",
        status="scheduled",
        reason=reason,
    )


def _run(targets, initial, state):
    task = get_task("pp_preventive_screening_review")
    final = state.model_dump()
    initial_dict = _snapshot_dict(initial)
    agent_diff = compute_diff(initial_dict, final)
    return match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial_dict, final=final,
    )


def test_correct_trajectory_passes():
    sm, sid, targets, initial, state = _setup_session()
    assert targets["overdue_screening_names"], "seed did not emit any overdue screenings"

    for i, name in enumerate(targets["overdue_screening_names"]):
        state.appointments.append(_make_appt(
            id=f"appt_new_{i}",
            provider_id=targets["pcp_id"],
            reason=name,
            offset_days=7 + i,
        ))

    report = _run(targets, initial, state)
    assert report.passed is True, f"failures: {report.failures}"
    assert report.score == 1.0, f"expected 1.0, got {report.score}"


def test_wrong_reason_fails():
    """reason doesn't match any screening name."""
    sm, sid, targets, initial, state = _setup_session()
    assert targets["overdue_screening_names"]

    for i, name in enumerate(targets["overdue_screening_names"]):
        state.appointments.append(_make_appt(
            id=f"appt_new_{i}",
            provider_id=targets["pcp_id"],
            reason="Routine checkup",  # not a screening name
            offset_days=7 + i,
        ))

    report = _run(targets, initial, state)
    assert report.passed is False


def test_partial_fails():
    """Only some overdue screenings scheduled (saturation failure)."""
    sm, sid, targets, initial, state = _setup_session()
    overdue = targets["overdue_screening_names"]
    assert len(overdue) >= 2, "seed needs >= 2 overdue screenings for this test"

    # Schedule only the first overdue screening.
    state.appointments.append(_make_appt(
        id="appt_new_0",
        provider_id=targets["pcp_id"],
        reason=overdue[0],
    ))

    report = _run(targets, initial, state)
    assert report.passed is False


def test_extra_appointment_fails():
    """Correct screenings + one extra for a non-overdue / unrelated reason.

    The extra entry uses a reason outside the overdue set so the unaccounted
    sweep flags it; the "Agent did not schedule more appointments than overdue
    screenings" bijection-excess invariant fires even when the reason happens
    to match another applicable (but non-overdue) screening.
    """
    sm, sid, targets, initial, state = _setup_session()

    for i, name in enumerate(targets["overdue_screening_names"]):
        state.appointments.append(_make_appt(
            id=f"appt_new_{i}",
            provider_id=targets["pcp_id"],
            reason=name,
        ))
    # Extra with a reason that cannot match any overdue screening.
    state.appointments.append(_make_appt(
        id="appt_extra",
        provider_id=targets["pcp_id"],
        reason="Unrelated follow-up",
        offset_days=30,
    ))

    report = _run(targets, initial, state)
    assert report.passed is False


def test_no_mutation_fails():
    """Agent did nothing — bijection under-saturated, must fail."""
    sm, sid, targets, initial, state = _setup_session()
    # no mutation

    report = _run(targets, initial, state)
    assert report.passed is False
    assert report.score < 1.0, f"do-nothing got score {report.score}"
