"""End-to-end tests for pp_review_eob canonical_diff.

Task: "Review the EOB for your most recent approved claim. If patient
responsibility <= $200, pay that exact claim. If > $200, leave all
claims unpaid. Do not send any messages."

This is a BRANCHING task modelled as `canonical_diff.oneof`:
  - Branch A — pay if recent_resp <= $200 (update entry requires resp<=200)
  - Branch B — do nothing if recent_resp > $200 (constraint asserts resp>200)

Each branch embeds its applicability condition so the wrong branch cannot
silently win on a given seed.

Seed behaviour probed for this task:
  seed=42  → recent_resp=$724.74  → SKIP branch (B)
  seed=2   → recent_resp=$39.58   → PAY branch (A)
  seed=200 → recent_resp=$165.29  → PAY branch (A)
"""

from decimal import Decimal

from webagentbench.backend.state import SessionManager
from webagentbench.evaluator_diff import compute_diff, match_diff
from webagentbench.tasks._registry import get_task


# Seed curators — stable across minor seed_builder refactors because the
# responsibility gap is large at these seeds.
_SKIP_SEED = 42    # recent_resp > $200 — correct action: do nothing
_PAY_SEED = 2      # recent_resp <= $200 — correct action: pay the claim


def _setup_session(seed: int):
    sm = SessionManager()
    sid, targets, _ = sm.create_session(
        env_id='patient_portal',
        task_id='pp_review_eob',
        seed=seed,
    )
    initial = sm.get_initial_snapshot(sid)
    state = sm.get_state(sid)
    return sm, sid, dict(targets), initial, state


def _most_recent_approved(initial, targets) -> str:
    """Replicate the canonical selector: max by (service_date, cid)."""
    return max(
        targets['approved_claim_ids'],
        key=lambda cid: (initial.get_claim(cid).service_date, cid),
    )


def _pay_claim(state, clm_id: str) -> None:
    for c in state.claims:
        if c.id == clm_id:
            c.patient_responsibility = Decimal("0")
            return
    raise ValueError(f"claim {clm_id!r} not found")


# ---------------------------------------------------------------------
# Seed sanity — keep the branch assumption intact. If a seed_builder
# refactor flips the branch at a curated seed, these assertions catch
# it and the curated list above should be updated.
# ---------------------------------------------------------------------

def test_curated_seeds_cover_both_branches():
    _, _, targets_skip, initial_skip, _ = _setup_session(_SKIP_SEED)
    recent_skip = _most_recent_approved(initial_skip, targets_skip)
    resp_skip = float(initial_skip.get_claim(recent_skip).patient_responsibility)
    assert resp_skip > 200, (
        f"_SKIP_SEED={_SKIP_SEED} was supposed to put recent_resp > 200, "
        f"got ${resp_skip}. Update the curated-seed list."
    )

    _, _, targets_pay, initial_pay, _ = _setup_session(_PAY_SEED)
    recent_pay = _most_recent_approved(initial_pay, targets_pay)
    resp_pay = float(initial_pay.get_claim(recent_pay).patient_responsibility)
    assert resp_pay <= 200, (
        f"_PAY_SEED={_PAY_SEED} was supposed to put recent_resp <= 200, "
        f"got ${resp_pay}. Update the curated-seed list."
    )


# ---------------------------------------------------------------------
# Correct trajectories — one per branch.
# ---------------------------------------------------------------------

def test_correct_trajectory_pay_branch_passes():
    """PAY seed (resp <= $200): agent pays the most-recent approved claim."""
    _, _, targets, initial, state = _setup_session(_PAY_SEED)
    target_id = _most_recent_approved(initial, targets)
    _pay_claim(state, target_id)

    task = get_task('pp_review_eob')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is True, f"failures: {report.failures}"
    assert report.score == 1.0, f"expected 1.0, got {report.score}"


def test_correct_trajectory_skip_branch_passes():
    """SKIP seed (resp > $200): agent correctly does nothing."""
    _, _, targets, initial, state = _setup_session(_SKIP_SEED)

    task = get_task('pp_review_eob')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is True, f"failures: {report.failures}"
    assert report.score == 1.0, f"expected 1.0, got {report.score}"


# Alias required by the validate.py stage-4 probe (which pattern-matches
# this common test name across migrated tasks).
def test_correct_trajectory_passes():
    """Stage-4 entry point — delegate to the SKIP branch (seed=42 default)."""
    test_correct_trajectory_skip_branch_passes()


# ---------------------------------------------------------------------
# Wrong-branch-action tests.
# ---------------------------------------------------------------------

def test_paid_when_over_200_fails():
    """SKIP seed (resp > $200) but agent pays anyway — both branches fail.

    Branch A: selector requires resp<=200, so zero matching candidates;
              the agent's update becomes collateral on state.claims.
    Branch B: the invariant on state.claims fires.
    """
    _, _, targets, initial, state = _setup_session(_SKIP_SEED)
    target_id = _most_recent_approved(initial, targets)
    _pay_claim(state, target_id)

    task = get_task('pp_review_eob')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "paying a claim with responsibility > $200 must fail — the "
        "instruction says to leave all claims unpaid in that branch."
    )


def test_not_paid_when_under_200_fails():
    """PAY seed (resp <= $200) but agent does nothing — both branches fail.

    Branch A: update has no matching candidate (agent didn't touch claim).
    Branch B: constraint 'resp > 200' fails (resp was <= 200).
    """
    _, _, targets, initial, state = _setup_session(_PAY_SEED)

    task = get_task('pp_review_eob')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "leaving a <= $200 claim unpaid must fail — the instruction "
        "requires paying that exact claim in that branch."
    )
    assert report.score < 1.0, f"expected score<1.0, got {report.score}"


def test_paid_wrong_claim_fails():
    """PAY seed: agent pays a NON-most-recent approved claim.

    Branch A selector picks the most-recent-by-service_date-with-cid-tiebreaker;
    paying the older approved claim must not saturate the update.
    """
    _, _, targets, initial, state = _setup_session(_PAY_SEED)
    recent_id = _most_recent_approved(initial, targets)
    older_id = next(
        (cid for cid in targets['approved_claim_ids'] if cid != recent_id),
        None,
    )
    assert older_id is not None, (
        "PAY seed must produce >=2 approved claims for the identity test "
        "to be non-vacuous (hazard Class 4)."
    )
    _pay_claim(state, older_id)

    task = get_task('pp_review_eob')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "paying the older approved claim must fail — the selector picks "
        "only the most-recent approved claim, and branch B's invariant "
        "on state.claims fires on any claim mutation."
    )


def test_message_sent_fails():
    """Do-nothing trajectory is correct for the SKIP seed — but if the agent
    sends a patient message as a side-effect, the invariant on state.messages
    fires in both branches."""
    from webagentbench.backend.models.patient_portal import ClinicalMessage

    _, _, targets, initial, state = _setup_session(_SKIP_SEED)
    state.messages.append(ClinicalMessage(
        id="msg_agent_side_effect",
        from_type="patient",
        provider_id=state.providers[0].id if state.providers else "prov_1",
        subject="Question about EOB",
        body="Why is my responsibility so high?",
        thread_id="thread_test",
    ))

    task = get_task('pp_review_eob')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "sending a patient message must fail — the task explicitly says "
        "'Do not send any messages' and invariant on state.messages catches it."
    )
