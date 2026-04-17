"""End-to-end tests for pp_complete_account_audit canonical_diff.

Single-appointment audit task:
  - Exactly one new Appointment with an admin (Patient Services) provider.
  - reason == "Account audit review".
  - datetime == earliest slot across ALL admin providers' available_slots.
  - All other collections preserved.
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
        task_id="pp_complete_account_audit",
        seed=seed,
    )
    initial = sm.get_initial_snapshot(sid)
    state = sm.get_state(sid)
    return sm, sid, dict(targets), initial, state


def _earliest_admin_slot(initial, targets) -> datetime:
    """Mirror the canonical_diff expression for datetime."""
    admin_ids = set(targets["admin_provider_ids"])
    slots = []
    for prov in initial.providers:
        if prov.id not in admin_ids:
            continue
        for s in prov.available_slots:
            slots.append(s.datetime)
    assert slots, "admin providers have no available_slots in seed"
    return min(slots)


def _make_appt(
    *,
    id: str,
    provider_id: str,
    reason: str,
    when: datetime,
    status: str = "scheduled",
) -> Appointment:
    return Appointment(
        id=id,
        provider_id=provider_id,
        datetime=when,
        type="in-person",
        status=status,
        reason=reason,
    )


def _run(targets, initial, state):
    task = get_task("pp_complete_account_audit")
    agent_diff = compute_diff(initial, state)
    return match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )


def _schedule_correct_audit(targets, initial, state) -> Appointment:
    """Schedule one admin-provider audit appt at the earliest admin slot."""
    admin_ids = targets["admin_provider_ids"]
    assert admin_ids, "seed produced no admin providers"
    when = _earliest_admin_slot(initial, targets)
    apt = _make_appt(
        id="appt_audit",
        provider_id=admin_ids[0],
        reason="Account audit review",
        when=when,
    )
    state.appointments.append(apt)
    return apt


# ── Stage 4: correct-trajectory round-trip ────────────────────────────

def test_correct_trajectory_passes():
    sm, sid, targets, initial, state = _setup_session()
    assert targets["admin_provider_ids"], "seed emitted no admin providers"
    _schedule_correct_audit(targets, initial, state)

    report = _run(targets, initial, state)
    assert report.passed is True, f"failures: {report.failures}"
    assert report.score == 1.0, f"expected 1.0, got {report.score}"


# ── Adversarial: wrong provider (not admin) ───────────────────────────

def test_wrong_provider_fails():
    sm, sid, targets, initial, state = _setup_session()
    when = _earliest_admin_slot(initial, targets)
    # Use PCP (non-admin) provider.
    non_admin_ids = [
        p.id for p in state.providers
        if p.id not in set(targets["admin_provider_ids"])
    ]
    assert non_admin_ids, "seed has only admin providers (unexpected)"
    state.appointments.append(_make_appt(
        id="appt_bad",
        provider_id=non_admin_ids[0],
        reason="Account audit review",
        when=when,
    ))

    report = _run(targets, initial, state)
    assert report.passed is False


# ── Adversarial: wrong reason ─────────────────────────────────────────

def test_wrong_reason_fails():
    sm, sid, targets, initial, state = _setup_session()
    when = _earliest_admin_slot(initial, targets)
    state.appointments.append(_make_appt(
        id="appt_bad_reason",
        provider_id=targets["admin_provider_ids"][0],
        reason="General follow-up",  # wrong reason
        when=when,
    ))

    report = _run(targets, initial, state)
    assert report.passed is False


# ── Adversarial: not the next available slot ──────────────────────────

def test_not_next_slot_fails():
    sm, sid, targets, initial, state = _setup_session()
    when = _earliest_admin_slot(initial, targets) + timedelta(days=30)
    state.appointments.append(_make_appt(
        id="appt_late",
        provider_id=targets["admin_provider_ids"][0],
        reason="Account audit review",
        when=when,
    ))

    report = _run(targets, initial, state)
    assert report.passed is False


# ── Adversarial: cancelled an existing upcoming appointment ───────────

def test_cancelled_existing_fails():
    sm, sid, targets, initial, state = _setup_session()
    _schedule_correct_audit(targets, initial, state)

    upcoming = targets.get("upcoming_ids") or []
    assert upcoming, "seed should produce upcoming appointments"
    for apt in state.appointments:
        if apt.id == upcoming[0]:
            apt.status = "cancelled"
            break

    report = _run(targets, initial, state)
    assert report.passed is False


# ── Do-nothing baseline ──────────────────────────────────────────────

def test_no_mutation_fails():
    sm, sid, targets, initial, state = _setup_session()
    report = _run(targets, initial, state)
    assert report.passed is False
    assert report.score < 1.0, f"do-nothing got score {report.score}"
