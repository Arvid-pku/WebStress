"""End-to-end tests for pp_complex_claim_dispute canonical_diff.

Task: "Three insurance claims were denied and each has an available EOB.
Review the denied claims and appeal all three of them using the claim
appeal action. Do not send any messages and do not modify any approved
claims."

Verifies:
  - Correct trajectory (status='appealed' on all 3 denied claims) passes.
  - Appealing only 2 of the 3 denied claims -> bijection under-saturates, fails.
  - Appealing 4 claims (3 denied + 1 approved) -> invariant violation, fails.
  - Modifying an approved claim instead of appealing denied -> fails.
  - Do-nothing trajectory fails (hazard Class 1 guard).
"""

from webagentbench.backend.state import SessionManager
from webagentbench.eval_core import compute_diff, match_diff
from webagentbench.tasks._registry import get_task


def _setup_session(seed: int = 42):
    """Fresh session + initial snapshot + live state."""
    sm = SessionManager()
    sid, targets, _ = sm.create_session(
        env_id='patient_portal',
        task_id='pp_complex_claim_dispute',
        seed=seed,
    )
    initial = sm.get_initial_snapshot(sid)
    state = sm.get_state(sid)
    return sm, sid, dict(targets), initial, state


def _appeal_claim(state, clm_id: str) -> None:
    """Simulate the backend appeal route: set status='appealed'."""
    for c in state.claims:
        if c.id == clm_id:
            c.status = "appealed"
            return
    raise ValueError(f"claim {clm_id!r} not found in session state")


def test_correct_trajectory_passes():
    """Appeal all three denied claims -> bijection saturates, invariants hold."""
    sm, sid, targets, initial, state = _setup_session()
    denied = targets["denied_claim_ids"]
    assert len(denied) == 3, f"seed must produce 3 denied claims, got {denied!r}"
    for cid in denied:
        _appeal_claim(state, cid)

    task = get_task('pp_complex_claim_dispute')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is True, f"failures: {report.failures}"
    assert report.score == 1.0, f"expected 1.0, got {report.score}"


def test_partial_fails():
    """Appeal only 2 of the 3 denied claims -> bijection under-saturates."""
    sm, sid, targets, initial, state = _setup_session()
    denied = targets["denied_claim_ids"]
    for cid in denied[:2]:
        _appeal_claim(state, cid)

    task = get_task('pp_complex_claim_dispute')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "appealing only 2 of 3 denied claims must fail — bijection over "
        "denied_claim_ids only saturates at 3."
    )
    assert report.score < 1.0, f"expected score<1.0, got {report.score}"


def test_approved_claim_appealed_fails():
    """Appeal all 3 denied AND one approved claim -> invariant violation."""
    sm, sid, targets, initial, state = _setup_session()
    approved_ids = targets.get("approved_claim_ids") or []
    assert approved_ids, "seed must produce >=1 approved claim for this test"
    for cid in targets["denied_claim_ids"]:
        _appeal_claim(state, cid)
    # Illegally mutate an approved claim
    for c in state.claims:
        if c.id == approved_ids[0]:
            c.status = "appealed"
            break

    task = get_task('pp_complex_claim_dispute')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "modifying an approved claim must fail — the `a.id not in "
        "target['denied_claim_ids']` invariant preserves every non-target claim."
    )


def test_wrong_status_fails():
    """Set the denied claim's status to something other than 'appealed'
    -> bijection `changes.status == appealed` predicate rejects it."""
    sm, sid, targets, initial, state = _setup_session()
    denied = targets["denied_claim_ids"]
    # Appeal 2 correctly, but give the 3rd a wrong status
    for cid in denied[:2]:
        _appeal_claim(state, cid)
    for c in state.claims:
        if c.id == denied[2]:
            c.status = "approved"  # wrong target status
            break

    task = get_task('pp_complex_claim_dispute')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "wrong terminal status on a denied claim must fail — the bijection "
        "under-saturates (only 2 of 3 match `status == appealed`)."
    )
    assert report.score < 1.0, f"expected score<1.0, got {report.score}"


def test_extra_message_fails():
    """Appeal all 3 denied claims AND send a patient message -> invariant
    violation on state.messages."""
    from webagentbench.backend.models.patient_portal import ClinicalMessage
    from datetime import datetime, timezone
    sm, sid, targets, initial, state = _setup_session()
    for cid in targets["denied_claim_ids"]:
        _appeal_claim(state, cid)
    # Append an unsolicited patient message
    state.messages.append(ClinicalMessage(
        id="msg_extra_1",
        from_type="patient",
        provider_id=targets["pcp_id"],
        subject="Unsolicited",
        body="Hi",
        thread_id="thread_extra_1",
        timestamp=datetime.now(timezone.utc),
    ))

    task = get_task('pp_complex_claim_dispute')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "sending an unsolicited message must fail — state.messages has a "
        "preserve: ALL invariant."
    )


def test_no_mutation_fails():
    """Do-nothing trajectory: bijection has 3 slots, 0 candidates — must
    fail with score<1.0 (hazard Class 1 regression guard)."""
    sm, sid, targets, initial, state = _setup_session()

    task = get_task('pp_complex_claim_dispute')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "do-nothing trajectory must not pass — the positive update entry has "
        "0 of 3 matched candidates."
    )
    assert report.score < 1.0, f"expected score<1.0, got {report.score}"
