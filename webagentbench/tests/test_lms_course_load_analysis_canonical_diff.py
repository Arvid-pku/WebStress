"""End-to-end tests for lms_course_load_analysis canonical_diff."""

from webagentbench.backend.state import SessionManager
from webagentbench.evaluator_diff import compute_diff, match_diff
from webagentbench.tasks._registry import get_task


def _setup_session(seed: int = 42):
    sm = SessionManager()
    sid, targets, _ = sm.create_session(
        env_id="lms",
        task_id="lms_course_load_analysis",
        seed=seed,
    )
    initial = sm.get_initial_snapshot(sid)
    state = sm.get_state(sid)
    return sm, sid, dict(targets), initial, state


def _csv_ids(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _mark_announcements_read(state, announcement_ids: list[str]) -> None:
    for announcement_id in announcement_ids:
        announcement = next((a for a in state.announcements if a.id == announcement_id), None)
        if announcement is None:
            raise ValueError(f"announcement {announcement_id!r} not found")
        announcement.is_read = True


def _drop_course(state, course_id: str) -> None:
    enrollment = state.get_enrollment_for_course(course_id)
    if enrollment is None:
        raise ValueError(f"enrollment for course {course_id!r} not found")
    enrollment.status = "dropped"


def _apply_correct_trajectory(state, targets: dict[str, str]) -> None:
    if targets["can_add_course"] == "true":
        _mark_announcements_read(state, _csv_ids(targets["unread_announcement_ids"]))
    else:
        _drop_course(state, targets["lowest_performing_course_id"])


def _report(initial, state, targets):
    task = get_task("lms_course_load_analysis")
    agent_diff = compute_diff(initial, state)
    return match_diff(
        agent_diff,
        task.canonical_diff,
        targets=dict(targets),
        initial=initial,
        final=state,
    )


def test_correct_trajectory_passes():
    _, _, targets, initial, state = _setup_session()

    _apply_correct_trajectory(state, targets)

    report = _report(initial, state, targets)
    assert report.passed is True, f"failures: {report.failures}"
    assert report.score == 1.0, f"expected 1.0, got {report.score}"


def test_no_mutation_fails():
    _, _, targets, initial, state = _setup_session()

    report = _report(initial, state, targets)
    assert report.passed is False, "doing nothing should fail"
    assert report.score == 0.0, f"expected 0.0, got {report.score}"


def test_wrong_branch_fails():
    _, _, targets, initial, state = _setup_session()

    if targets["can_add_course"] == "true":
        _drop_course(state, targets["lowest_performing_course_id"])
    else:
        _mark_announcements_read(state, _csv_ids(targets["unread_announcement_ids"]))

    report = _report(initial, state, targets)
    assert report.passed is False, "taking the wrong branch should fail"


def test_extra_drop_fails():
    _, _, targets, initial, state = _setup_session()

    _apply_correct_trajectory(state, targets)
    extra_course = next(
        enrollment.course_id
        for enrollment in state.enrollments
        if enrollment.course_id != targets["lowest_performing_course_id"]
    )
    _drop_course(state, extra_course)

    report = _report(initial, state, targets)
    assert report.passed is False, "dropping an extra course should fail"
