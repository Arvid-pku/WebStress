import time

from simulator_core import SimulatorCore
from judge import Judge


def test_observation_no_internal_reason():
    sim = SimulatorCore()
    instr = {"id": "t1", "description": "", "template": "desktop", "difficulty": "easy", "time_limit": 30, "success_criteria": []}
    obs, start_digest, eid = sim.reset(instr, seed=42)
    # Click a missing element to trigger rejection
    out = sim.step(eid, {"type": "click", "target": {"element_id": "missing_element"}}, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), 0)
    observation = out["observation"]

    assert "internal_result" not in observation
    assert "reason" not in observation
    # Rejection percepts: flash and/or beep
    assert (observation.get("meta", {}).get("event_visuals") == "flash") or (len(observation.get("audio_events", [])) > 0)


def test_simulator_deterministic():
    sim1 = SimulatorCore()
    sim2 = SimulatorCore()
    instr = {"id": "t2", "description": "", "template": "desktop", "difficulty": "easy", "time_limit": 30, "success_criteria": []}
    _, d1, _ = sim1.reset(instr, seed=123)
    _, d2, _ = sim2.reset(instr, seed=123)
    assert d1 == d2


def test_internal_logging_present():
    sim = SimulatorCore()
    instr = {"id": "t3", "description": "", "template": "desktop", "difficulty": "easy", "time_limit": 30, "success_criteria": []}
    obs, d, eid = sim.reset(instr, seed=7)
    out = sim.step(eid, {"type": "double_click", "target": {"element_id": "icon_settings"}}, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), 0)
    assert "internal_result" in out
    assert "event_log" in out
    assert "state_diff" in out
    assert "state_digest" in out


def test_judge_consistent():
    judge = Judge()
    instruction = {"id": "t4", "description": "Expect Settings text present", "template": "desktop", "difficulty": "easy", "time_limit": 30, "success_criteria": [{"predicate": "element_text_contains:Settings", "weight": 1.0}]}

    # Simulate identical logs (with a final observation containing the target text)
    obs = {
        "timestamp": "2025-01-01T00:00:00Z",
        "screenshot_id": "s-desktop-1",
        "ui_elements": [
            {"element_id": "settings_header", "role": "heading", "text": "Settings", "attributes": {"visible": True}}
        ],
        "audio_events": [],
        "meta": {"page": "settings"}
    }
    log1 = {"steps": [{"observation": obs, "internal_result": {"result": "rejected", "reason": ""}}]}
    log2 = {"steps": [{"observation": obs, "internal_result": {"result": "rejected", "reason": ""}}]}
    start = {"start_digest": "x"}
    end = {"filesystem_paths": []}
    j1 = judge.evaluate(instruction, start, end, log1)
    j2 = judge.evaluate(instruction, start, end, log2)
    assert j1["score"] == j2["score"]
