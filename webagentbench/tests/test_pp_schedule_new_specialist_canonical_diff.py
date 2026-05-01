"""End-to-end tests for pp_schedule_new_specialist canonical_diff.

Task: find a dermatologist accepting new patients, schedule an in-person
appointment linked to the existing approved dermatology referral.

Trajectories covered:
- correct (derm provider + accepting_new + in-person + linked to approved
  derm referral) -> passes 1.0
- non-dermatology provider -> fails (provider_id predicate)
- provider not accepting new patients -> fails (accepting_new predicate)
- type=telehealth instead of in-person -> fails
- no linked_referral_id (None) -> fails
- no mutation at all -> fails
"""

from datetime import datetime, timezone

from webagentbench.backend.models.patient_portal import Appointment
from webagentbench.backend.state import SessionManager
from webagentbench.eval_core import compute_diff, match_diff
from webagentbench.tasks._registry import get_task


def _setup_session(seed: int = 42):
    """Fresh session + initial snapshot + live state."""
    sm = SessionManager()
    sid, targets, _ = sm.create_session(
        env_id='patient_portal',
        task_id='pp_schedule_new_specialist',
        seed=seed,
    )
    initial = sm.get_initial_snapshot(sid)
    state = sm.get_state(sid)
    return sm, sid, dict(targets), initial, state


def _derm_provider(initial, accepting_new: bool = True):
    """Return the first dermatology provider with matching accepting_new."""
    for p in initial.providers:
        if p.specialty == "dermatology" and p.accepting_new == accepting_new:
            return p
    return None


def _approved_derm_referral_id(initial, targets):
    """Id of an approved referral whose to_specialty == 'dermatology'."""
    approved = set(targets["approved_ref_ids"])
    for r in initial.referrals:
        if r.id in approved and r.status == "approved" and r.to_specialty == "dermatology":
            return r.id
    raise AssertionError(
        "seed did not produce an approved dermatology referral "
        f"(approved_ref_ids={targets['approved_ref_ids']!r})"
    )


def _make_appt(**kwargs) -> Appointment:
    kwargs.setdefault("type", "in-person")
    kwargs.setdefault("status", "scheduled")
    kwargs.setdefault("reason", "Dermatology consultation")
    return Appointment(**kwargs)


def test_correct_trajectory_passes():
    """Agent schedules an in-person derm appointment linked to the approved derm referral."""
    sm, sid, targets, initial, state = _setup_session()
    derm = _derm_provider(initial, accepting_new=True)
    assert derm is not None, "seed must contain a dermatology provider accepting new patients"
    ref_id = _approved_derm_referral_id(initial, targets)
    slot = derm.available_slots[0]

    state.appointments.append(_make_appt(
        id="appt_new_derm_correct",
        provider_id=derm.id,
        datetime=slot.datetime,
        type="in-person",
        linked_referral_id=ref_id,
    ))

    task = get_task('pp_schedule_new_specialist')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is True, f"failures: {report.failures}"
    assert report.score == 1.0, f"expected 1.0, got {report.score}"


def test_non_dermatology_fails():
    """Appointment scheduled with a non-dermatology provider -- provider_id predicate fails."""
    sm, sid, targets, initial, state = _setup_session()
    other = next(
        p for p in initial.providers
        if p.specialty not in ("dermatology", "pcp", "billing", "admin")
        and p.available_slots and p.accepting_new
    )
    ref_id = _approved_derm_referral_id(initial, targets)
    state.appointments.append(_make_appt(
        id="appt_new_wrong_spec",
        provider_id=other.id,
        datetime=other.available_slots[0].datetime,
        type="in-person",
        linked_referral_id=ref_id,
    ))

    task = get_task('pp_schedule_new_specialist')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False


def test_not_accepting_new_fails():
    """Appointment with a derm provider whose accepting_new has been flipped False."""
    sm, sid, targets, initial, state = _setup_session()
    derm = _derm_provider(initial, accepting_new=True)
    assert derm is not None
    # Mutate on BOTH initial and final so the agent's action is "picked a provider
    # who wasn't accepting new" rather than "agent flipped the provider's flag".
    for p in initial.providers:
        if p.id == derm.id:
            p.accepting_new = False
    for p in state.providers:
        if p.id == derm.id:
            p.accepting_new = False
    ref_id = _approved_derm_referral_id(initial, targets)
    state.appointments.append(_make_appt(
        id="appt_new_closed_panel",
        provider_id=derm.id,
        datetime=derm.available_slots[0].datetime,
        type="in-person",
        linked_referral_id=ref_id,
    ))

    task = get_task('pp_schedule_new_specialist')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False


def test_wrong_type_telehealth_fails():
    """Appointment scheduled as telehealth instead of in-person -- type predicate fails."""
    sm, sid, targets, initial, state = _setup_session()
    derm = _derm_provider(initial, accepting_new=True)
    assert derm is not None
    ref_id = _approved_derm_referral_id(initial, targets)
    state.appointments.append(_make_appt(
        id="appt_new_wrong_type",
        provider_id=derm.id,
        datetime=derm.available_slots[0].datetime,
        type="telehealth",
        linked_referral_id=ref_id,
    ))

    task = get_task('pp_schedule_new_specialist')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False


def test_no_linked_referral_fails():
    """Appointment with linked_referral_id=None -- linked_referral_id predicate fails."""
    sm, sid, targets, initial, state = _setup_session()
    derm = _derm_provider(initial, accepting_new=True)
    assert derm is not None
    state.appointments.append(_make_appt(
        id="appt_new_no_ref",
        provider_id=derm.id,
        datetime=derm.available_slots[0].datetime,
        type="in-person",
        linked_referral_id=None,
    ))

    task = get_task('pp_schedule_new_specialist')
    agent_diff = compute_diff(initial, state)
    report = match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )
    assert report.passed is False


def test_no_mutation_fails():
    """Agent did nothing at all -- should fail the required create."""
    sm, sid, targets, initial, state = _setup_session()

    task = get_task('pp_schedule_new_specialist')
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
