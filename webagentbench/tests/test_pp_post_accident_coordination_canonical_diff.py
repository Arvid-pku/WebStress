"""End-to-end tests for pp_post_accident_coordination canonical_diff.

Task: coordinate post-accident care by creating exactly three new entities:
  1) an orthopedic follow-up Appointment (reason "Post-accident orthopedic
     follow-up") with a provider in target.ortho_provider_ids;
  2) a new radiology Referral from the PCP (reason "Post-accident MRI
     evaluation");
  3) a PCP disability-documentation Appointment (reason "Disability
     documentation visit").
Do not send messages, cancel existing appointments, or modify medications.

Verifies:
  - Correct trajectory (all three creates) passes 1.0.
  - Missing ortho-appt trajectory fails (create[0]).
  - Missing radiology-referral trajectory fails (create[1]).
  - Missing PCP-appt trajectory fails (create[2]).
  - Wrong-specialty ortho trajectory fails (create[0] predicate).
  - Modified-prescription trajectory fails (state.prescriptions invariant).
  - Do-nothing trajectory scores 0.0, passed=False (Hazard Class 1 guard).
"""

from datetime import timedelta

from webagentbench.backend.models.patient_portal import Appointment, Referral
from webagentbench.backend.state import SessionManager
from webagentbench.evaluator_diff import compute_diff, match_diff
from webagentbench.tasks._registry import get_task


def _setup_session(seed: int = 42):
    sm = SessionManager()
    sid, targets, _ = sm.create_session(
        env_id='patient_portal',
        task_id='pp_post_accident_coordination',
        seed=seed,
    )
    initial = sm.get_initial_snapshot(sid)
    state = sm.get_state(sid)
    return sm, sid, dict(targets), initial, state


def _earliest_slot_for(initial, prov_id: str):
    for p in initial.providers:
        if p.id == prov_id:
            return min(s.datetime for s in p.available_slots)
    raise ValueError(f"provider {prov_id!r} not found in initial snapshot")


def _make_appt(**kwargs) -> Appointment:
    kwargs.setdefault("type", "in-person")
    kwargs.setdefault("status", "scheduled")
    return Appointment(**kwargs)


def _make_referral(**kwargs) -> Referral:
    kwargs.setdefault("status", "requested")
    return Referral(**kwargs)


def _schedule_ortho(state, targets, initial, *, reason=None, provider_id=None,
                    apt_id="appt_new_ortho"):
    ortho_ids = targets["ortho_provider_ids"]
    pid = provider_id if provider_id is not None else ortho_ids[0]
    state.appointments.append(_make_appt(
        id=apt_id,
        provider_id=pid,
        datetime=_earliest_slot_for(initial, pid),
        reason=reason if reason is not None else "Post-accident orthopedic follow-up",
    ))


def _schedule_pcp_docs(state, targets, initial, *, reason=None,
                       apt_id="appt_new_pcp_docs"):
    pcp_id = targets["pcp_id"]
    state.appointments.append(_make_appt(
        id=apt_id,
        provider_id=pcp_id,
        datetime=_earliest_slot_for(initial, pcp_id),
        reason=reason if reason is not None else "Disability documentation visit",
    ))


def _request_radiology_referral(state, targets, *, reason=None,
                                 from_provider_id=None,
                                 ref_id="ref_new_radiology"):
    pcp_id = targets["pcp_id"]
    # Build a plausible expires_at from any existing referral (the field is
    # {any: true} in the canonical diff, so the exact value is irrelevant).
    if state.referrals:
        expires_at = state.referrals[0].expires_at + timedelta(days=30)
    else:
        from webagentbench.backend.time_provider import utc_now
        expires_at = utc_now() + timedelta(days=90)
    state.referrals.append(_make_referral(
        id=ref_id,
        from_provider_id=from_provider_id if from_provider_id is not None else pcp_id,
        to_specialty="radiology",
        reason=reason if reason is not None else "Post-accident MRI evaluation",
        status="requested",
        expires_at=expires_at,
    ))


def _run(state, initial, targets):
    task = get_task('pp_post_accident_coordination')
    agent_diff = compute_diff(initial, state)
    return match_diff(
        agent_diff, task.canonical_diff,
        targets=dict(targets),
        initial=initial, final=state,
    )


