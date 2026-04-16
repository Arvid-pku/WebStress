"""End-to-end integration tests for pp_immunization_gap_review canonical_diff.

Covers three trajectories:
- correct: one appointment per due vaccine, correct provider, future date
- wrong provider: provider_id not in admin_providers for that vaccine
- excess: one extra appointment beyond the bijection count
"""

from datetime import datetime, timezone, timedelta

from webagentbench.backend.state import SessionManager
from webagentbench.backend.models.patient_portal import Appointment
from webagentbench.evaluator_diff import compute_diff, match_diff
from webagentbench.tasks._registry import get_task


def _setup_session(seed: int = 42):
    sm = SessionManager()
    sid, targets, _ = sm.create_session(
        env_id="patient_portal",
        task_id="pp_immunization_gap_review",
        seed=seed,
    )
    initial_snapshot = sm.get_initial_snapshot(sid)
    state = sm.get_state(sid)
    return sm, sid, dict(targets), initial_snapshot, state


def _future_datetime_in_window(targets: dict) -> str:
    """ISO string within [window_start, window_end]."""
    start = datetime.fromisoformat(targets["window_start"].replace("Z", "+00:00"))
    return (start + timedelta(days=7)).isoformat()


def _make_appt(**kwargs) -> Appointment:
    kwargs.setdefault("type", "in-person")
    kwargs.setdefault("status", "scheduled")
    kwargs.setdefault("reason", "Immunization")
    return Appointment(**kwargs)


def _snapshot_dict(snap):
    return snap.model_dump() if hasattr(snap, "model_dump") else snap


def test_correct_trajectory_passes():
    sm, sid, targets, initial, state = _setup_session()
    future = _future_datetime_in_window(targets)

    for imm_id in targets["due_imm_ids"]:
        providers = targets["admin_providers"][imm_id]
        state.appointments.append(_make_appt(
            id=f"appt_new_{imm_id}",
            provider_id=providers[0],
            datetime=future,
        ))

    final = state.model_dump()
    initial_dict = _snapshot_dict(initial)
    agent_diff = compute_diff(initial_dict, final)
    task = get_task("pp_immunization_gap_review")
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=targets,
        initial=initial_dict,
        final=final,
    )
    assert report.passed is True, f"failures: {report.failures}"


def test_wrong_provider_fails():
    sm, sid, targets, initial, state = _setup_session()
    future = _future_datetime_in_window(targets)

    for imm_id in targets["due_imm_ids"]:
        state.appointments.append(_make_appt(
            id=f"appt_new_{imm_id}",
            provider_id="prov_wrong_id",  # not in admin_providers
            datetime=future,
        ))

    final = state.model_dump()
    initial_dict = _snapshot_dict(initial)
    agent_diff = compute_diff(initial_dict, final)
    task = get_task("pp_immunization_gap_review")
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=targets,
        initial=initial_dict,
        final=final,
    )
    assert report.passed is False


def test_excess_appointment_fails():
    sm, sid, targets, initial, state = _setup_session()
    future = _future_datetime_in_window(targets)

    for imm_id in targets["due_imm_ids"]:
        providers = targets["admin_providers"][imm_id]
        state.appointments.append(_make_appt(
            id=f"appt_new_{imm_id}",
            provider_id=providers[0],
            datetime=future,
        ))
    extra_provider = list(targets["admin_providers"].values())[0][0]
    state.appointments.append(_make_appt(
        id="appt_extra",
        provider_id=extra_provider,
        datetime=future,
    ))

    final = state.model_dump()
    initial_dict = _snapshot_dict(initial)
    agent_diff = compute_diff(initial_dict, final)
    task = get_task("pp_immunization_gap_review")
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=targets,
        initial=initial_dict,
        final=final,
    )
    assert report.passed is False
