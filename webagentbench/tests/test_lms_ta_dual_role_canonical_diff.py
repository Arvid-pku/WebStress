"""End-to-end tests for lms_ta_dual_role canonical_diff."""

from datetime import datetime, timedelta

from webagentbench.backend.state import SessionManager
from webagentbench.eval_core import compute_diff, match_diff
from webagentbench.tasks._registry import get_task


def _setup_session(seed: int = 42):
    sm = SessionManager()
    sid, targets, _ = sm.create_session(
        env_id="lms",
        task_id="lms_ta_dual_role",
        seed=seed,
    )
    initial = sm.get_initial_snapshot(sid)
    state = sm.get_state(sid)
    return sm, sid, dict(targets), initial, state


def _session_start(targets: dict[str, str]) -> datetime:
    return datetime.fromisoformat(targets["session_start"])


def _pending_review_ids(targets: dict[str, str]) -> list[str]:
    return [rid.strip() for rid in targets["pending_review_ids"].split(",") if rid.strip()]


def _apply_peer_review(state, review_id: str, rubric_scores: dict[str, int], comments: str) -> None:
    review = state.get_peer_review(review_id)
    if review is None:
        raise ValueError(f"review {review_id!r} not found")
    review.rubric_scores = rubric_scores
    review.comments = comments
    review.status = "submitted"


def _submit_assignment(
    state,
    targets: dict[str, str],
    assignment_id: str,
    file_name: str,
) -> None:
    assignment = state.get_assignment(assignment_id)
    if assignment is None:
        raise ValueError(f"assignment {assignment_id!r} not found")
    submitted_at = max(_session_start(targets), assignment.due_at) + timedelta(minutes=5)
    assignment.file_name = file_name
    assignment.submitted_at = submitted_at
    assignment.attempt_count = 1
    assignment.submission_status = "late" if submitted_at > assignment.due_at else "submitted"


def _report_for(state, initial, targets):
    task = get_task("lms_ta_dual_role")
    agent_diff = compute_diff(initial, state)
    return match_diff(
        agent_diff,
        task.canonical_diff,
        targets=dict(targets),
        initial=initial,
        final=state,
        session_start=_session_start(targets),
    )


def test_seed_roles_are_separated():
    _, _, targets, _, state = _setup_session()

    target_assignment = state.get_assignment(targets["target_assignment_id"])
    assert target_assignment is not None
    assert target_assignment.course_id != targets["ta_course_id"], (
        "student submission must not land in the TA course"
    )

    target_course = state.get_course(target_assignment.course_id)
    assert target_course is not None
    assert target_course.course_code == targets["student_course_code"]

    pending_ids = _pending_review_ids(targets)
    assert pending_ids, "expected pending peer reviews in the TA course"

    pending_course_codes = {
        state.get_course(state.get_assignment(state.get_peer_review(rid).assignment_id).course_id).course_code
        for rid in pending_ids
    }
    assert pending_course_codes == {targets["ta_course_code"]}, (
        f"peer reviews should stay in the TA course, got {pending_course_codes}"
    )


def test_correct_trajectory_passes():
    _, _, targets, initial, state = _setup_session()
    correct_comment = (
        "This review clearly addresses the rubric criteria and explains the reasoning."
    )
    for review_id in _pending_review_ids(targets):
        _apply_peer_review(
            state,
            review_id,
            {"clarity": 5, "depth": 4, "originality": 5},
            correct_comment,
        )
    _submit_assignment(state, targets, targets["target_assignment_id"], "ta_student_submission.pdf")

    report = _report_for(state, initial, targets)
    assert report.passed is True, f"failures: {report.failures}"
    assert report.score == 1.0, f"expected 1.0, got {report.score}"


def test_no_mutation_fails():
    _, _, targets, initial, state = _setup_session()

    report = _report_for(state, initial, targets)
    assert report.passed is False, "doing nothing should fail"
    assert report.score == 0.0, f"expected 0.0, got {report.score}"


def test_missing_peer_review_criterion_fails():
    _, _, targets, initial, state = _setup_session()
    review_ids = _pending_review_ids(targets)

    _apply_peer_review(
        state,
        review_ids[0],
        {"clarity": 5, "depth": 4},
        "This comment is long enough, but the rubric is incomplete.",
    )
    for review_id in review_ids[1:]:
        _apply_peer_review(
            state,
            review_id,
            {"clarity": 5, "depth": 4, "originality": 5},
            "This review clearly addresses the rubric criteria and explains the reasoning.",
        )
    _submit_assignment(state, targets, targets["target_assignment_id"], "ta_student_submission.pdf")

    report = _report_for(state, initial, targets)
    assert report.passed is False, "omitting a rubric criterion should fail"


def test_short_peer_review_comment_fails():
    _, _, targets, initial, state = _setup_session()

    for review_id in _pending_review_ids(targets):
        _apply_peer_review(
            state,
            review_id,
            {"clarity": 5, "depth": 4, "originality": 5},
            "Too short.",
        )
    _submit_assignment(state, targets, targets["target_assignment_id"], "ta_student_submission.pdf")

    report = _report_for(state, initial, targets)
    assert report.passed is False, "short peer review comments should fail"


def test_wrong_assignment_id_fails():
    _, _, targets, initial, state = _setup_session()
    correct_comment = (
        "This review clearly addresses the rubric criteria and explains the reasoning."
    )

    for review_id in _pending_review_ids(targets):
        _apply_peer_review(
            state,
            review_id,
            {"clarity": 5, "depth": 4, "originality": 5},
            correct_comment,
        )
    _submit_assignment(state, targets, targets["decoy_assignment_id"], "ta_student_submission.pdf")

    report = _report_for(state, initial, targets)
    assert report.passed is False, (
        "submitting the decoy assignment should fail the target assignment selector"
    )


def test_extra_mutation_fails():
    _, _, targets, initial, state = _setup_session()
    correct_comment = (
        "This review clearly addresses the rubric criteria and explains the reasoning."
    )

    for review_id in _pending_review_ids(targets):
        _apply_peer_review(
            state,
            review_id,
            {"clarity": 5, "depth": 4, "originality": 5},
            correct_comment,
        )
    _submit_assignment(state, targets, targets["target_assignment_id"], "ta_student_submission.pdf")
    _submit_assignment(state, targets, targets["decoy_assignment_id"], "extra_submission.pdf")

    report = _report_for(state, initial, targets)
    assert report.passed is False, (
        "mutating the decoy assignment should violate the untouched-assignments invariant"
    )
