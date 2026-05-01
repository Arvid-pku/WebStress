"""End-to-end tests for pp_medication_conflict canonical_diff.

Task: identify the interacting rx pair, then schedule exactly one appointment
with the prescribing provider of the *newer* rx (max by last_filled) at that
provider's next available slot, with reason "Interaction review". Do not
discontinue any prescription or send any message.

Trajectories covered:
- correct (newer-rx provider, earliest slot, exact reason) → passes 1.0
- wrong_provider (scheduled with other interacting rx's provider) → fails
- wrong_provider_pcp (scheduled with PCP instead) → fails
- not_earliest_slot (correct provider, second-earliest slot) → fails
- discontinued_medication (correct appt + discontinued interacting rx) → fails
- no_mutation (empty trajectory) → fails (score 0.0)
"""

from webagentbench.backend.models.patient_portal import Appointment
from webagentbench.backend.state import SessionManager
from webagentbench.eval_core import compute_diff, match_diff
from webagentbench.tasks._registry import get_task


def _setup_session(seed: int = 42):
    sm = SessionManager()
    sid, targets, _ = sm.create_session(
        env_id="patient_portal",
        task_id="pp_medication_conflict",
        seed=seed,
    )
    initial = sm.get_initial_snapshot(sid)
    state = sm.get_state(sid)
    return sm, sid, dict(targets), initial, state


def _newer_rx_provider(initial, targets) -> str:
    """Return provider_id of the newer (max last_filled) interacting rx."""
    rx_ids = targets["interacting_rx_ids"]
    newer_rid = max(
        rx_ids,
        key=lambda rid: (initial.get_prescription(rid).last_filled, rid),
    )
    return initial.get_prescription(newer_rid).provider_id


def _older_rx_provider(initial, targets) -> str:
    """Return provider_id of the older (min last_filled) interacting rx."""
    rx_ids = targets["interacting_rx_ids"]
    older_rid = min(
        rx_ids,
        key=lambda rid: (initial.get_prescription(rid).last_filled, rid),
    )
    return initial.get_prescription(older_rid).provider_id


def _earliest_slot(initial, provider_id: str):
    for p in initial.providers:
        if p.id == provider_id:
            return min(s.datetime for s in p.available_slots)
    raise ValueError(f"provider {provider_id!r} missing from initial snapshot")


def _make_appt(**kwargs) -> Appointment:
    kwargs.setdefault("type", "in-person")
    kwargs.setdefault("status", "scheduled")
    kwargs.setdefault("reason", "Interaction review")
    return Appointment(**kwargs)


def test_correct_trajectory_passes():
    sm, sid, targets, initial, state = _setup_session()
    prov_id = _newer_rx_provider(initial, targets)
    state.appointments.append(_make_appt(
        id="appt_new_interaction",
        provider_id=prov_id,
        datetime=_earliest_slot(initial, prov_id),
    ))

    task = get_task("pp_medication_conflict")
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is True, f"failures: {report.failures}"
    assert report.score == 1.0, f"expected 1.0, got {report.score}"


def test_wrong_provider_fails():
    """Agent scheduled with the OTHER interacting rx's prescribing provider."""
    sm, sid, targets, initial, state = _setup_session()
    prov_id = _older_rx_provider(initial, targets)
    newer_prov = _newer_rx_provider(initial, targets)
    # Only meaningful if the two interacting rxes actually have distinct providers.
    if prov_id == newer_prov:
        # Fall back to any other provider that isn't the newer one.
        alt = next(
            (p for p in state.providers if p.id != newer_prov and p.available_slots),
            None,
        )
        assert alt is not None, "seed lacks a non-newer-rx provider"
        prov_id = alt.id
    state.appointments.append(_make_appt(
        id="appt_new_wrong_prov",
        provider_id=prov_id,
        datetime=_earliest_slot(initial, prov_id),
    ))

    task = get_task("pp_medication_conflict")
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False


def test_wrong_provider_pcp_fails():
    """Agent defaulted to the PCP instead of the newer rx's prescriber."""
    sm, sid, targets, initial, state = _setup_session()
    pcp_id = targets["pcp_id"]
    newer_prov = _newer_rx_provider(initial, targets)
    # If the PCP happens to be the newer-rx provider on this seed, this test
    # degenerates — pick a different non-newer-rx provider instead.
    if pcp_id == newer_prov:
        alt = next(
            (p for p in state.providers if p.id != newer_prov and p.available_slots),
            None,
        )
        assert alt is not None, "seed lacks a non-newer-rx provider"
        pcp_id = alt.id
    state.appointments.append(_make_appt(
        id="appt_new_wrong_pcp",
        provider_id=pcp_id,
        datetime=_earliest_slot(initial, pcp_id),
    ))

    task = get_task("pp_medication_conflict")
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False


def test_not_earliest_slot_fails():
    """Correct provider but scheduled at second-earliest slot."""
    sm, sid, targets, initial, state = _setup_session()
    prov_id = _newer_rx_provider(initial, targets)
    slots = sorted(
        s.datetime
        for p in initial.providers if p.id == prov_id
        for s in p.available_slots
    )
    assert len(slots) >= 2, "seed must produce >=2 slots for this provider"
    state.appointments.append(_make_appt(
        id="appt_new_later_slot",
        provider_id=prov_id,
        datetime=slots[1],
    ))

    task = get_task("pp_medication_conflict")
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False


def test_discontinued_medication_fails():
    """Agent correctly booked the appointment but discontinued one interacting rx."""
    sm, sid, targets, initial, state = _setup_session()
    prov_id = _newer_rx_provider(initial, targets)
    state.appointments.append(_make_appt(
        id="appt_new_interaction",
        provider_id=prov_id,
        datetime=_earliest_slot(initial, prov_id),
    ))
    # Discontinue one of the interacting rxes — violates prescription invariant.
    rid = targets["interacting_rx_ids"][0]
    for rx in state.prescriptions:
        if rx.id == rid:
            rx.status = "discontinued"
            break

    task = get_task("pp_medication_conflict")
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False


def test_no_mutation_fails():
    """Agent did nothing — create entry unsatisfied, score 0.0, not passed."""
    sm, sid, targets, initial, state = _setup_session()

    task = get_task("pp_medication_conflict")
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False
    assert report.score == 0.0, f"expected 0.0 (no-op), got {report.score}"
