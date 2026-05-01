"""End-to-end tests for pp_renew_expiring_rx canonical_diff.

Task: "Identify all prescriptions expiring within the next 30 days. For each
one that has 0 refills remaining, request a renewal. Do not request renewals
for prescriptions that still have refills available."

Verifies:
  - Correct trajectory (flip every expiring zero-refill Rx to pending_renewal
    AND create one patient->rx_renewal ClinicalMessage per such Rx) passes 1.0.
  - Wrong-rx-renewed fails (a non-zero-refill expiring rx set to
    pending_renewal violates the filtered invariant on the "still has refills"
    subset of prescriptions).
  - No-mutation fails (do-nothing trajectory has 0 positive weight).
  - No-message-sent fails (status flips without renewal messages).
  - Wrong-category fails (messages use 'clinical' instead of 'rx_renewal').
"""

from webagentbench.backend.models.patient_portal import ClinicalMessage
from webagentbench.backend.state import SessionManager
from webagentbench.eval_core import compute_diff, match_diff
from webagentbench.tasks._registry import get_task


def _setup_session(seed: int = 42):
    """Fresh session + initial snapshot + live state."""
    sm = SessionManager()
    sid, targets, _ = sm.create_session(
        env_id='patient_portal',
        task_id='pp_renew_expiring_rx',
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


def _append_renewal_message(
    state, rx_id: str, provider_id: str, *,
    category: str = "rx_renewal",
    from_type: str = "patient",
    linked_entity_id: str | None = None,
    linked_entity_type: str = "prescription",
) -> ClinicalMessage:
    msg_id = state._gen_id("msg")
    msg = ClinicalMessage(
        id=msg_id,
        from_type=from_type,
        provider_id=provider_id,
        subject="Prescription renewal request",
        body="Requesting renewal for medication.",
        thread_id=f"thread_{msg_id}",
        category=category,
        is_read=True,
        linked_entity_id=linked_entity_id if linked_entity_id is not None else rx_id,
        linked_entity_type=linked_entity_type,
    )
    state.messages.append(msg)
    return msg


def _renew(state, rx_id: str) -> None:
    """Simulate the backend renewal route: status->pending_renewal + new msg."""
    rx = _get_rx(state, rx_id)
    rx.status = "pending_renewal"
    _append_renewal_message(state, rx_id, rx.provider_id)


def test_correct_trajectory_passes():
    """Every expiring zero-refill rx flips to pending_renewal AND each gets a
    patient-authored rx_renewal ClinicalMessage linked to that rx."""
    sm, sid, targets, initial, state = _setup_session()
    assert targets["expiring_zero_refill_rx_ids"], (
        "seed must produce >=1 expiring zero-refill rx for the test to be meaningful"
    )
    for rx_id in targets["expiring_zero_refill_rx_ids"]:
        _renew(state, rx_id)

    task = get_task('pp_renew_expiring_rx')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is True, f"failures: {report.failures}"
    assert report.score == 1.0, f"expected 1.0, got {report.score}"


def test_wrong_rx_renewed_fails():
    """Agent flips an expiring rx that still has refills (refills_remaining > 0)
    to pending_renewal. The instruction forbids this; the filtered invariant
    on "prescriptions that still have refills" must surface the violation."""
    sm, sid, targets, initial, state = _setup_session()

    # Find an expiring rx NOT in the zero-refill expiring subset (i.e. one
    # that still has refills — the instruction says NOT to renew these).
    wrong_id = next(
        (rid for rid in targets["expiring_rx_ids"]
         if rid not in targets["expiring_zero_refill_rx_ids"]),
        None,
    )
    assert wrong_id is not None, (
        "seed must produce >=1 expiring rx with refills remaining to exercise "
        "the negative-case invariant. Check seed params."
    )

    # Simulate the wrong action: renew the refill-having rx instead.
    _renew(state, wrong_id)
    # Also do the correct renewals so the positive pool is saturated and the
    # only failure is the invariant violation.
    for rx_id in targets["expiring_zero_refill_rx_ids"]:
        _renew(state, rx_id)

    task = get_task('pp_renew_expiring_rx')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "renewing a rx with refills remaining must fail the filtered "
        "invariant on state.prescriptions (a.id not in expiring_zero_refill_rx_ids)."
    )


def test_no_mutation_fails():
    """Agent does nothing. Positive pool empty -> passed=False (Class 1 guard)."""
    sm, sid, targets, initial, state = _setup_session()

    task = get_task('pp_renew_expiring_rx')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "do-nothing trajectory must not pass — neither update nor create "
        "bijection has any matching candidate."
    )
    assert report.score < 1.0, f"expected <1.0, got {report.score}"


def test_no_message_sent_fails():
    """Status flipped on all expiring zero-refill rxes but no renewal messages
    created — create[0] bijection unsaturated."""
    sm, sid, targets, initial, state = _setup_session()
    for rx_id in targets["expiring_zero_refill_rx_ids"]:
        _get_rx(state, rx_id).status = "pending_renewal"

    task = get_task('pp_renew_expiring_rx')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "status flip alone must not pass — the create bijection for renewal "
        "messages has no candidates."
    )
    assert report.score < 1.0, f"expected <1.0, got {report.score}"


def test_wrong_category_fails():
    """Status flipped + patient messages created, but category is 'clinical'
    instead of 'rx_renewal' — create[0] must reject those candidates."""
    sm, sid, targets, initial, state = _setup_session()
    for rx_id in targets["expiring_zero_refill_rx_ids"]:
        rx = _get_rx(state, rx_id)
        rx.status = "pending_renewal"
        _append_renewal_message(state, rx.id, rx.provider_id, category="clinical")

    task = get_task('pp_renew_expiring_rx')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "misrouted message (category != 'rx_renewal') must fail — category is "
        "the structural signal that the renewal reached the RX system."
    )
