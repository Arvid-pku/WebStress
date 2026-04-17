"""End-to-end tests for booking_save_property canonical_diff."""

from datetime import datetime, timezone
from pathlib import Path
import random

from webagentbench.backend.models.booking import BookingState, SavedList
from webagentbench.backend.seeder import FakeDataGenerator
from webagentbench.backend.seeders.booking import BookingSeedRunner
from webagentbench.evaluator_diff import compute_diff, match_diff
from webagentbench.tasks._schema import TaskDefinition


_TASK_YAML = Path(__file__).resolve().parents[1] / "tasks" / "booking" / "booking_save_property.yaml"
TASK_ID = "booking_save_property"


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


def _add_property_to_list(state, list_id: str, property_id: str) -> None:
    sl = next(s for s in state.saved_lists if s.id == list_id)
    if property_id not in sl.property_ids:
        sl.property_ids.append(property_id)
        sl.updated_at = datetime.now(timezone.utc)


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
        _add_property_to_list(state, targets["list_id"], targets["property_id"])
        report = _evaluate(task, initial, state, targets)
        assert report.passed is True, f"seed {seed}: failures={report.failures}"
        assert report.score == 1.0, f"seed {seed}: expected 1.0, got {report.score}"


def test_no_mutation_fails():
    task, targets, initial, state = _setup_session(0)
    report = _evaluate(task, initial, state, targets)
    assert report.passed is False
    assert report.score == 0.0


def test_wrong_property_fails():
    task, targets, initial, state = _setup_session(0)
    decoy = next(p for p in state.properties if p.id != targets["property_id"])
    _add_property_to_list(state, targets["list_id"], decoy.id)
    report = _evaluate(task, initial, state, targets)
    assert report.passed is False


def test_wrong_list_fails():
    task, targets, initial, state = _setup_session(0)
    wrong_list = SavedList(
        id=state._next_id("list"),
        name="Other List",
        property_ids=[],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    state.saved_lists.append(wrong_list)
    _add_property_to_list(state, wrong_list.id, targets["property_id"])
    report = _evaluate(task, initial, state, targets)
    assert report.passed is False


def test_extra_property_fails():
    task, targets, initial, state = _setup_session(0)
    decoy = next(p for p in state.properties if p.id != targets["property_id"])
    _add_property_to_list(state, targets["list_id"], targets["property_id"])
    _add_property_to_list(state, targets["list_id"], decoy.id)
    report = _evaluate(task, initial, state, targets)
    assert report.passed is False
