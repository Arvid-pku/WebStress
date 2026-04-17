"""End-to-end tests for pp_rx_cost_optimization canonical_diff.

Task: "Move your active Atorvastatin prescription to the mail-order pharmacy
already linked to your profile. Do not send any messages, do not request a
renewal, and do not modify any other prescription."

Verifies:
  - Correct trajectory (target Atorvastatin rx.pharmacy_id → mail_order_pharmacy_id)
    passes with score 1.0.
  - Wrong-rx trajectory (transfers a non-Atorvastatin rx to mail-order) fails
    via the `where` selector pinning target_rx_id AND the filtered invariant.
  - Wrong-pharmacy trajectory (Atorvastatin moved to a retail non-mail-order
    pharmacy) fails via the pharmacy_id predicate in update.changes.
  - Renewal-request trajectory (agent sets status=pending_renewal instead of
    transferring) fails because the pharmacy_id update has no matching
    candidate AND because the filtered invariant rejects the status mutation.
  - Message-sent trajectory (agent sends a new patient message) fails via
    the filtered invariant on state.messages.
  - No-mutation trajectory (agent does nothing) fails because the positive
    update entry has zero matched candidates (hazard Class 1 regression guard).
"""

from datetime import datetime, timezone

from webagentbench.backend.models.patient_portal import ClinicalMessage
from webagentbench.backend.state import SessionManager
from webagentbench.evaluator_diff import compute_diff, match_diff
from webagentbench.tasks._registry import get_task


def _setup_session(seed: int = 42):
    """Fresh session + initial snapshot + live state."""
    sm = SessionManager()
    sid, targets, _ = sm.create_session(
        env_id='patient_portal',
        task_id='pp_rx_cost_optimization',
        seed=seed,
    )
    initial = sm.get_initial_snapshot(sid)
    state = sm.get_state(sid)
    return sm, sid, dict(targets), initial, state


def _set_rx_pharmacy(state, rx_id: str, pharmacy_id: str) -> None:
    """Simulate the backend transfer route: set rx.pharmacy_id = pharmacy_id."""
    for rx in state.prescriptions:
        if rx.id == rx_id:
            rx.pharmacy_id = pharmacy_id
            return
    raise ValueError(f"prescription {rx_id!r} not found")


def _set_rx_status(state, rx_id: str, status: str) -> None:
    for rx in state.prescriptions:
        if rx.id == rx_id:
            rx.status = status
            return
    raise ValueError(f"prescription {rx_id!r} not found")


def _evaluate(targets, initial, state):
    task = get_task('pp_rx_cost_optimization')
    agent_diff = compute_diff(initial, state)
    return match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )


def test_correct_trajectory_passes():
    """Agent moves the target Atorvastatin rx.pharmacy_id to mail_order_pharmacy_id.
    Expected: score=1.0, passed=True, no failures."""
    sm, sid, targets, initial, state = _setup_session()
    _set_rx_pharmacy(state, targets["target_rx_id"], targets["mail_order_pharmacy_id"])

    report = _evaluate(targets, initial, state)
    assert report.passed is True, f"failures: {report.failures}"
    assert report.score == 1.0, f"expected 1.0, got {report.score}"


def test_wrong_rx_transferred_fails():
    """Agent transfers a different active prescription (not Atorvastatin) to
    the mail-order pharmacy. Should fail via the `where.id` predicate on the
    update (which pins target_rx_id) AND the filtered invariant on other
    prescriptions."""
    sm, sid, targets, initial, state = _setup_session()

    other = next(
        (r for r in state.prescriptions
         if r.id != targets["target_rx_id"] and r.status == "active"),
        None,
    )
    assert other is not None, "seed must produce >=1 non-target active rx for this test"
    _set_rx_pharmacy(state, other.id, targets["mail_order_pharmacy_id"])

    report = _evaluate(targets, initial, state)
    assert report.passed is False, (
        "transferring the wrong rx should fail — `where` pins target_rx_id, "
        "and the filtered invariant rejects pharmacy_id mutations on other "
        "prescriptions."
    )


def test_transferred_to_retail_fails():
    """Agent moves Atorvastatin to a non-mail-order (retail) pharmacy. Should
    fail via the pharmacy_id predicate in `update.changes`."""
    sm, sid, targets, initial, state = _setup_session()

    retail_pharm = next(
        (p for p in state.pharmacies if p.id != targets["mail_order_pharmacy_id"]),
        None,
    )
    assert retail_pharm is not None, "seed must produce >=1 non-mail-order pharmacy for this test"
    _set_rx_pharmacy(state, targets["target_rx_id"], retail_pharm.id)

    report = _evaluate(targets, initial, state)
    assert report.passed is False, (
        "transferring Atorvastatin to a retail pharmacy should fail via the "
        "pharmacy_id predicate in update.changes."
    )


def test_renewal_requested_fails():
    """Agent requests a renewal on the target rx (sets status=pending_renewal)
    instead of transferring it. Should fail because:
      (a) the positive update has no match: pharmacy_id did not change, so no
          candidate satisfies the change predicate, AND
      (b) the filtered invariant on state.prescriptions treats the target rx
          as IN scope (wait — filter is `a.id != target_rx_id`, so target rx
          is EXCLUDED from invariant). The mutation is still caught because
          the positive update has no matching candidate → score < 1.0 +
          unaccounted status-mutation on the target rx also surfaces."""
    sm, sid, targets, initial, state = _setup_session()
    _set_rx_status(state, targets["target_rx_id"], "pending_renewal")

    report = _evaluate(targets, initial, state)
    assert report.passed is False, (
        "renewal-instead-of-transfer trajectory should fail: the positive "
        "update has zero matching candidates (pharmacy_id unchanged)."
    )


def test_message_sent_fails():
    """Agent sends a new patient message (e.g. asking the pharmacy for help)
    instead of silently transferring. Should fail via the filtered invariant
    on state.messages (filter pins initial message ids)."""
    sm, sid, targets, initial, state = _setup_session()
    # Correct primary mutation still applied — so the only delta is the extra message:
    _set_rx_pharmacy(state, targets["target_rx_id"], targets["mail_order_pharmacy_id"])

    # Pick any existing provider/thread so ClinicalMessage validates.
    existing_msg = state.messages[0] if state.messages else None
    provider_id = existing_msg.provider_id if existing_msg else (
        state.providers[0].id if state.providers else "prov_1"
    )
    thread_id = existing_msg.thread_id if existing_msg else "thread_new_1"

    state.messages.append(ClinicalMessage(
        id=state._gen_id("msg"),
        from_type="patient",
        provider_id=provider_id,
        subject="Question about transfer",
        body="Please confirm the transfer.",
        thread_id=thread_id,
        timestamp=datetime.now(timezone.utc),
        is_read=False,
        category="clinical",
    ))

    report = _evaluate(targets, initial, state)
    assert report.passed is False, (
        "sending a new patient message should fail via the filtered invariant "
        "on state.messages (new message id not in initial set)."
    )


def test_no_mutation_fails():
    """Agent does nothing. Invariants trivially pass, but the positive update
    entry has zero matched candidates — score must be <1.0 and passed=False
    (hazard Class 1 regression guard)."""
    sm, sid, targets, initial, state = _setup_session()

    report = _evaluate(targets, initial, state)
    assert report.passed is False, (
        "do-nothing trajectory must not pass — the positive update entry has "
        "no matching candidate."
    )
    assert report.score < 1.0, f"expected score<1.0, got {report.score}"
