"""End-to-end tests for lms_end_of_semester_verification canonical_diff."""

from datetime import datetime, timedelta

from webagentbench.backend.state import SessionManager
from webagentbench.eval_core import compute_diff, match_diff
from webagentbench.tasks._registry import get_task


def _setup_session(seed: int = 42):
    sm = SessionManager()
    sid, targets, _ = sm.create_session(
        env_id="lms",
        task_id="lms_end_of_semester_verification",
        seed=seed,
    )
    initial = sm.get_initial_snapshot(sid)
    state = sm.get_state(sid)
    parsed_targets = dict(targets)
    return sm, sid, parsed_targets, initial, state, datetime.fromisoformat(parsed_targets["session_start"])


def _ids(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _resubmit_assignment(state, assignment_id: str, *, session_start: datetime) -> None:
    assignment = state.get_assignment(assignment_id)
    if assignment is None:
        raise ValueError(f"assignment {assignment_id!r} not found")

    submitted_at = max(session_start + timedelta(hours=1), assignment.due_at + timedelta(hours=1))
    assignment.file_name = "grade_audit.pdf"
    assignment.submitted_at = submitted_at
    assignment.attempt_count = 2
    assignment.submission_status = "late" if submitted_at > assignment.due_at else "submitted"


def _mark_read(state, announcement_id: str) -> None:
    announcement = state.get_announcement(announcement_id)
    if announcement is None:
        raise ValueError(f"announcement {announcement_id!r} not found")
    announcement.is_read = True


def _report(initial, state, targets, session_start):
    task = get_task("lms_end_of_semester_verification")
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

    for assignment_id in _ids(targets["discrepant_resubmit_assignment_ids"]):
        _resubmit_assignment(state, assignment_id, session_start=session_start)

    for announcement_id in _ids(targets["unread_announcement_ids"]):
        _mark_read(state, announcement_id)

    report = _report(initial, state, targets, session_start)
    assert report.passed is True, f"failures: {report.failures}"
    assert report.score == 1.0, f"expected 1.0, got {report.score}"


def test_no_mutation_fails():
    sm, sid, targets, initial, state, session_start = _setup_session()

    report = _report(initial, state, targets, session_start)
    assert report.passed is False, "doing nothing should fail"
    assert report.score == 0.0, f"expected 0.0, got {report.score}"


def test_wrong_count_fails():
    sm, sid, targets, initial, state, session_start = _setup_session()

    assignment_ids = _ids(targets["discrepant_resubmit_assignment_ids"])
    for assignment_id in assignment_ids[:-1]:
        _resubmit_assignment(state, assignment_id, session_start=session_start)

    for announcement_id in _ids(targets["unread_announcement_ids"]):
        _mark_read(state, announcement_id)

    report = _report(initial, state, targets, session_start)
    assert report.passed is False, "resubmitting only part of the discrepant set should fail"


def test_wrong_id_fails():
    sm, sid, targets, initial, state, session_start = _setup_session()

    for assignment_id in _ids(targets["discrepant_resubmit_assignment_ids"]):
        _resubmit_assignment(state, assignment_id, session_start=session_start)

    unread_ids = set(_ids(targets["unread_announcement_ids"]))
    wrong_announcement = next(a for a in state.announcements if a.id not in unread_ids and a.is_read)
    wrong_announcement.is_read = False

    for announcement_id in unread_ids:
        _mark_read(state, announcement_id)

    report = _report(initial, state, targets, session_start)
    assert report.passed is False, "mutating an announcement outside the unread target set should fail"


def test_extra_mutation_fails():
    sm, sid, targets, initial, state, session_start = _setup_session()

    for assignment_id in _ids(targets["discrepant_resubmit_assignment_ids"]):
        _resubmit_assignment(state, assignment_id, session_start=session_start)

    for announcement_id in _ids(targets["unread_announcement_ids"]):
        _mark_read(state, announcement_id)

    state.enrollments[0].status = "dropped"

    report = _report(initial, state, targets, session_start)
    assert report.passed is False, "dropping a course while verifying grades should fail"
