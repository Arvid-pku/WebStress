"""End-to-end tests for lms_final_exam_prep_plan canonical_diff."""

from datetime import datetime, timedelta

from webagentbench.backend.state import SessionManager
from webagentbench.eval_core import compute_diff, match_diff
from webagentbench.tasks._registry import get_task


def _setup_session(seed: int = 42):
    sm = SessionManager()
    sid, targets, _ = sm.create_session(
        env_id="lms",
        task_id="lms_final_exam_prep_plan",
        seed=seed,
    )
    initial = sm.get_initial_snapshot(sid)
    state = sm.get_state(sid)
    return sm, sid, dict(targets), initial, state


def _ids(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _session_start(targets: dict[str, str]) -> datetime:
    return datetime.fromisoformat(targets["session_start"])


def _drop_enrollment(state, enrollment_id: str) -> None:
    enrollment = next((e for e in state.enrollments if e.id == enrollment_id), None)
    if enrollment is None:
        raise ValueError(f"enrollment {enrollment_id!r} not found")
    enrollment.status = "dropped"


def _submit_exam_prep(state, targets: dict[str, str], assignment_id: str, *, file_name: str = "exam_prep.pdf") -> None:
    assignment = state.get_assignment(assignment_id)
    if assignment is None:
        raise ValueError(f"assignment {assignment_id!r} not found")
    submitted_at = _session_start(targets) + timedelta(hours=1)
    assignment.file_name = file_name
    assignment.submitted_at = submitted_at
    assignment.attempt_count += 1
    assignment.submission_status = "late" if submitted_at > assignment.due_at else "submitted"


def _report(initial, state, targets):
    task = get_task("lms_final_exam_prep_plan")
    agent_diff = compute_diff(initial, state)
    return match_diff(
        agent_diff,
        task.canonical_diff,
        targets=dict(targets),
        initial=initial,
        final=state,
        session_start=_session_start(targets),
    )


def test_seed_integrity_exposes_distinct_course_sets():
    _, _, targets, _, state = _setup_session(seed=42)
    impossible = _ids(targets["impossible_b_course_ids"])
    impossible_enrollments = _ids(targets["impossible_b_enrollment_ids"])
    achievable = _ids(targets["achievable_course_ids"])
    achievable_assignments = _ids(targets["achievable_final_exam_assignment_ids"])
    final_exam_ids = _ids(targets["final_exam_assignment_ids"])

    assert impossible, "seed must expose at least one impossible-B course"
    assert achievable, "seed must expose at least one achievable course"
    assert set(impossible).isdisjoint(achievable), "course sets must be disjoint"
    assert len(impossible_enrollments) == len(impossible), "every impossible course must map to one enrollment"
    assert len(achievable_assignments) == len(achievable), "every achievable course must map to one final exam assignment"
    assert len(final_exam_ids) == len(state.courses), "every course should have a final exam target"
    for assignment_id in final_exam_ids:
        assignment = state.get_assignment(assignment_id)
        assert assignment is not None
        assert assignment.type == "exam"
        assert assignment.weight_category == "final"
    for enrollment_id in impossible_enrollments:
        enrollment = next((e for e in state.enrollments if e.id == enrollment_id), None)
        assert enrollment is not None
        assert enrollment.status == "enrolled"
    for assignment_id in achievable_assignments:
        assignment = state.get_assignment(assignment_id)
        assert assignment is not None
        assert assignment.type == "exam"
        assert assignment.weight_category == "final"


def test_correct_trajectory_passes():
    _, _, targets, initial, state = _setup_session(seed=42)

    for enrollment_id in _ids(targets["impossible_b_enrollment_ids"]):
        _drop_enrollment(state, enrollment_id)
    for assignment_id in _ids(targets["achievable_final_exam_assignment_ids"]):
        _submit_exam_prep(state, targets, assignment_id)

    report = _report(initial, state, targets)
    assert report.passed is True, f"failures: {report.failures}"
    assert report.score == 1.0, f"expected 1.0, got {report.score}"


def test_no_mutation_fails():
    _, _, targets, initial, state = _setup_session(seed=42)

    report = _report(initial, state, targets)
    assert report.passed is False, "doing nothing should fail"
    assert report.score == 0.0, f"expected 0.0, got {report.score}"


def test_wrong_course_dropped_fails():
    _, _, targets, initial, state = _setup_session(seed=42)

    wrong_enrollment_id = next(
        enrollment.id
        for enrollment in state.enrollments
        if enrollment.id not in _ids(targets["impossible_b_enrollment_ids"])
    )
    _drop_enrollment(state, wrong_enrollment_id)

    report = _report(initial, state, targets)
    assert report.passed is False, "dropping an achievable course should fail"


def test_wrong_final_exam_file_fails():
    _, _, targets, initial, state = _setup_session(seed=42)

    for enrollment_id in _ids(targets["impossible_b_enrollment_ids"]):
        _drop_enrollment(state, enrollment_id)
    achievable_assignments = _ids(targets["achievable_final_exam_assignment_ids"])
    assert achievable_assignments, "seed must expose at least one achievable assignment"

    _submit_exam_prep(state, targets, achievable_assignments[0], file_name="wrong_upload.pdf")
    for assignment_id in achievable_assignments[1:]:
        _submit_exam_prep(state, targets, assignment_id)

    report = _report(initial, state, targets)
    assert report.passed is False, "submitting the final exam with the wrong file should fail"


def test_extra_collateral_mutation_fails():
    _, _, targets, initial, state = _setup_session(seed=42)

    for enrollment_id in _ids(targets["impossible_b_enrollment_ids"]):
        _drop_enrollment(state, enrollment_id)
    for assignment_id in _ids(targets["achievable_final_exam_assignment_ids"]):
        _submit_exam_prep(state, targets, assignment_id)
    state.courses[0].title = state.courses[0].title + " (edited)"

    report = _report(initial, state, targets)
    assert report.passed is False, (
        "editing a course while completing the final exam prep plan should "
        "violate the invariant sweep"
    )
