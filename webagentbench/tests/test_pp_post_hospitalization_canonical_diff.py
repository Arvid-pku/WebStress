"""End-to-end tests for pp_post_hospitalization canonical_diff.

Task: "You were recently discharged from the hospital. Complete the following
post-discharge tasks: 1) Schedule exactly one PCP follow-up appointment using
the next available PCP slot with reason 'Post-discharge PCP follow-up', 2)
Read the discharge summary message in your inbox, 3) Because the discharge
summary in this seed mentions a specialist follow-up, schedule exactly one
specialist appointment with reason 'Post-discharge specialist follow-up'.
Do not send any messages and do not modify any prescriptions."

Verifies:
  - Correct trajectory (read discharge msg + PCP create + specialist create)
    passes 1.0.
  - Only-PCP trajectory fails (missing specialist create).
  - Only-specialist trajectory fails (missing PCP create).
  - No-message-read trajectory fails (missing update).
  - Wrong-specialty specialist trajectory fails (wrong specialist provider_id).
  - Modified-prescription trajectory fails (prescription invariant).
  - Do-nothing trajectory fails with score 0.0.
"""

from webagentbench.backend.models.patient_portal import Appointment
from webagentbench.backend.state import SessionManager
from webagentbench.evaluator_diff import compute_diff, match_diff
from webagentbench.tasks._registry import get_task


def _setup_session(seed: int = 42):
    """Fresh session + initial snapshot + live state."""
    sm = SessionManager()
    sid, targets, _ = sm.create_session(
        env_id='patient_portal',
        task_id='pp_post_hospitalization',
        seed=seed,
    )
    initial = sm.get_initial_snapshot(sid)
    state = sm.get_state(sid)
    return sm, sid, dict(targets), initial, state


def _earliest_slot_for(initial, prov_id: str):
    for p in initial.providers:
        if p.id == prov_id:
            return min(s.datetime for s in p.available_slots)
    raise ValueError(f"provider {prov_id!r} not found in initial snapshot")


def _mark_message_read(state, msg_id: str) -> None:
    for m in state.messages:
        if m.id == msg_id:
            m.is_read = True
            return
    raise ValueError(f"message {msg_id!r} not found in session state")


def _make_appt(**kwargs) -> Appointment:
    kwargs.setdefault("type", "in-person")
    kwargs.setdefault("status", "scheduled")
    return Appointment(**kwargs)


def _schedule_pcp_followup(state, pcp_id: str, datetime_value, *, reason=None,
                           apt_id="appt_new_pcp_followup"):
    state.appointments.append(_make_appt(
        id=apt_id,
        provider_id=pcp_id,
        datetime=datetime_value,
        reason=reason if reason is not None else "Post-discharge PCP follow-up",
    ))


def _schedule_specialist_followup(state, prov_id: str, datetime_value, *,
                                   reason=None,
                                   apt_id="appt_new_specialist_followup"):
    state.appointments.append(_make_appt(
        id=apt_id,
        provider_id=prov_id,
        datetime=datetime_value,
        reason=reason if reason is not None else "Post-discharge specialist follow-up",
    ))


def _run(state, initial, targets):
    task = get_task('pp_post_hospitalization')
    agent_diff = compute_diff(initial, state)
    return match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )


# ────────────────────────────────────────────────────────────────────


def test_correct_trajectory_passes():
    sm, sid, targets, initial, state = _setup_session()
    pcp_id = targets["pcp_id"]
    discharge_msg_id = targets["discharge_msg_id"]
    specialist_ids = targets["discharge_specialist_provider_ids"]
    assert specialist_ids, "seed must emit at least one specialist provider id"
    specialist_id = specialist_ids[0]

    _mark_message_read(state, discharge_msg_id)
    _schedule_pcp_followup(state, pcp_id, _earliest_slot_for(initial, pcp_id))
    _schedule_specialist_followup(
        state, specialist_id, _earliest_slot_for(initial, specialist_id),
    )

    report = _run(state, initial, targets)
    assert report.passed is True, f"failures: {report.failures}"
    assert report.score == 1.0, f"expected 1.0, got {report.score}"


