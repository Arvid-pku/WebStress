"""End-to-end tests for pp_medication_reconciliation canonical_diff.

Task: "After a hospitalization, reconcile your medication list without
composing any free-form messages: 1) Read the discharge summary message in
your inbox, 2) Find the medication explicitly noted in the summary as
'discontinued during hospitalization', 3) For each active prescription
named in that note, use the prescription renewal request flow so it moves
to pending renewal, 4) Schedule exactly one PCP appointment with reason
'Post-discharge medication reconciliation'. Do not directly discontinue
prescriptions yourself and do not send any separate clinical messages."

Verifies:
  - Correct trajectory (read discharge, flip discontinued rx to
    pending_renewal via rx_renewal message, schedule PCP appt) passes 1.0.
  - Missing message-read fails the ClinicalMessage update.
  - Missing rx status flip fails the Prescription bijection update.
  - Missing PCP appointment fails the Appointment create.
  - Direct discontinuation (status=discontinued on active rx the note
    did NOT flag) fails the filtered prescription invariant.
  - Extra patient-authored clinical message is surfaced by the matcher.
  - Do-nothing trajectory must fail with score 0.0 (Hazard Class 1).
"""

from datetime import datetime, timezone, timedelta

from webagentbench.backend.models.patient_portal import (
    Appointment,
    ClinicalMessage,
)
from webagentbench.backend.state import SessionManager
from webagentbench.evaluator_diff import compute_diff, match_diff
from webagentbench.tasks._registry import get_task


def _setup_session(seed: int = 42):
    """Fresh session + initial snapshot + live state."""
    sm = SessionManager()
    sid, targets, _ = sm.create_session(
        env_id="patient_portal",
        task_id="pp_medication_reconciliation",
        seed=seed,
    )
    initial = sm.get_initial_snapshot(sid)
    state = sm.get_state(sid)
    return sm, sid, dict(targets), initial, state


def _get_rx(state, rx_id: str):
    for r in state.prescriptions:
        if r.id == rx_id:
            return r
    raise ValueError(f"rx {rx_id!r} not found")


def _mark_message_read(state, msg_id: str) -> None:
    for m in state.messages:
        if m.id == msg_id:
            m.is_read = True
            return
    raise ValueError(f"message {msg_id!r} not found")


def _append_renewal_message(
    state,
    rx_id: str,
    provider_id: str,
    *,
    category: str = "rx_renewal",
) -> ClinicalMessage:
    msg_id = state._gen_id("msg")
    msg = ClinicalMessage(
        id=msg_id,
        from_type="patient",
        provider_id=provider_id,
        subject="Prescription renewal request",
        body="Requesting renewal for discontinued medication.",
        thread_id=f"thread_{msg_id}",
        category=category,
        is_read=True,
        linked_entity_id=rx_id,
        linked_entity_type="prescription",
    )
    state.messages.append(msg)
    return msg


def _renew(state, rx_id: str) -> None:
    """Simulate the renewal route: status->pending_renewal + rx_renewal msg."""
    rx = _get_rx(state, rx_id)
    rx.status = "pending_renewal"
    _append_renewal_message(state, rx.id, rx.provider_id)


def _schedule_pcp_appt(
    state,
    pcp_id: str,
    *,
    reason: str | None = None,
    apt_id: str = "appt_new_med_reconcile",
) -> Appointment:
    apt = Appointment(
        id=apt_id,
        provider_id=pcp_id,
        datetime=datetime.now(timezone.utc) + timedelta(days=3),
        type="in-person",
        status="scheduled",
        reason=reason if reason is not None else "Post-discharge medication reconciliation",
    )
    state.appointments.append(apt)
    return apt


def _run(state, initial, targets):
    task = get_task("pp_medication_reconciliation")
    agent_diff = compute_diff(initial, state)
    return match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )


# ────────────────────────────────────────────────────────────────────


