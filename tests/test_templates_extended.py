import time

from simulator_core import SimulatorCore


def test_email_client_send_flow_creates_outbox_file():
    sim = SimulatorCore()
    instr = {"id": "e1", "description": "", "template": "email_client", "difficulty": "easy", "time_limit": 30, "success_criteria": []}
    obs, d, eid = sim.reset(instr, seed=11)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # Open compose
    sim.step(eid, {"type": "click", "target": {"element_id": "compose_btn"}}, now, 0)
    # Fill fields
    sim.step(eid, {"type": "input_text", "target": {"element_id": "to_input"}, "text": "user@example.com"}, now, 0)
    sim.step(eid, {"type": "input_text", "target": {"element_id": "subject_input"}, "text": "Hi"}, now, 0)
    sim.step(eid, {"type": "input_text", "target": {"element_id": "body_input"}, "text": "Hello"}, now, 0)
    # Send
    out = sim.step(eid, {"type": "click", "target": {"element_id": "send_btn"}}, now, 0)
    # Verify filesystem in state summary
    end_summary = sim.get_state_summary(eid)
    assert "/home/user/outbox/sent-11.eml" in set(end_summary.get("filesystem_paths", []))
    # Observation should have status banner visible
    obs2 = out["observation"]
    assert any(el.get("element_id") == "status_banner" and el.get("attributes", {}).get("visible") for el in obs2.get("ui_elements", []))


def test_file_manager_new_file_creation():
    sim = SimulatorCore()
    instr = {"id": "f1", "description": "", "template": "file_manager", "difficulty": "easy", "time_limit": 30, "success_criteria": []}
    obs, d, eid = sim.reset(instr, seed=22)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    out = sim.step(eid, {"type": "click", "target": {"element_id": "new_file_btn"}}, now, 0)
    end_summary = sim.get_state_summary(eid)
    assert "/home/user/untitled.txt" in set(end_summary.get("filesystem_paths", []))
    # Observation shows a status banner
    obs2 = out["observation"]
    assert any(el.get("element_id") == "status_banner" and el.get("attributes", {}).get("visible") for el in obs2.get("ui_elements", []))

