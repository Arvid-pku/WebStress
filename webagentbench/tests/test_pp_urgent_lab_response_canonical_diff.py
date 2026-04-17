"""End-to-end tests for pp_urgent_lab_response canonical_diff.

Task: find the critical lab result, schedule exactly one follow-up appointment
with the provider who ordered that specific lab (not the PCP unless they are
the ordering provider), using that provider's next available slot. Use reason
exactly "Critical lab follow-up". Do not send messages or modify medications.

Trajectories covered:
- correct (ordering provider + earliest slot + exact reason) → passes 1.0
- wrong provider (PCP booked when PCP isn't the lab orderer) → fails
- wrong reason (free-text mismatch) → fails
- not earliest slot (second-earliest slot of the ordering provider) → fails
- discontinued rx (medication modification violates prescriptions invariant) → fails
- no mutation (do-nothing) → fails
"""

from webagentbench.backend.models.patient_portal import Appointment
from webagentbench.backend.state import SessionManager
from webagentbench.evaluator_diff import compute_diff, match_diff
from webagentbench.tasks._registry import get_task


def _setup_session(seed: int = 42):
    sm = SessionManager()
    sid, targets, _ = sm.create_session(
        env_id="patient_portal",
        task_id="pp_urgent_lab_response",
        seed=seed,
    )
    initial = sm.get_initial_snapshot(sid)
    state = sm.get_state(sid)
    return sm, sid, dict(targets), initial, state


def _ordering_provider_id(initial, critical_lab_id: str) -> str:
    """Canonical selector: provider who ordered the specific critical lab.

    Mirrors the `expr` predicate in the canonical_diff.
    """
    lab = initial.get_lab(critical_lab_id)
    assert lab is not None, f"critical lab {critical_lab_id!r} missing from initial snapshot"
    return lab.ordered_by


def _earliest_slot(initial, provider_id: str):
    for p in initial.providers:
        if p.id == provider_id:
            return min(s.datetime for s in p.available_slots)
    raise ValueError(f"provider {provider_id!r} missing from initial snapshot")


def _make_appt(**kwargs) -> Appointment:
    kwargs.setdefault("type", "in-person")
    kwargs.setdefault("status", "scheduled")
    kwargs.setdefault("reason", "Critical lab follow-up")
    return Appointment(**kwargs)


def test_correct_trajectory_passes():
    sm, sid, targets, initial, state = _setup_session()
    prov_id = _ordering_provider_id(initial, targets["critical_lab_id"])
    state.appointments.append(_make_appt(
        id="appt_new_critical_followup",
        provider_id=prov_id,
        datetime=_earliest_slot(initial, prov_id),
    ))

    task = get_task("pp_urgent_lab_response")
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is True, f"failures: {report.failures}"
    assert report.score == 1.0, f"expected 1.0, got {report.score}"


def test_wrong_provider_fails():
    """Scheduling with the PCP when PCP is not the critical lab's orderer must fail."""
    sm, sid, targets, initial, state = _setup_session()
    prov_id = _ordering_provider_id(initial, targets["critical_lab_id"])
    pcp_id = targets["pcp_id"]
    # This test is only meaningful when PCP differs from the ordering provider.
    assert pcp_id != prov_id, (
        "seed produced PCP == ordering provider; pick a different seed to "
        "exercise the wrong-provider branch"
    )
    state.appointments.append(_make_appt(
        id="appt_new_wrong_prov",
        provider_id=pcp_id,
        datetime=_earliest_slot(initial, pcp_id),
    ))

    task = get_task("pp_urgent_lab_response")
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "booking with PCP (non-orderer) must fail — the `provider_id` expr "
        "pins to the critical lab's ordering provider."
    )


def test_wrong_reason_fails():
    """Appointment reason doesn't match the required exact string."""
    sm, sid, targets, initial, state = _setup_session()
    prov_id = _ordering_provider_id(initial, targets["critical_lab_id"])
    state.appointments.append(_make_appt(
        id="appt_new_wrong_reason",
        provider_id=prov_id,
        datetime=_earliest_slot(initial, prov_id),
        reason="Critical lab followup",  # close but not exact
    ))

    task = get_task("pp_urgent_lab_response")
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False


def test_not_earliest_slot_fails():
    """Correct provider + reason but using the 2nd-earliest slot must fail."""
    sm, sid, targets, initial, state = _setup_session()
    prov_id = _ordering_provider_id(initial, targets["critical_lab_id"])
    slots = sorted(
        s.datetime for p in initial.providers if p.id == prov_id for s in p.available_slots
    )
    assert len(slots) >= 2, (
        "seed must produce >=2 slots for the ordering provider for this test "
        "to be non-vacuous"
    )
    state.appointments.append(_make_appt(
        id="appt_new_later_slot",
        provider_id=prov_id,
        datetime=slots[1],  # second-earliest
    ))

    task = get_task("pp_urgent_lab_response")
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False


def test_discontinued_rx_fails():
    """Even with a correct appointment, discontinuing a medication must fail —
    prescriptions invariant is `preserve: ALL`."""
    sm, sid, targets, initial, state = _setup_session()
    prov_id = _ordering_provider_id(initial, targets["critical_lab_id"])
    state.appointments.append(_make_appt(
        id="appt_new_ok_with_bad_rx",
        provider_id=prov_id,
        datetime=_earliest_slot(initial, prov_id),
    ))
    # Mutate one active rx → discontinued (forbidden by invariant).
    active_rx_ids = list(targets["active_rx_ids"])
    assert active_rx_ids, "seed did not produce any active prescriptions"
    victim_id = active_rx_ids[0]
    for rx in state.prescriptions:
        if rx.id == victim_id:
            rx.status = "discontinued"
            break
    else:
        raise AssertionError(f"rx {victim_id!r} missing from state")

    task = get_task("pp_urgent_lab_response")
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "modifying an active prescription must fail — the prescriptions "
        "invariant is preserve:ALL."
    )


def test_no_mutation_fails():
    """Do-nothing trajectory must not pass (hazard Class 1 regression guard)."""
    sm, sid, targets, initial, state = _setup_session()
    # (no mutation)

    task = get_task("pp_urgent_lab_response")
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "do-nothing trajectory must not pass — the positive create entry "
        "has no matching candidate."
    )
    assert report.score < 1.0, f"expected score<1.0, got {report.score}"
