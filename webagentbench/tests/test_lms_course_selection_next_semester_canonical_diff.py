"""End-to-end tests for lms_course_selection_next_semester canonical_diff."""

from datetime import datetime, timedelta, timezone

from webagentbench.backend.state import SessionManager
from webagentbench.eval_core import compute_diff, match_diff
from webagentbench.tasks._registry import get_task


def _setup_session(seed: int = 42):
    sm = SessionManager()
    sid, targets, _ = sm.create_session(
        env_id="lms",
        task_id="lms_course_selection_next_semester",
        seed=seed,
    )
    initial = sm.get_initial_snapshot(sid)
    state = sm.get_state(sid)
    return sm, sid, dict(targets), initial, state


def _course_plan_assignment_id(targets: dict[str, str]) -> str:
    assignment_id = targets["course_plan_assignment_id"].strip()
    if not assignment_id:
        raise ValueError("seed must provide a course_plan_assignment_id")
    return assignment_id


def _unread_announcement_ids(targets: dict[str, str]) -> list[str]:
    raw = targets.get("unread_announcement_ids", "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def _session_start(targets: dict[str, str]) -> datetime:
    return datetime.fromisoformat(targets["session_start"])


def _submit_course_plan(state, targets: dict[str, str]) -> None:
    assignment = state.get_assignment(_course_plan_assignment_id(targets))
    if assignment is None:
        raise ValueError("target course_plan assignment not found")

    submitted_at = max(
        _session_start(targets) + timedelta(hours=1),
        datetime.now(timezone.utc),
    )
    assignment.file_name = "course_plan.pdf"
    assignment.submitted_at = submitted_at
    assignment.attempt_count += 1
    assignment.submission_status = (
        "late" if submitted_at > assignment.due_at else "submitted"
    )


def _mark_announcements_read(state, announcement_ids: list[str]) -> None:
    for announcement_id in announcement_ids:
        announcement = state.get_announcement(announcement_id)
        if announcement is None:
            raise ValueError(f"announcement {announcement_id!r} not found")
        announcement.is_read = True


def _report(initial, state, targets):
    task = get_task("lms_course_selection_next_semester")
    agent_diff = compute_diff(initial, state)
    return match_diff(
        agent_diff,
        task.canonical_diff,
        targets=dict(targets),
        initial=initial,
        final=state,
        session_start=_session_start(targets),
    )


def test_correct_trajectory_passes():
    _, _, targets, initial, state = _setup_session()

    _submit_course_plan(state, targets)

    report = _report(initial, state, targets)
    assert report.passed is True, f"failures: {report.failures}"
    assert report.score == 1.0, f"expected 1.0, got {report.score}"


def test_ineligible_branch_passes():
    _, _, targets, initial, state = _setup_session()
    low_gpa_targets = dict(targets)
    low_gpa_targets["gpa"] = "2.40"

    _mark_announcements_read(state, _unread_announcement_ids(targets))

    report = _report(initial, state, low_gpa_targets)
    assert report.passed is True, f"failures: {report.failures}"
    assert report.score == 1.0, f"expected 1.0, got {report.score}"


def test_no_mutation_fails():
    _, _, targets, initial, state = _setup_session()

    report = _report(initial, state, targets)
    assert report.passed is False, "doing nothing should fail"
    assert report.score == 0.0, f"expected 0.0, got {report.score}"


def test_wrong_assignment_file_fails():
    _, _, targets, initial, state = _setup_session()

    assignment = state.get_assignment(_course_plan_assignment_id(targets))
    if assignment is None:
        raise ValueError("target course_plan assignment not found")
    submitted_at = max(
        _session_start(targets) + timedelta(hours=1),
        datetime.now(timezone.utc),
    )
    assignment.file_name = "wrong_upload.pdf"
    assignment.submitted_at = submitted_at
    assignment.attempt_count += 1
    assignment.submission_status = (
        "late" if submitted_at > assignment.due_at else "submitted"
    )

    report = _report(initial, state, targets)
    assert report.passed is False, "submitting with the wrong file should fail"


def test_partial_announcement_read_fails():
    _, _, targets, initial, state = _setup_session()
    low_gpa_targets = dict(targets)
    low_gpa_targets["gpa"] = "2.40"
    unread_ids = _unread_announcement_ids(targets)
    assert len(unread_ids) >= 2, "seed must provide at least two unread announcements"

    _mark_announcements_read(state, unread_ids[:-1])

    report = _report(initial, state, low_gpa_targets)
    assert report.passed is False, (
        "leaving one announcement unread on the read-announcements branch should fail"
    )


def test_wrong_branch_fails():
    _, _, targets, initial, state = _setup_session()

    _mark_announcements_read(state, _unread_announcement_ids(targets))

    report = _report(initial, state, targets)
    assert report.passed is False, "taking the announcement branch when eligible should fail"


def test_extra_collateral_mutation_fails():
    _, _, targets, initial, state = _setup_session()

    _submit_course_plan(state, targets)
    state.courses[0].title = state.courses[0].title + " (edited)"

    report = _report(initial, state, targets)
    assert report.passed is False, (
        "editing a course while submitting the course plan should violate the invariant"
    )
