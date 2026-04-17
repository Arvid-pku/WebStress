"""End-to-end tests for pp_file_claim_appeal canonical_diff.

Task: "File an appeal for your denied insurance claim that has an available
EOB. Reference the approved referral and the original appointment as
supporting evidence in your appeal."

Verifies:
  - Correct trajectory (set the appealable claim's status to 'appealed')
    passes, score 1.0.
  - Appealing a different denied claim fails (identity test — target is
    the specific appealable_claim_id scalar).
  - Appealing an approved claim fails (approved claims must not be
    appealed; they remain 'approved').
  - Do-nothing trajectory fails (Class 1 regression guard).
"""

from webagentbench.backend.state import SessionManager
from webagentbench.evaluator_diff import compute_diff, match_diff
from webagentbench.tasks._registry import get_task


def _setup_session(seed: int = 42):
    """Fresh session + initial snapshot + live state."""
    sm = SessionManager()
    sid, targets, _ = sm.create_session(
        env_id='patient_portal',
        task_id='pp_file_claim_appeal',
        seed=seed,
    )
    initial = sm.get_initial_snapshot(sid)
    state = sm.get_state(sid)
    return sm, sid, dict(targets), initial, state


def _appeal_claim(state, clm_id: str) -> None:
    """Simulate the backend appeal route: set status → 'appealed'."""
    for c in state.claims:
        if c.id == clm_id:
            c.status = "appealed"
            return
    raise ValueError(f"claim {clm_id!r} not found in session state")


def test_correct_trajectory_passes():
    """Agent appeals the specific appealable_claim_id target."""
    sm, sid, targets, initial, state = _setup_session()
    target_id = targets["appealable_claim_id"]
    assert target_id is not None, (
        "seed must set appealable_claim_id (near_appeal_deadline=true)"
    )
    _appeal_claim(state, target_id)

    task = get_task('pp_file_claim_appeal')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is True, f"failures: {report.failures}"
    assert report.score == 1.0, f"expected 1.0, got {report.score}"


def test_wrong_claim_appealed_fails():
    """Agent appeals a different denied claim (not appealable_claim_id)."""
    sm, sid, targets, initial, state = _setup_session()
    target_id = targets["appealable_claim_id"]
    denied_ids = targets.get("denied_claim_ids") or []
    other_denied = next(
        (cid for cid in denied_ids if cid != target_id),
        None,
    )
    assert other_denied is not None, (
        "seed must produce >=2 denied claims so this identity test is "
        "non-vacuous (hazard Class 4)"
    )
    _appeal_claim(state, other_denied)

    task = get_task('pp_file_claim_appeal')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "appealing a non-target denied claim must fail — the `where` "
        "selector matches only appealable_claim_id, and the invariant "
        "on state.claims rejects mutations on other claims."
    )


def test_approved_claim_appealed_fails():
    """Agent appeals an approved claim instead of the denied one."""
    sm, sid, targets, initial, state = _setup_session()
    approved_ids = targets.get("approved_claim_ids") or []
    assert approved_ids, "seed must produce >=1 approved claim for this test"
    _appeal_claim(state, approved_ids[0])

    task = get_task('pp_file_claim_appeal')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "appealing an approved claim must fail — target is the "
        "appealable denied claim, and the invariant sweep rejects "
        "mutations on non-target claims."
    )


def test_no_mutation_fails():
    """Agent does nothing. Positive update has zero matched candidates,
    so score must be < 1.0 and passed=False (hazard Class 1 regression guard)."""
    sm, sid, targets, initial, state = _setup_session()

    task = get_task('pp_file_claim_appeal')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "do-nothing trajectory must not pass — the positive update entry "
        "has no matching candidate."
    )
    assert report.score < 1.0, f"expected score<1.0, got {report.score}"
