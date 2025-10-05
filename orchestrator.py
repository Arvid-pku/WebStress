import json
import os
import time
from typing import Any, Dict, Tuple

from simulator_core import SimulatorCore
from judge import Judge
from proposer import Proposer


class DummyAgent:
    """A minimal agent that emits a single action causing a rejection, then stops."""

    def act(self, observation: Dict[str, Any], instruction: Dict[str, Any]) -> Dict[str, Any]:
        # Prefer element_id targeting per spec
        # This naive agent first tries to click confirm; user can wire own agent.
        return {"type": "click", "target": {"element_id": "confirm_payment_btn"}}


def run_episode(instr: Dict[str, Any], seed: int, fidelity: str = "low", steps_limit: int = 1) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    sim = SimulatorCore()
    agent = DummyAgent()
    judge = Judge()

    obs, start_digest, episode_id = sim.reset(instr, seed, fidelity)
    episode_log: Dict[str, Any] = {
        "episode_id": episode_id,
        "instruction_id": instr.get("id"),
        "seed": seed,
        "start_digest": start_digest,
        "steps": [],
    }

    done = False
    steps = 0
    while not done and steps < steps_limit:
        action = agent.act(obs, instr)
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        out = sim.step(episode_id, action, now, 0)

        episode_log["steps"].append({
            "t": now,
            "action": action,
            "internal_result": out["internal_result"],
            "event_log": out["event_log"],
            "state_diff": out["state_diff"],
            "state_digest": out["state_digest"],
            "observation": out["observation"],  # store agent-visible obs for replay/judge
        })
        obs = out["observation"]
        done = bool(out.get("terminal"))
        steps += 1

    end_summary = sim.get_state_summary(episode_id)
    start_summary = {"start_digest": start_digest}
    judgement = judge.evaluate(instr, start_summary, end_summary, episode_log)
    return episode_log, judgement


def save_episode(out_dir: str, episode_log: Dict[str, Any], judgement: Dict[str, Any]) -> None:
    os.makedirs(out_dir, exist_ok=True)
    eid = episode_log.get("episode_id", "episode")
    with open(os.path.join(out_dir, f"{eid}.log.json"), "w", encoding="utf-8") as f:
        json.dump(episode_log, f, indent=2, sort_keys=True)
    with open(os.path.join(out_dir, f"{eid}.judge.json"), "w", encoding="utf-8") as f:
        json.dump(judgement, f, indent=2, sort_keys=True)


if __name__ == "__main__":
    # Example dry run
    instruction = {
        "id": "demo",
        "description": "Trigger validation error.",
        "template": "flight_booking",
        "difficulty": "easy",
        "time_limit": 30,
        "success_criteria": [
            {"predicate": "element_text_contains:Invalid card number", "weight": 1.0}
        ],
    }
    log, judge_out = run_episode(instruction, seed=123, fidelity="low", steps_limit=1)
    save_episode("runs", log, judge_out)
    print("Saved episode to 'runs/'")

