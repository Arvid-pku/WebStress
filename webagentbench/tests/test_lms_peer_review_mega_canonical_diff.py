"""End-to-end tests for lms_peer_review_mega canonical_diff."""

from datetime import datetime, timedelta

from webagentbench.backend.state import SessionManager
from webagentbench.eval_core import compute_diff, match_diff
from webagentbench.tasks._registry import get_task


def _setup_session(seed: int = 42):
    sm = SessionManager()
    sid, targets, _ = sm.create_session(
        env_id="lms",
        task_id="lms_peer_review_mega",
        seed=seed,
    )
    initial = sm.get_initial_snapshot(sid)
    state = sm.get_state(sid)
    session_start = datetime.fromisoformat(targets["session_start"])
    return sm, sid, dict(targets), initial, state, session_start


def _ids(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _pending_review_ids(targets: dict[str, str]) -> list[str]:
    return _ids(targets["pending_review_ids"])


def _resubmit_assignment_ids(targets: dict[str, str]) -> list[str]:
    return _ids(targets["resubmit_assignment_ids"])


def _submit_review(state, review_id: str, *, rubric_scores: dict[str, int], comments: str) -> None:
    review = state.get_peer_review(review_id)
    if review is None:
        raise ValueError(f"review {review_id!r} not found")
    review.rubric_scores = rubric_scores
    review.comments = comments
    review.status = "submitted"


def _resubmit_assignment(
    state,
    assignment_id: str,
    *,
    file_name: str,
    submitted_at: datetime,
) -> None:
    assignment = state.get_assignment(assignment_id)
    if assignment is None:
        raise ValueError(f"assignment {assignment_id!r} not found")
    assignment.file_name = file_name
    assignment.submitted_at = submitted_at
    assignment.attempt_count = 2
    assignment.submission_status = "late" if submitted_at > assignment.due_at else "submitted"


def _report(initial, state, targets, session_start):
    task = get_task("lms_peer_review_mega")
    agent_diff = compute_diff(initial, state)
    return match_diff(
        agent_diff,
        task.canonical_diff,
        targets=dict(targets),
        initial=initial,
        final=state,
        session_start=session_start,
    )


def _apply_happy_path(state, targets, session_start):
    for review_id in _pending_review_ids(targets):
        _submit_review(
            state,
            review_id,
            rubric_scores={"clarity": 5, "depth": 4, "originality": 5},
            comments="This submission is clearly structured, detailed, and thoughtfully argued throughout.",
        )

    assignment_id = _resubmit_assignment_ids(targets)[0]
    assignment = state.get_assignment(assignment_id)
    if assignment is None:
        raise ValueError(f"assignment {assignment_id!r} not found")
    _resubmit_assignment(
        state,
        assignment_id,
        file_name="revised_after_review.pdf",
        submitted_at=max(
            session_start + timedelta(minutes=5),
            assignment.due_at + timedelta(hours=1),
        ),
    )


def test_correct_trajectory_passes():
    _, _, targets, initial, state, session_start = _setup_session()
    _apply_happy_path(state, targets, session_start)

    report = _report(initial, state, targets, session_start)
    assert report.passed is True, f"failures: {report.failures}"
    assert report.score == 1.0, f"expected 1.0, got {report.score}"


def test_no_mutation_fails():
    _, _, targets, initial, state, session_start = _setup_session()

    report = _report(initial, state, targets, session_start)
    assert report.passed is False, "doing nothing should fail"
    assert report.score == 0.0, f"expected 0.0, got {report.score}"


def test_missing_rubric_criterion_fails():
    _, _, targets, initial, state, session_start = _setup_session()

    review_id = _pending_review_ids(targets)[0]
    _submit_review(
        state,
        review_id,
        rubric_scores={"clarity": 5, "depth": 4},
        comments="This comment is still long enough, but one rubric criterion is missing.",
    )

    report = _report(initial, state, targets, session_start)
    assert report.passed is False, "omitting one rubric criterion should fail"


def test_short_comment_fails():
    _, _, targets, initial, state, session_start = _setup_session()

    review_id = _pending_review_ids(targets)[0]
    _submit_review(
        state,
        review_id,
        rubric_scores={"clarity": 5, "depth": 4, "originality": 5},
        comments="Too short",
    )

    report = _report(initial, state, targets, session_start)
    assert report.passed is False, "short comments should fail"


def test_wrong_assignment_file_fails():
    _, _, targets, initial, state, session_start = _setup_session()

    _apply_happy_path(state, targets, session_start)
    assignment_id = _resubmit_assignment_ids(targets)[0]
    assignment = state.get_assignment(assignment_id)
    assert assignment is not None

    _resubmit_assignment(
        state,
        assignment_id,
        file_name="wrong_upload.pdf",
        submitted_at=max(
            session_start + timedelta(minutes=5),
            assignment.due_at + timedelta(hours=1),
        ),
    )

    report = _report(initial, state, targets, session_start)
    assert report.passed is False, "using the wrong file name should fail"


def test_extra_mutation_fails():
    _, _, targets, initial, state, session_start = _setup_session()

    _apply_happy_path(state, targets, session_start)
    state.enrollments[0].status = "dropped"

    report = _report(initial, state, targets, session_start)
    assert report.passed is False, "dropping an enrollment should fail"
