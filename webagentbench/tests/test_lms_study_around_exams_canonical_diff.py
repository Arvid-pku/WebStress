"""End-to-end tests for lms_study_around_exams canonical_diff."""

from webagentbench.backend.state import SessionManager
from webagentbench.eval_core import compute_diff, match_diff
from webagentbench.tasks._registry import get_task


def _setup_session(seed: int = 42):
    sm = SessionManager()
    sid, targets, _ = sm.create_session(
        env_id="lms",
        task_id="lms_study_around_exams",
        seed=seed,
    )
    initial = sm.get_initial_snapshot(sid)
    state = sm.get_state(sid)
    return sm, sid, dict(targets), initial, state


def _target_ids(targets: dict[str, str]) -> list[str]:
    raw = targets["unread_announcement_ids"]
    return [aid.strip() for aid in raw.split(",") if aid.strip()]


def _announcement_ids(state) -> list[str]:
    return [announcement.id for announcement in state.announcements]


def _announcement(state, announcement_id: str):
    announcement = state.get_announcement(announcement_id)
    if announcement is None:
        raise ValueError(f"announcement {announcement_id!r} not found")
    return announcement


def _mark_read(state, announcement_id: str) -> None:
    _announcement(state, announcement_id).is_read = True


def _set_wrong_field(state, announcement_id: str) -> None:
    _announcement(state, announcement_id).is_read = "yes"


def _set_title(state, announcement_id: str, title: str) -> None:
    _announcement(state, announcement_id).title = title


def _run_report(initial, state, targets):
    task = get_task("lms_study_around_exams")
    agent_diff = compute_diff(initial, state)
    return match_diff(
        agent_diff,
        task.canonical_diff,
        targets=dict(targets),
        initial=initial,
        final=state,
    )


def test_correct_trajectory_passes():
    sm, sid, targets, initial, state = _setup_session()

    for announcement_id in _target_ids(targets):
        _mark_read(state, announcement_id)

    report = _run_report(initial, state, targets)
    assert report.passed is True, f"failures: {report.failures}"
    assert report.score == 1.0, f"expected 1.0, got {report.score}"


def test_no_mutation_fails():
    sm, sid, targets, initial, state = _setup_session()

    report = _run_report(initial, state, targets)
    assert report.passed is False, "doing nothing should fail"
    assert report.score == 0.0, f"expected 0.0, got {report.score}"


def test_wrong_id_fails():
    sm, sid, targets, initial, state = _setup_session()

    target_ids = set(_target_ids(targets))
    wrong_id = next(aid for aid in _announcement_ids(state) if aid not in target_ids)
    _set_wrong_field(state, wrong_id)

    report = _run_report(initial, state, targets)
    assert report.passed is False, "mutating the wrong announcement should fail"


def test_wrong_field_fails():
    sm, sid, targets, initial, state = _setup_session()

    target_id = _target_ids(targets)[0]
    _set_wrong_field(state, target_id)

    report = _run_report(initial, state, targets)
    assert report.passed is False, "setting the wrong field value should fail"


def test_extra_mutation_fails():
    sm, sid, targets, initial, state = _setup_session()

    for announcement_id in _target_ids(targets):
        _mark_read(state, announcement_id)

    target_ids = set(_target_ids(targets))
    wrong_id = next(aid for aid in _announcement_ids(state) if aid not in target_ids)
    _set_title(state, wrong_id, "Edited announcement should not be touched")

    report = _run_report(initial, state, targets)
    assert report.passed is False, "an extra mutation should violate the invariant"
