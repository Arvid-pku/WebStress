"""End-to-end tests for pp_transfer_prescription canonical_diff.

Task: "Transfer your Metformin prescription from its current pharmacy to
the Walgreens pharmacy already in your pharmacy list."

Verifies:
  - Correct trajectory (target Metformin rx's pharmacy_id → Walgreens pharm_id)
    passes with score 1.0.
  - Wrong-rx trajectory (transfers a non-Metformin rx to Walgreens) fails
    via the filtered invariant on other prescriptions AND the `where` selector
    pinning the Metformin rx id.
  - Wrong-pharmacy trajectory (Metformin moved to a non-Walgreens pharmacy)
    fails via the `pharmacy_id` predicate on the update entry.
  - No-mutation trajectory (agent does nothing) fails because the positive
    update entry has no matched candidate (hazard Class 1 regression guard).
"""

from webagentbench.backend.state import SessionManager
from webagentbench.eval_core import compute_diff, match_diff
from webagentbench.tasks._registry import get_task


def _setup_session(seed: int = 42):
    """Fresh session + initial snapshot + live state."""
    sm = SessionManager()
    sid, targets, _ = sm.create_session(
        env_id='patient_portal',
        task_id='pp_transfer_prescription',
        seed=seed,
    )
    initial = sm.get_initial_snapshot(sid)
    state = sm.get_state(sid)
    return sm, sid, dict(targets), initial, state


def _transfer(state, rx_id: str, pharmacy_id: str) -> None:
    """Simulate the backend transfer route: set rx.pharmacy_id = pharmacy_id."""
    for rx in state.prescriptions:
        if rx.id == rx_id:
            rx.pharmacy_id = pharmacy_id
            return
    raise ValueError(f"prescription {rx_id!r} not found")


def test_correct_trajectory_passes():
    sm, sid, targets, initial, state = _setup_session()
    _transfer(state, targets["target_rx_id"], targets["target_pharmacy_id"])

    task = get_task('pp_transfer_prescription')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is True, f"failures: {report.failures}"
    assert report.score == 1.0, f"expected 1.0, got {report.score}"


def test_wrong_rx_transferred_fails():
    """Agent transfers a NON-Metformin prescription to Walgreens — should fail
    via the filtered invariant on other prescriptions AND the `where` selector
    on the update (which requires id == target_rx_id)."""
    sm, sid, targets, initial, state = _setup_session()

    other = next(
        (r for r in state.prescriptions
         if r.id != targets["target_rx_id"] and r.status == "active"),
        None,
    )
    assert other is not None, "seed must produce >=1 non-target active rx for this test"
    _transfer(state, other.id, targets["target_pharmacy_id"])

    task = get_task('pp_transfer_prescription')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "transferring the wrong rx should fail — the `where` selector pins "
        "target_rx_id (the Metformin rx) and the filtered invariant rejects "
        "pharmacy mutations on other prescriptions."
    )


def test_transferred_to_wrong_pharmacy_fails():
    """Agent moves Metformin to a pharmacy that is NOT Walgreens — should fail
    via the pharmacy_id predicate in the `update.changes` block."""
    sm, sid, targets, initial, state = _setup_session()

    wrong_pharm = next(
        (p for p in state.pharmacies if p.id != targets["target_pharmacy_id"]),
        None,
    )
    assert wrong_pharm is not None, "seed must produce >=2 pharmacies for this test"
    _transfer(state, targets["target_rx_id"], wrong_pharm.id)

    task = get_task('pp_transfer_prescription')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "transferring Metformin to a non-Walgreens pharmacy should fail via "
        "the pharmacy_id predicate in update.changes."
    )


def test_no_mutation_fails():
    """Agent does nothing. Invariants trivially pass, but the positive `update`
    entry has zero matched candidates — score should be <1.0 on the positive
    pool and passed=False (hazard Class 1 regression guard)."""
    sm, sid, targets, initial, state = _setup_session()

    task = get_task('pp_transfer_prescription')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "do-nothing trajectory must not pass — the positive update entry has "
        "no matching candidate."
    )
    assert report.score < 1.0, f"expected score<1.0, got {report.score}"
