import json
import sys
from typing import Any, Dict

from simulator_core import SimulatorCore
try:
    from llm_wrappers import LLMSimulator  # optional
except Exception:
    LLMSimulator = None  # type: ignore


def verify_episode(log: Dict[str, Any]) -> bool:
    instr_id = log.get("instruction_id", "instr")
    seed = log.get("seed", 0)
    # Minimal instruction placeholder; template inferred by simulator default
    instr = {"id": instr_id, "template": "desktop", "description": "", "difficulty": "easy", "time_limit": 30, "success_criteria": []}

    base = SimulatorCore()
    use_llm = (log.get("components", {}) or {}).get("simulator") == "llm" and LLMSimulator is not None
    sim = LLMSimulator(core=base, model=None, seed=seed) if use_llm else base
    obs, start_digest, episode_id = sim.reset(instr, seed)
    if start_digest != log.get("start_digest"):
        return False
    ok = True
    for step in log.get("steps", []):
        action = step.get("action")
        out = sim.step(episode_id, action, step.get("t", ""), 0)
        if out.get("state_digest") != step.get("state_digest"):
            ok = False
            break
    return ok


def main():
    if len(sys.argv) < 2:
        print("Usage: python replay.py path/to/episode.log.json")
        sys.exit(1)
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        log = json.load(f)
    ok = verify_episode(log)
    print("replay_verification:", "ok" if ok else "mismatch")


if __name__ == "__main__":
    main()
