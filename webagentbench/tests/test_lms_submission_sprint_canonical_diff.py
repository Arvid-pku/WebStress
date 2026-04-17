"""End-to-end tests for lms_submission_sprint canonical_diff."""

from datetime import datetime, timezone
from decimal import Decimal

from webagentbench.backend.state import SessionManager
from webagentbench.evaluator_diff import compute_diff, match_diff
from webagentbench.tasks._registry import get_task


def _setup_session(seed: int = 42):
    sm = SessionManager()
    sid, targets, _ = sm.create_session(
        env_id="lms",
        task_id="lms_submission_sprint",
        seed=seed,
    )
    initial = sm.get_initial_snapshot(sid)
    state = sm.get_state(sid)
    return sm, sid, dict(targets), initial, state


def _submission_priority_key(state, assignment, submit_time: datetime):
    course = state.get_course(assignment.course_id)
    if course is None:
        raise ValueError(f"course for assignment {assignment.id!r} not found")
    weight = Decimal(str(course.syllabus.grading_policy[assignment.weight_category].weight))
    weighted_points = Decimal(str(assignment.points_possible)) * weight
    penalty = state.late_penalty_for_assignment(assignment.id, submit_time)
    impact = weighted_points * (Decimal("1") - penalty)
    return (impact, weighted_points, -assignment.due_at.timestamp(), assignment.id)


def _top_submission_ids(state, count: int = 3, submit_time: datetime | None = None) -> list[str]:
    submit_time = submit_time or datetime.now(timezone.utc)
    ranked = sorted(
        [
            ( _submission_priority_key(state, assignment, submit_time), assignment.id)
            for assignment in state.assignments
            if assignment.submission_status == "not_submitted"
        ],
        reverse=True,
    )
    return [assignment_id for _key, assignment_id in ranked[:count]]


def _submit_assignment(
    state,
    assignment_id: str,
    *,
    file_name: str = "sprint_submission.pdf",
    submitted_at: datetime | None = None,
) -> None:
    assignment = state.get_assignment(assignment_id)
    if assignment is None:
        raise ValueError(f"assignment {assignment_id!r} not found")
    submitted_at = submitted_at or datetime.now(timezone.utc)
    assignment.submission_status = "late" if submitted_at > assignment.due_at else "submitted"
    assignment.file_name = file_name
    assignment.attempt_count += 1
    assignment.submitted_at = submitted_at


def _report_for(state, initial, targets):
    task = get_task("lms_submission_sprint")
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
    submitted_at = datetime.now(timezone.utc)
    top_ids = _top_submission_ids(state, submit_time=submitted_at)

    for assignment_id in top_ids:
        _submit_assignment(state, assignment_id, submitted_at=submitted_at)

    report = _report_for(state, initial, targets)
    assert report.passed is True, f"failures: {report.failures}"
    assert report.score == 1.0, f"expected 1.0, got {report.score}"


def test_no_mutation_fails():
    _, _, targets, initial, state = _setup_session()

    report = _report_for(state, initial, targets)
    assert report.passed is False, "doing nothing should fail"
    assert report.score == 0.0, f"expected 0.0, got {report.score}"


def test_wrong_assignment_fails():
    _, _, targets, initial, state = _setup_session()
    submitted_at = datetime.now(timezone.utc)
    top_ids = _top_submission_ids(state, submit_time=submitted_at)

    _submit_assignment(state, top_ids[0], submitted_at=submitted_at)
    _submit_assignment(state, top_ids[1], submitted_at=submitted_at)

    wrong_id = next(
        assignment.id
        for assignment in state.assignments
        if assignment.id not in top_ids
    )
    _submit_assignment(state, wrong_id, submitted_at=submitted_at)

    report = _report_for(state, initial, targets)
    assert report.passed is False, "submitting a non-target assignment should fail"


def test_wrong_count_fails():
    _, _, targets, initial, state = _setup_session()
    submitted_at = datetime.now(timezone.utc)
    top_ids = _top_submission_ids(state, submit_time=submitted_at)

    _submit_assignment(state, top_ids[0], submitted_at=submitted_at)
    _submit_assignment(state, top_ids[1], submitted_at=submitted_at)

    report = _report_for(state, initial, targets)
    assert report.passed is False, "submitting only two assignments should fail"


def test_extra_mutation_fails():
    _, _, targets, initial, state = _setup_session()
    submitted_at = datetime.now(timezone.utc)
    top_ids = _top_submission_ids(state, submit_time=submitted_at)

    for assignment_id in top_ids:
        _submit_assignment(state, assignment_id, submitted_at=submitted_at)

    wrong_id = next(
        assignment.id
        for assignment in state.assignments
        if assignment.id not in top_ids
    )
    _submit_assignment(state, wrong_id, file_name="extra_submission.pdf", submitted_at=submitted_at)

    report = _report_for(state, initial, targets)
    assert report.passed is False, (
        "submitting a fourth assignment should violate the assignment invariant"
    )
