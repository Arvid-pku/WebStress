"""End-to-end tests for booking_send_message canonical_diff."""

from datetime import datetime, timezone
from pathlib import Path
import random

from webagentbench.backend.models.booking import BookingState, Message
from webagentbench.backend.seeder import FakeDataGenerator
from webagentbench.backend.seeders.booking import BookingSeedRunner
from webagentbench.eval_core import compute_diff, match_diff
from webagentbench.tasks._schema import TaskDefinition


_TASK_YAML = Path(__file__).resolve().parents[1] / "tasks" / "booking" / "booking_send_message.yaml"
TASK_ID = "booking_send_message"


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


def _send_correct_message(state, targets) -> Message:
    prop = state.get_property(targets["property_id"])
    msg = Message(
        id=state._next_id("msg"),
        property_id=targets["property_id"],
        property_name=prop.name if prop else targets.get("property_name", ""),
        reservation_id=targets.get("reservation_id", ""),
        subject="Check-in time inquiry",
        body=(
            "Hello, could you please let me know the earliest check-in time "
            "available? Thank you."
        ),
        sender="guest",
        read=False,
        created_at=datetime.now(timezone.utc),
    )
    state.messages.append(msg)
    return msg


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
        _send_correct_message(state, targets)
        report = _evaluate(task, initial, state, targets)
        assert report.passed is True, f"seed {seed}: failures={report.failures}"
        assert report.score == 1.0, f"seed {seed}: expected 1.0, got {report.score}"


def test_no_mutation_fails():
    task, targets, initial, state = _setup_session(0)
    report = _evaluate(task, initial, state, targets)
    assert report.passed is False, "doing nothing should fail"
    assert report.score == 0.0, f"expected 0.0, got {report.score}"


def test_wrong_subject_fails():
    task, targets, initial, state = _setup_session(0)
    prop = state.get_property(targets["property_id"])
    state.messages.append(Message(
        id=state._next_id("msg"),
        property_id=targets["property_id"],
        property_name=prop.name,
        reservation_id=targets.get("reservation_id", ""),
        subject="Room upgrade request",
        body="Please upgrade my room. Thank you, and the earliest check-in time please.",
        sender="guest",
        read=False,
        created_at=datetime.now(timezone.utc),
    ))
    report = _evaluate(task, initial, state, targets)
    assert report.passed is False, "wrong subject should fail"


def test_wrong_property_fails():
    task, targets, initial, state = _setup_session(0)
    other_prop = next(p for p in state.properties if p.id != targets["property_id"])
    state.messages.append(Message(
        id=state._next_id("msg"),
        property_id=other_prop.id,
        property_name=other_prop.name,
        reservation_id="",
        subject="Check-in time inquiry",
        body="Hello, what is the earliest check-in time? Thank you.",
        sender="guest",
        read=False,
        created_at=datetime.now(timezone.utc),
    ))
    report = _evaluate(task, initial, state, targets)
    assert report.passed is False, "wrong property should fail"


def test_extra_message_fails():
    task, targets, initial, state = _setup_session(0)
    _send_correct_message(state, targets)
    _send_correct_message(state, targets)  # duplicate
    report = _evaluate(task, initial, state, targets)
    assert report.passed is False, "duplicate message should fail"


def test_modifying_existing_message_fails():
    task, targets, initial, state = _setup_session(0)
    _send_correct_message(state, targets)
    state.messages[0].read = not state.messages[0].read
    report = _evaluate(task, initial, state, targets)
    assert report.passed is False, "modifying existing message should fail"
