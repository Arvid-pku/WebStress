import time

from simulator_core import SimulatorCore
from judge import Judge


def test_observation_no_internal_reason():
    sim = SimulatorCore()
    instr = {
        "id": "t1",
        "description": "Trigger validation error",
        "template": "flight_booking",
        "difficulty": "easy",
        "time_limit": 30,
        "success_criteria": []
    }
    obs, start_digest, eid = sim.reset(instr, seed=42)
    out = sim.step(eid, {"type": "click", "target": {"element_id": "confirm_payment_btn"}}, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), 0)
    observation = out["observation"]

    assert "internal_result" not in observation
    assert "reason" not in observation
    # Error banner appears perceptually
    assert any(el.get("element_id") == "error_banner" and el.get("attributes", {}).get("visible") for el in observation.get("ui_elements", []))


def test_simulator_deterministic():
    sim1 = SimulatorCore()
    sim2 = SimulatorCore()
    instr = {"id": "t2", "description": "", "template": "flight_booking", "difficulty": "easy", "time_limit": 30, "success_criteria": []}
    _, d1, _ = sim1.reset(instr, seed=123)
    _, d2, _ = sim2.reset(instr, seed=123)
    assert d1 == d2


def test_internal_logging_present():
    sim = SimulatorCore()
    instr = {"id": "t3", "description": "", "template": "flight_booking", "difficulty": "easy", "time_limit": 30, "success_criteria": []}
    obs, d, eid = sim.reset(instr, seed=7)
    out = sim.step(eid, {"type": "click", "target": {"element_id": "confirm_payment_btn"}}, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), 0)
    assert "internal_result" in out
    assert "event_log" in out
    assert "state_diff" in out
    assert "state_digest" in out


def test_judge_consistent():
    judge = Judge()
    instruction = {
        "id": "t4",
        "description": "Expect error banner after invalid confirm",
        "template": "flight_booking",
        "difficulty": "easy",
        "time_limit": 30,
        "success_criteria": [
            {"predicate": "element_text_contains:Invalid card number", "weight": 1.0}
        ]
    }

    # Simulate identical logs (with a final observation containing the error text)
    obs = {
        "timestamp": "2025-01-01T00:00:00Z",
        "screenshot_id": "s-flight_booking-1",
        "ui_elements": [
            {"element_id": "error_banner", "role": "banner", "text": "Invalid card number", "attributes": {"visible": True}}
        ],
        "audio_events": [],
        "meta": {"page": "checkout"}
    }
    log1 = {"steps": [{"observation": obs, "internal_result": {"result": "rejected", "reason": ""}}]}
    log2 = {"steps": [{"observation": obs, "internal_result": {"result": "rejected", "reason": ""}}]}
    start = {"start_digest": "x"}
    end = {"filesystem_paths": []}
    j1 = judge.evaluate(instruction, start, end, log1)
    j2 = judge.evaluate(instruction, start, end, log2)
    assert j1["score"] == j2["score"]

