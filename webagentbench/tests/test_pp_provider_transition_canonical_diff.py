"""End-to-end tests for pp_provider_transition canonical_diff.

Task: "Establish endocrinology follow-up without using messages: 1) Find the
endocrinologist in the directory who is accepting new patients, 2) Use the
approved endocrinology referral to schedule one appointment with that
endocrinologist in the next available slot, 3) Use the appointment reason
exactly 'Endocrinology transfer of care'. Do not cancel any existing
appointments and do not modify any prescriptions."

Trajectories covered:
- correct (endo accepting_new + approved endo referral + earliest endo slot
  + exact reason string) -> passes 1.0
- wrong reason string -> fails (reason predicate)
- wrong provider specialty -> fails (provider_id predicate)
- not the earliest endo slot -> fails (datetime predicate)
- no linked_referral_id -> fails (linked_referral_id predicate)
- cancelled an existing appointment (collateral damage) -> fails (invariant)
- no mutation at all -> fails (required create)
"""

from webagentbench.backend.models.patient_portal import Appointment
from webagentbench.backend.state import SessionManager
from webagentbench.eval_core import compute_diff, match_diff
from webagentbench.tasks._registry import get_task


def _setup_session(seed: int = 42):
    """Fresh session + initial snapshot + live state."""
    sm = SessionManager()
    sid, targets, _ = sm.create_session(
        env_id='patient_portal',
        task_id='pp_provider_transition',
        seed=seed,
    )
    initial = sm.get_initial_snapshot(sid)
    state = sm.get_state(sid)
    return sm, sid, dict(targets), initial, state


def _endo_provider(initial, targets, accepting_new: bool = True):
    """Return the first endocrinology provider in the target pool with
    matching accepting_new."""
    endo_ids = set(targets["endo_provider_ids"])
    for p in initial.providers:
        if p.id in endo_ids and p.specialty == "endocrinology" and p.accepting_new == accepting_new:
            return p
    return None


def _approved_endo_referral_id(initial, targets):
    """Id of an approved referral whose to_specialty == 'endocrinology'."""
    approved = set(targets["approved_ref_ids"])
    for r in initial.referrals:
        if r.id in approved and r.status == "approved" and r.to_specialty == "endocrinology":
            return r.id
    raise AssertionError(
        "seed did not produce an approved endocrinology referral "
        f"(approved_ref_ids={targets['approved_ref_ids']!r})"
    )


def _earliest_endo_slot(initial, targets):
    """Earliest available slot across endocrinologists in the target pool
    who are accepting new patients."""
    endo_ids = set(targets["endo_provider_ids"])
    slots = [
        s.datetime
        for p in initial.providers
        if p.id in endo_ids
        and p.accepting_new
        and p.specialty == "endocrinology"
        for s in p.available_slots
    ]
    assert slots, "seed must produce >=1 endocrinology slot accepting new patients"
    return min(slots)


def _make_appt(**kwargs) -> Appointment:
    kwargs.setdefault("type", "in-person")
    kwargs.setdefault("status", "scheduled")
    kwargs.setdefault("reason", "Endocrinology transfer of care")
    return Appointment(**kwargs)


# ────────────────────────────────────────────────────────────────────


def test_correct_trajectory_passes():
    """Agent schedules an endo transfer-of-care appointment at the next
    available endo slot linked to the approved endo referral."""
    sm, sid, targets, initial, state = _setup_session()
    endo = _endo_provider(initial, targets, accepting_new=True)
    assert endo is not None, "seed must contain an endocrinologist accepting new patients"
    ref_id = _approved_endo_referral_id(initial, targets)

    state.appointments.append(_make_appt(
        id="appt_new_endo_correct",
        provider_id=endo.id,
        datetime=_earliest_endo_slot(initial, targets),
        linked_referral_id=ref_id,
    ))

    task = get_task('pp_provider_transition')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is True, f"failures: {report.failures}"
    assert report.score == 1.0, f"expected 1.0, got {report.score}"


