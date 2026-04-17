"""End-to-end tests for pp_full_referral_chain canonical_diff.

Task: verify PCP neurology referral is approved, confirm pre-authorization is
in place, then schedule a neurology appointment. The 'verify' and 'confirm'
parts are read-only; the only state-changing step is scheduling one neurology
appointment. The canonical_diff therefore asserts a single Appointment create
with a neurology provider + approved-neurology referral, plus invariants that
forbid mutating referrals (captures the 'did not modify referral status'
signal).

Trajectories covered:
- correct (neurology provider + approved neuro referral)        -> passes 1.0
- wrong-specialty provider                                       -> fails
- agent modified a referral's status                             -> fails (critical invariant)
- agent flipped a denied referral to approved to use it          -> fails
- no mutation at all                                             -> fails
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
        task_id='pp_full_referral_chain',
        seed=seed,
    )
    initial = sm.get_initial_snapshot(sid)
    state = sm.get_state(sid)
    return sm, sid, dict(targets), initial, state


def _neuro_provider(initial):
    """First neurology provider with an available slot."""
    for p in initial.providers:
        if p.specialty == "neurology" and p.available_slots:
            return p
    return None


def _approved_neuro_referral_id(initial, targets):
    """Id of an approved referral whose to_specialty == 'neurology' and
    whose prior_auth is either not required or approved (so the backend
    gate would let us book against it)."""
    approved = set(targets["approved_ref_ids"])
    for r in initial.referrals:
        if (r.id in approved and r.status == "approved"
                and r.to_specialty == "neurology"
                and (not r.prior_auth_required or r.prior_auth_status == "approved")):
            return r.id
    raise AssertionError(
        "seed did not produce an approved neurology referral with "
        f"approved pre-auth (approved_ref_ids={targets['approved_ref_ids']!r}, "
        f"prior_auth_ref_id={targets.get('prior_auth_ref_id')!r})"
    )


def _make_appt(**kwargs) -> Appointment:
    kwargs.setdefault("type", "in-person")
    kwargs.setdefault("status", "scheduled")
    kwargs.setdefault("reason", "Neurology consultation")
    return Appointment(**kwargs)


def test_correct_trajectory_passes():
    """Agent schedules a neurology appointment linked to the approved
    neuro referral (whose pre-auth is approved)."""
    sm, sid, targets, initial, state = _setup_session()
    neuro = _neuro_provider(initial)
    assert neuro is not None, "seed must contain a neurology provider with a slot"
    ref_id = _approved_neuro_referral_id(initial, targets)
    slot = neuro.available_slots[0]

    state.appointments.append(_make_appt(
        id="appt_new_neuro_correct",
        provider_id=neuro.id,
        datetime=slot.datetime,
        type="in-person",
        linked_referral_id=ref_id,
    ))

    task = get_task('pp_full_referral_chain')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is True, f"failures: {report.failures}"
    assert report.score == 1.0, f"expected 1.0, got {report.score}"


def test_wrong_specialty_fails():
    """Agent schedules with a non-neurology provider -- provider_id predicate fails."""
    sm, sid, targets, initial, state = _setup_session()
    other = None
    for p in initial.providers:
        if p.specialty not in ("neurology", "pcp", "billing", "admin") and p.available_slots:
            other = p
            break
    assert other is not None, "seed must contain a non-neurology specialist with a slot"
    ref_id = _approved_neuro_referral_id(initial, targets)
    state.appointments.append(_make_appt(
        id="appt_new_wrong_spec",
        provider_id=other.id,
        datetime=other.available_slots[0].datetime,
        type="in-person",
        linked_referral_id=ref_id,
    ))

    task = get_task('pp_full_referral_chain')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False


def test_modified_referral_status_fails():
    """Agent schedules the neurology appointment correctly BUT also flips a
    pending referral's status to approved -- the referrals invariant
    (critical) must flag the mutation even though the appointment is correct."""
    sm, sid, targets, initial, state = _setup_session()
    neuro = _neuro_provider(initial)
    assert neuro is not None
    ref_id = _approved_neuro_referral_id(initial, targets)
    state.appointments.append(_make_appt(
        id="appt_new_neuro_but_referral_modified",
        provider_id=neuro.id,
        datetime=neuro.available_slots[0].datetime,
        type="in-person",
        linked_referral_id=ref_id,
    ))

    # Pick a pending referral the agent should NOT touch and approve it.
    pending_ids = set(targets.get("pending_ref_ids") or [])
    assert pending_ids, (
        "seed must include at least one pending referral for this test "
        f"(targets={targets})"
    )
    victim_id = next(iter(pending_ids))
    for r in state.referrals:
        if r.id == victim_id:
            r.status = "approved"  # illegal mutation — agent is only meant to verify
            break
    else:
        raise AssertionError(f"referral {victim_id} missing from state")

    task = get_task('pp_full_referral_chain')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "agent mutated a referral's status but task passed — the "
        "state.referrals invariant is not catching the mutation"
    )


def test_used_denied_referral_fails():
    """Agent flips a denied referral to approved and attempts to use it as the
    linked_referral_id for the neuro appointment. The referrals invariant must
    flag the mutation."""
    sm, sid, targets, initial, state = _setup_session()
    neuro = _neuro_provider(initial)
    assert neuro is not None

    denied_ids = list(targets.get("denied_ref_ids") or [])
    assert denied_ids, (
        "seed must include at least one denied referral for this test "
        f"(targets={targets})"
    )
    victim_id = denied_ids[0]

    # Illegal mutation: flip denied -> approved so it can be used.
    for r in state.referrals:
        if r.id == victim_id:
            r.status = "approved"
            if r.prior_auth_required:
                r.prior_auth_status = "approved"
            break
    else:
        raise AssertionError(f"referral {victim_id} missing from state")

    state.appointments.append(_make_appt(
        id="appt_new_neuro_via_denied",
        provider_id=neuro.id,
        datetime=neuro.available_slots[0].datetime,
        type="in-person",
        linked_referral_id=victim_id,
    ))

    task = get_task('pp_full_referral_chain')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "agent flipped a denied referral to approved and used it — the "
        "referrals invariant should have caught the mutation"
    )


def test_no_mutation_fails():
    """Agent did nothing at all -- the required create is missing."""
    sm, sid, targets, initial, state = _setup_session()

    task = get_task('pp_full_referral_chain')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "no-mutation trajectory unexpectedly passed -- invariants are "
        "contributing to the positive numerator (see hazard Class 1)"
    )
