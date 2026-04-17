"""End-to-end tests for pp_view_insurance canonical_diff.

Task: schedule exactly one Patient Services appointment at the next available
admin slot with reason "Insurance card verification", without touching
prescriptions, messages, labs, referrals, claims, or immunizations.

The target set ``admin_provider_ids`` is a LIST (there may be multiple admin
providers). The canonical slot is the EARLIEST available slot ACROSS ALL
admin providers in the pool.

Trajectories covered:
- correct (earliest admin slot, correct reason) -> passes 1.0
- wrong provider (non-admin) -> fails
- wrong reason (close but not exact) -> fails
- not-earliest slot (2nd earliest across admin pool) -> fails
- no mutation (empty agent diff) -> fails
"""

from webagentbench.backend.models.patient_portal import Appointment
from webagentbench.backend.state import SessionManager
from webagentbench.evaluator_diff import compute_diff, match_diff
from webagentbench.tasks._registry import get_task


def _setup_session(seed: int = 42):
    sm = SessionManager()
    sid, targets, _ = sm.create_session(
        env_id="patient_portal",
        task_id="pp_view_insurance",
        seed=seed,
    )
    initial = sm.get_initial_snapshot(sid)
    state = sm.get_state(sid)
    return sm, sid, dict(targets), initial, state


def _admin_slots_sorted(initial, admin_ids):
    """All slots across every provider whose id is in admin_ids, sorted ascending."""
    return sorted(
        s.datetime
        for p in initial.providers
        if p.id in admin_ids
        for s in p.available_slots
    )


def _earliest_admin_slot(initial, admin_ids):
    slots = _admin_slots_sorted(initial, admin_ids)
    if not slots:
        raise ValueError(f"No admin provider slots in initial for ids={admin_ids!r}")
    return slots[0]


def _provider_for_slot(initial, admin_ids, target_dt):
    """Return the admin provider whose available_slots contain target_dt."""
    for p in initial.providers:
        if p.id in admin_ids:
            for s in p.available_slots:
                if s.datetime == target_dt:
                    return p.id
    raise ValueError(f"no admin provider owns slot {target_dt!r}")


def _make_appt(**kwargs) -> Appointment:
    kwargs.setdefault("type", "in-person")
    kwargs.setdefault("status", "scheduled")
    kwargs.setdefault("reason", "Insurance card verification")
    return Appointment(**kwargs)


def test_correct_trajectory_passes():
    sm, sid, targets, initial, state = _setup_session()
    admin_ids = list(targets["admin_provider_ids"])
    earliest = _earliest_admin_slot(initial, admin_ids)
    prov_id = _provider_for_slot(initial, admin_ids, earliest)
    state.appointments.append(_make_appt(
        id="appt_new_insurance_verify",
        provider_id=prov_id,
        datetime=earliest,
    ))

    task = get_task("pp_view_insurance")
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is True, f"failures: {report.failures}"
    assert report.score == 1.0, f"expected 1.0, got {report.score}"


def test_wrong_provider_fails():
    """Appointment scheduled with a non-admin provider -- expr on provider_id fails."""
    sm, sid, targets, initial, state = _setup_session()
    admin_ids = set(targets["admin_provider_ids"])
    other = next(
        p for p in state.providers
        if p.id not in admin_ids and p.available_slots
    )
    state.appointments.append(_make_appt(
        id="appt_new_wrong_prov",
        provider_id=other.id,
        datetime=min(s.datetime for s in other.available_slots),
    ))

    task = get_task("pp_view_insurance")
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False


def test_wrong_reason_fails():
    """Appointment reason doesn't match the required exact string."""
    sm, sid, targets, initial, state = _setup_session()
    admin_ids = list(targets["admin_provider_ids"])
    earliest = _earliest_admin_slot(initial, admin_ids)
    prov_id = _provider_for_slot(initial, admin_ids, earliest)
    state.appointments.append(_make_appt(
        id="appt_new_wrong_reason",
        provider_id=prov_id,
        datetime=earliest,
        reason="Insurance verification",  # close but not exact
    ))

    task = get_task("pp_view_insurance")
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False


def test_not_earliest_slot_fails():
    """Appointment uses the 2nd-earliest slot across the admin pool."""
    sm, sid, targets, initial, state = _setup_session()
    admin_ids = list(targets["admin_provider_ids"])
    slots = _admin_slots_sorted(initial, admin_ids)
    assert len(slots) >= 2, "seed must produce >=2 admin-pool slots for this test"
    second = slots[1]
    prov_id = _provider_for_slot(initial, admin_ids, second)
    state.appointments.append(_make_appt(
        id="appt_new_later_slot",
        provider_id=prov_id,
        datetime=second,
    ))

    task = get_task("pp_view_insurance")
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False


def test_no_mutation_fails():
    """Agent did nothing at all -- should fail the required create."""
    sm, sid, targets, initial, state = _setup_session()

    task = get_task("pp_view_insurance")
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "no-mutation trajectory unexpectedly passed -- invariants are "
        "contributing to the positive numerator (see hazard Class 1)"
    )
