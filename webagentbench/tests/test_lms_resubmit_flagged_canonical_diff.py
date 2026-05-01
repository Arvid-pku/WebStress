"""End-to-end tests for lms_resubmit_flagged canonical_diff."""

from datetime import datetime, timedelta

from webagentbench.backend.state import SessionManager
from webagentbench.eval_core import compute_diff, match_diff
from webagentbench.tasks._registry import get_task


def _setup_session(seed: int = 42):
    sm = SessionManager()
    sid, targets, _ = sm.create_session(
        env_id="lms",
        task_id="lms_resubmit_flagged",
        seed=seed,
    )
    initial = sm.get_initial_snapshot(sid)
    state = sm.get_state(sid)
    parsed_targets = dict(targets)
    return sm, sid, parsed_targets, initial, state, datetime.fromisoformat(parsed_targets["session_start"])


def _target_ids(targets: dict[str, str]) -> list[str]:
    return [aid.strip() for aid in targets["resubmit_assignment_ids"].split(",") if aid.strip()]


def _resubmit_assignment(
    state,
    assignment_id: str,
    *,
    file_name: str,
    submitted_at: datetime,
    attempt_count: int = 2,
) -> None:
    assignment = state.get_assignment(assignment_id)
    if assignment is None:
        raise ValueError(f"assignment {assignment_id!r} not found")
    assignment.file_name = file_name
    assignment.submitted_at = submitted_at
    assignment.attempt_count = attempt_count
    assignment.submission_status = "late" if submitted_at > assignment.due_at else "submitted"


def _match(task_id: str, initial, state, targets, session_start):
    task = get_task(task_id)
    agent_diff = compute_diff(initial, state)
    return match_diff(
        agent_diff,
        task.canonical_diff,
        targets=dict(targets),
        initial=initial,
        final=state,
        session_start=session_start,
    )


def test_correct_trajectory_passes():
    sm, sid, targets, initial, state, session_start = _setup_session()

    for assignment_id in _target_ids(targets):
        assignment = state.get_assignment(assignment_id)
        assert assignment is not None
        _resubmit_assignment(
            state,
            assignment_id,
            file_name="revision_v2.pdf",
            submitted_at=assignment.due_at - timedelta(hours=1),
        )

    report = _match("lms_resubmit_flagged", initial, state, targets, session_start)
    assert report.passed is True, f"failures: {report.failures}"
    assert report.score == 1.0, f"expected 1.0, got {report.score}"


def test_late_resubmission_passes():
    sm, sid, targets, initial, state, session_start = _setup_session()

    for assignment_id in _target_ids(targets):
        assignment = state.get_assignment(assignment_id)
        assert assignment is not None
        _resubmit_assignment(
            state,
            assignment_id,
            file_name="revision_v2.pdf",
            submitted_at=assignment.due_at + timedelta(hours=1),
        )

    report = _match("lms_resubmit_flagged", initial, state, targets, session_start)
    assert report.passed is True, f"failures: {report.failures}"
    assert report.score == 1.0, f"expected 1.0, got {report.score}"


def test_no_mutation_fails():
    sm, sid, targets, initial, state, session_start = _setup_session()

    report = _match("lms_resubmit_flagged", initial, state, targets, session_start)
    assert report.passed is False, "doing nothing should fail"
    assert report.score == 0.0, f"expected 0.0, got {report.score}"


def test_partial_resubmission_fails():
    sm, sid, targets, initial, state, session_start = _setup_session()

    target_ids = _target_ids(targets)
    assignment = state.get_assignment(target_ids[0])
    assert assignment is not None
    _resubmit_assignment(
        state,
        target_ids[0],
        file_name="revision_v2.pdf",
        submitted_at=assignment.due_at - timedelta(hours=1),
    )

    report = _match("lms_resubmit_flagged", initial, state, targets, session_start)
    assert report.passed is False, "resubmitting only one flagged assignment should fail"


def test_wrong_file_name_fails():
    sm, sid, targets, initial, state, session_start = _setup_session()

    target_ids = _target_ids(targets)
    assignment = state.get_assignment(target_ids[0])
    assert assignment is not None
    _resubmit_assignment(
        state,
        target_ids[0],
        file_name="wrong_upload.pdf",
        submitted_at=assignment.due_at - timedelta(hours=1),
    )

    assignment = state.get_assignment(target_ids[1])
    assert assignment is not None
    _resubmit_assignment(
        state,
        target_ids[1],
        file_name="revision_v2.pdf",
        submitted_at=assignment.due_at - timedelta(hours=1),
    )

    report = _match("lms_resubmit_flagged", initial, state, targets, session_start)
    assert report.passed is False, "using the wrong file name should fail"


def test_wrong_assignment_fails():
    sm, sid, targets, initial, state, session_start = _setup_session()

    decoy = state.get_assignment(targets["decoy_assignment_id"])
    assert decoy is not None
    _resubmit_assignment(
        state,
        decoy.id,
        file_name="revision_v2.pdf",
        submitted_at=decoy.due_at - timedelta(hours=1),
    )

    report = _match("lms_resubmit_flagged", initial, state, targets, session_start)
    assert report.passed is False, "resubmitting the decoy assignment should fail"


def test_extra_enrollment_mutation_fails():
    sm, sid, targets, initial, state, session_start = _setup_session()

    for assignment_id in _target_ids(targets):
        assignment = state.get_assignment(assignment_id)
        assert assignment is not None
        _resubmit_assignment(
            state,
            assignment_id,
            file_name="revision_v2.pdf",
            submitted_at=assignment.due_at - timedelta(hours=1),
        )

    state.enrollments[0].status = "dropped"

    report = _match("lms_resubmit_flagged", initial, state, targets, session_start)
    assert report.passed is False, (
        "dropping a course while resubmitting flagged assignments should fail"
    )
