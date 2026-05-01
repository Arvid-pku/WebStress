"""End-to-end tests for booking_change_language canonical_diff.

Hazard Class 14: single-instance state fields (``state.settings``) aren't
visible to ``compute_diff`` so the task is verified via ``constraints:``.
Constraints are penalty-only, so the do-nothing trajectory scores > 0
after penalty deductions but still has ``passed is False`` via the
emitted Failure entries.
"""

from pathlib import Path
import random

from webagentbench.backend.models.booking import BookingState
from webagentbench.backend.seeder import FakeDataGenerator
from webagentbench.backend.seeders.booking import BookingSeedRunner
from webagentbench.eval_core import compute_diff, match_diff
from webagentbench.tasks._schema import TaskDefinition


_TASK_YAML = Path(__file__).resolve().parents[1] / "tasks" / "booking" / "booking_change_language.yaml"
TASK_ID = "booking_change_language"


def _setup_session(seed: int):
    task = TaskDefinition.from_yaml(_TASK_YAML)
    runner = BookingSeedRunner()
    seeded_data, targets = runner.run(
        task=task,
        seed=seed,
        fake=FakeDataGenerator(seed),
        rng=random.Random(seed),
    )
    state = BookingState.model_validate(seeded_data)
    initial = state.model_copy(deep=True)
    return task, dict(targets), initial, state


def _evaluate(task, initial, state, targets):
    agent_diff = compute_diff(initial, state)
    return match_diff(
        agent_diff,
        task.canonical_diff,
        targets=dict(targets),
        initial=initial,
        final=state,
    )


def test_correct_trajectory_passes():
    for seed in (0, 3, 42):
        task, targets, initial, state = _setup_session(seed)
        state.settings.language = "French"
        report = _evaluate(task, initial, state, targets)
        assert report.passed is True, f"seed {seed}: failures={report.failures}"
        assert report.score == 1.0, f"seed {seed}: expected 1.0, got {report.score}"


def test_no_mutation_fails():
    task, targets, initial, state = _setup_session(0)
    report = _evaluate(task, initial, state, targets)
    # Class 14: pure-constraint tasks can't meet the Class 1 "score == 0"
    # guard. passed=False is still correct because the critical failure
    # emits a Failure entry.
    assert report.passed is False


def test_wrong_language_fails():
    task, targets, initial, state = _setup_session(0)
    state.settings.language = "Spanish"
    report = _evaluate(task, initial, state, targets)
    assert report.passed is False


def test_currency_change_fails():
    task, targets, initial, state = _setup_session(0)
    state.settings.language = "French"
    state.settings.currency = "EUR"
    report = _evaluate(task, initial, state, targets)
    assert report.passed is False