def test_wrong_reason_fails():
    """Appointment scheduled with a reason that doesn't match the required
    exact string -- reason predicate fails."""
    sm, sid, targets, initial, state = _setup_session()
    endo = _endo_provider(initial, targets, accepting_new=True)
    assert endo is not None
    ref_id = _approved_endo_referral_id(initial, targets)

    state.appointments.append(_make_appt(
        id="appt_new_wrong_reason",
        provider_id=endo.id,
        datetime=_earliest_endo_slot(initial, targets),
        linked_referral_id=ref_id,
        reason="Endocrinology follow-up",  # close but not the required exact string
    ))

    task = get_task('pp_provider_transition')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, "wrong reason must fail create predicate"


def test_non_endocrinology_fails():
    """Appointment booked with a non-endocrinology provider -- provider_id
    predicate fails."""
    sm, sid, targets, initial, state = _setup_session()
    ref_id = _approved_endo_referral_id(initial, targets)
    endo_ids = set(targets["endo_provider_ids"])
    other = next(
        p for p in initial.providers
        if p.id not in endo_ids and p.available_slots and p.accepting_new
    )
    state.appointments.append(_make_appt(
        id="appt_new_wrong_spec",
        provider_id=other.id,
        datetime=min(s.datetime for s in other.available_slots),
        linked_referral_id=ref_id,
    ))

    task = get_task('pp_provider_transition')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, "non-endocrinology provider must fail create predicate"


def test_not_earliest_slot_fails():
    """Agent booked the endo appointment at the 2nd-earliest endo slot
    rather than the required earliest slot."""
    sm, sid, targets, initial, state = _setup_session()
    endo = _endo_provider(initial, targets, accepting_new=True)
    assert endo is not None
    ref_id = _approved_endo_referral_id(initial, targets)

    endo_ids = set(targets["endo_provider_ids"])
    slots = sorted(
        s.datetime
        for p in initial.providers
        if p.id in endo_ids
        and p.accepting_new
        and p.specialty == "endocrinology"
        for s in p.available_slots
    )
    assert len(slots) >= 2, "seed must produce >=2 endo slots for this test"
    state.appointments.append(_make_appt(
        id="appt_new_late_slot",
        provider_id=endo.id,
        datetime=slots[1],  # 2nd-earliest
        linked_referral_id=ref_id,
    ))

    task = get_task('pp_provider_transition')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, "non-earliest slot must fail create datetime predicate"


def test_no_linked_referral_fails():
    """Appointment with linked_referral_id=None -- linked_referral_id
    predicate fails."""
    sm, sid, targets, initial, state = _setup_session()
    endo = _endo_provider(initial, targets, accepting_new=True)
    assert endo is not None

    state.appointments.append(_make_appt(
        id="appt_new_no_ref",
        provider_id=endo.id,
        datetime=_earliest_endo_slot(initial, targets),
        linked_referral_id=None,
    ))

    task = get_task('pp_provider_transition')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, "missing linked_referral_id must fail predicate"


def test_cancelled_existing_appt_fails():
    """Agent correctly schedules the endo appointment but also cancels an
    existing upcoming appointment -- invariant on state.appointments must
    reject the collateral damage."""
    sm, sid, targets, initial, state = _setup_session()
    endo = _endo_provider(initial, targets, accepting_new=True)
    assert endo is not None
    ref_id = _approved_endo_referral_id(initial, targets)

    state.appointments.append(_make_appt(
        id="appt_new_endo_correct",
        provider_id=endo.id,
        datetime=_earliest_endo_slot(initial, targets),
        linked_referral_id=ref_id,
    ))
    # Cancel one pre-existing upcoming appointment.
    upcoming_ids = set(targets["upcoming_ids"])
    victim = next(a for a in state.appointments if a.id in upcoming_ids)
    victim.status = "cancelled"

    task = get_task('pp_provider_transition')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False, (
        "cancelling a pre-existing appointment must fail the state.appointments invariant"
    )


def test_no_mutation_fails():
    """Agent did nothing at all -- should fail the required create."""
    sm, sid, targets, initial, state = _setup_session()

    task = get_task('pp_provider_transition')
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