def test_only_pcp_apt_fails():
    """Agent scheduled PCP follow-up and marked message read but skipped the
    specialist follow-up."""
    sm, sid, targets, initial, state = _setup_session()
    pcp_id = targets["pcp_id"]

    _mark_message_read(state, targets["discharge_msg_id"])
    _schedule_pcp_followup(state, pcp_id, _earliest_slot_for(initial, pcp_id))
    # (no specialist appointment)

    report = _run(state, initial, targets)
    assert report.passed is False, "missing specialist create must fail"
    assert report.score < 1.0, f"expected score<1.0, got {report.score}"


def test_only_specialist_fails():
    """Agent scheduled the specialist follow-up and marked message read but
    skipped the PCP follow-up."""
    sm, sid, targets, initial, state = _setup_session()
    specialist_id = targets["discharge_specialist_provider_ids"][0]

    _mark_message_read(state, targets["discharge_msg_id"])
    _schedule_specialist_followup(
        state, specialist_id, _earliest_slot_for(initial, specialist_id),
    )

    report = _run(state, initial, targets)
    assert report.passed is False, "missing PCP create must fail"
    assert report.score < 1.0, f"expected score<1.0, got {report.score}"


def test_no_message_read_fails():
    """Agent scheduled both follow-ups but never read the discharge message."""
    sm, sid, targets, initial, state = _setup_session()
    pcp_id = targets["pcp_id"]
    specialist_id = targets["discharge_specialist_provider_ids"][0]

    _schedule_pcp_followup(state, pcp_id, _earliest_slot_for(initial, pcp_id))
    _schedule_specialist_followup(
        state, specialist_id, _earliest_slot_for(initial, specialist_id),
    )
    # (discharge_summary message left unread)

    report = _run(state, initial, targets)
    assert report.passed is False, "missing update on discharge message must fail"
    assert report.score < 1.0, f"expected score<1.0, got {report.score}"


def test_wrong_specialty_fails():
    """Agent booked a specialist-shaped appointment but with a provider whose
    specialty doesn't match the discharge summary (e.g. endocrinology instead
    of cardiology)."""
    sm, sid, targets, initial, state = _setup_session()
    pcp_id = targets["pcp_id"]

    _mark_message_read(state, targets["discharge_msg_id"])
    _schedule_pcp_followup(state, pcp_id, _earliest_slot_for(initial, pcp_id))
    # Find a non-PCP, non-matching-specialty provider with slots.
    allowed_ids = set(targets["discharge_specialist_provider_ids"])
    wrong_provider = next(
        p for p in initial.providers
        if p.id != pcp_id
        and p.id not in allowed_ids
        and p.specialty not in ("billing", "admin")
        and p.available_slots
    )
    _schedule_specialist_followup(
        state, wrong_provider.id,
        min(s.datetime for s in wrong_provider.available_slots),
    )

    report = _run(state, initial, targets)
    assert report.passed is False, (
        "specialist booked with wrong-specialty provider must fail create[1]"
    )


def test_modified_rx_fails():
    """Agent completed all three positive actions but also mutated an active
    prescription — must fail on the prescription invariant."""
    sm, sid, targets, initial, state = _setup_session()
    pcp_id = targets["pcp_id"]
    specialist_id = targets["discharge_specialist_provider_ids"][0]

    _mark_message_read(state, targets["discharge_msg_id"])
    _schedule_pcp_followup(state, pcp_id, _earliest_slot_for(initial, pcp_id))
    _schedule_specialist_followup(
        state, specialist_id, _earliest_slot_for(initial, specialist_id),
    )
    # Mutate an active prescription to discontinued.
    active_rx_ids = targets["active_rx_ids"]
    assert active_rx_ids, "seed must emit at least one active prescription"
    mutated = False
    for rx in state.prescriptions:
        if rx.id == active_rx_ids[0]:
            rx.status = "discontinued"
            mutated = True
            break
    assert mutated, "target active prescription not found in state"

    report = _run(state, initial, targets)
    assert report.passed is False, (
        "modified prescription must fail the state.prescriptions invariant"
    )


def test_no_mutation_fails():
    """Agent did nothing — score must be 0.0 and passed=False (Hazard Class 1
    regression guard: invariants are penalty-only, never positive weight)."""
    sm, sid, targets, initial, state = _setup_session()
    # (no mutations)

    report = _run(state, initial, targets)
    assert report.passed is False, "do-nothing trajectory must fail"
    assert report.score == 0.0, (
        f"do-nothing must earn 0.0 score (invariants are penalty-only), "
        f"got {report.score}"
    )