def test_correct_trajectory_passes():
    """Discharge message read, every discontinued rx flipped to
    pending_renewal (with matching rx_renewal message), PCP med-reconcile
    appointment scheduled."""
    sm, sid, targets, initial, state = _setup_session()
    assert targets["discontinued_rx_ids"], (
        "seed must emit >=1 discontinued rx for the test to be meaningful"
    )
    _mark_message_read(state, targets["discharge_msg_id"])
    for rx_id in targets["discontinued_rx_ids"]:
        _renew(state, rx_id)
    _schedule_pcp_appt(state, targets["pcp_id"])

    report = _run(state, initial, targets)
    assert report.passed is True, f"failures: {report.failures}"
    assert report.score == 1.0, f"expected 1.0, got {report.score}"


def test_no_message_read_fails():
    """Rx flipped + appt scheduled, but the discharge message was never
    marked read — update[0] (ClinicalMessage is_read) has no candidate."""
    sm, sid, targets, initial, state = _setup_session()
    for rx_id in targets["discontinued_rx_ids"]:
        _renew(state, rx_id)
    _schedule_pcp_appt(state, targets["pcp_id"])

    report = _run(state, initial, targets)
    assert report.passed is False, (
        "missing discharge-message read must fail update[0]"
    )
    assert report.score < 1.0, f"expected <1.0, got {report.score}"


def test_no_rx_flip_fails():
    """Discharge read + renewal message sent + appt scheduled, but rx
    status was never flipped — update[1] bijection has no candidate."""
    sm, sid, targets, initial, state = _setup_session()
    _mark_message_read(state, targets["discharge_msg_id"])
    for rx_id in targets["discontinued_rx_ids"]:
        rx = _get_rx(state, rx_id)
        _append_renewal_message(state, rx.id, rx.provider_id)
    _schedule_pcp_appt(state, targets["pcp_id"])

    report = _run(state, initial, targets)
    assert report.passed is False, (
        "missing rx status flip must fail update[1] bijection"
    )
    assert report.score < 1.0, f"expected <1.0, got {report.score}"


def test_no_pcp_appt_fails():
    """Discharge read + rx renewed, but no PCP appointment scheduled —
    create[1] (Appointment) has no candidate."""
    sm, sid, targets, initial, state = _setup_session()
    _mark_message_read(state, targets["discharge_msg_id"])
    for rx_id in targets["discontinued_rx_ids"]:
        _renew(state, rx_id)

    report = _run(state, initial, targets)
    assert report.passed is False, (
        "missing PCP appointment must fail create[1]"
    )
    assert report.score < 1.0, f"expected <1.0, got {report.score}"


def test_direct_discontinuation_fails():
    """Agent directly discontinued a prescription that was NOT named in
    the discharge note — must fail the filtered prescription invariant
    ('a.id not in target[discontinued_rx_ids]')."""
    sm, sid, targets, initial, state = _setup_session()
    _mark_message_read(state, targets["discharge_msg_id"])
    for rx_id in targets["discontinued_rx_ids"]:
        _renew(state, rx_id)
    _schedule_pcp_appt(state, targets["pcp_id"])
    wrong_rx_id = next(
        (rid for rid in targets["active_rx_ids"]
         if rid not in targets["discontinued_rx_ids"]),
        None,
    )
    assert wrong_rx_id is not None, (
        "seed must emit >=1 active rx not flagged as discontinued"
    )
    _get_rx(state, wrong_rx_id).status = "discontinued"

    report = _run(state, initial, targets)
    assert report.passed is False, (
        "direct discontinuation of a non-flagged rx must fail the filtered "
        "prescription invariant"
    )


def test_no_mutation_fails():
    """Do-nothing trajectory must fail with score 0.0 (invariants are
    penalty-only; Hazard Class 1 regression guard)."""
    sm, sid, targets, initial, state = _setup_session()

    report = _run(state, initial, targets)
    assert report.passed is False, "do-nothing trajectory must fail"
    assert report.score == 0.0, (
        f"do-nothing must earn 0.0 score (invariants are penalty-only), "
        f"got {report.score}"
    )