# ────────────────────────────────────────────────────────────────────


def test_correct_trajectory_passes():
    sm, sid, targets, initial, state = _setup_session()
    _schedule_ortho(state, targets, initial)
    _request_radiology_referral(state, targets)
    _schedule_pcp_docs(state, targets, initial)

    report = _run(state, initial, targets)
    assert report.passed is True, f"failures: {report.failures}"
    assert report.score == 1.0, f"expected 1.0, got {report.score}"


def test_missing_ortho_fails():
    """Agent skipped the orthopedic follow-up."""
    sm, sid, targets, initial, state = _setup_session()
    _request_radiology_referral(state, targets)
    _schedule_pcp_docs(state, targets, initial)

    report = _run(state, initial, targets)
    assert report.passed is False, "missing ortho appt must fail"
    assert report.score < 1.0, f"expected <1.0, got {report.score}"


def test_missing_radiology_referral_fails():
    """Agent skipped the radiology referral request."""
    sm, sid, targets, initial, state = _setup_session()
    _schedule_ortho(state, targets, initial)
    _schedule_pcp_docs(state, targets, initial)

    report = _run(state, initial, targets)
    assert report.passed is False, "missing radiology referral must fail"
    assert report.score < 1.0, f"expected <1.0, got {report.score}"


def test_missing_pcp_appt_fails():
    """Agent skipped the PCP disability-documentation appointment."""
    sm, sid, targets, initial, state = _setup_session()
    _schedule_ortho(state, targets, initial)
    _request_radiology_referral(state, targets)

    report = _run(state, initial, targets)
    assert report.passed is False, "missing PCP docs appt must fail"
    assert report.score < 1.0, f"expected <1.0, got {report.score}"


def test_wrong_specialty_ortho_fails():
    """Agent booked an 'ortho' appointment with a non-orthopedics provider."""
    sm, sid, targets, initial, state = _setup_session()
    pcp_id = targets["pcp_id"]
    ortho_ids = set(targets["ortho_provider_ids"])
    # Find a provider with slots that's neither ortho nor PCP.
    wrong = None
    for p in initial.providers:
        if p.id in ortho_ids or p.id == pcp_id:
            continue
        if not p.available_slots:
            continue
        wrong = p
        break
    assert wrong is not None, "seed must have a non-ortho non-PCP provider with slots"

    # Note: we bypass the actual /appointments/create route (which has a
    # referral gate) and write directly to state — the point is to exercise
    # the matcher's predicate rejection on provider_id.
    state.appointments.append(_make_appt(
        id="appt_new_wrong_specialty",
        provider_id=wrong.id,
        datetime=min(s.datetime for s in wrong.available_slots),
        reason="Post-accident orthopedic follow-up",
    ))
    _request_radiology_referral(state, targets)
    _schedule_pcp_docs(state, targets, initial)

    report = _run(state, initial, targets)
    assert report.passed is False, (
        "ortho booking with non-orthopedics provider must fail create[0]"
    )


def test_modified_rx_fails():
    """Agent did all three creates but also mutated an active prescription."""
    sm, sid, targets, initial, state = _setup_session()
    _schedule_ortho(state, targets, initial)
    _request_radiology_referral(state, targets)
    _schedule_pcp_docs(state, targets, initial)

    active_rx_ids = targets["active_rx_ids"]
    assert active_rx_ids, "seed must emit at least one active prescription"
    mutated = False
    for rx in state.prescriptions:
        if rx.id == active_rx_ids[0]:
            rx.status = "discontinued"
            mutated = True
            break
    assert mutated, "target active prescription not found in state"

    report = _run(state, initial, targets)
    assert report.passed is False, (
        "modified prescription must fail state.prescriptions invariant"
    )


def test_no_mutation_fails():
    """Agent did nothing — score must be 0.0 and passed=False (Hazard Class 1
    regression guard: invariants are penalty-only, never positive weight)."""
    sm, sid, targets, initial, state = _setup_session()
    report = _run(state, initial, targets)
    assert report.passed is False, "do-nothing trajectory must fail"
    assert report.score == 0.0, (
        f"do-nothing must earn 0.0 score (invariants are penalty-only), "
        f"got {report.score}"
    )
