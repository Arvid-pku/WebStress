import argparse
import json
import os
import time
from typing import Any, Dict, Tuple

from simulator_core import SimulatorCore
from judge import Judge
from proposer import Proposer

USE_LLM_AGENT = os.getenv("USE_LLM_AGENT") == "1"
USE_LLM_JUDGE = os.getenv("USE_LLM_JUDGE") == "1"
USE_LLM_PROPOSER = os.getenv("USE_LLM_PROPOSER") == "1"
USE_LLM_SIMULATOR = os.getenv("USE_LLM_SIMULATOR") == "1"

# Always attempt to import LLM wrappers; they lazily create clients.
try:
    from llm_wrappers import LLMAgent, LLMJudge, LLMProposer, LLMSimulator
except Exception:
    LLMAgent = None  # type: ignore
    LLMJudge = None  # type: ignore
    LLMProposer = None  # type: ignore
    LLMSimulator = None  # type: ignore


class DummyAgent:
    """A minimal agent that emits a single action causing a rejection, then stops."""

    def act(self, observation: Dict[str, Any], instruction: Dict[str, Any]) -> Dict[str, Any]:
        # Prefer element_id targeting per spec
        # This naive agent double-clicks the Settings icon on desktop.
        return {"type": "double_click", "target": {"element_id": "icon_settings"}}


def run_episode(instr: Dict[str, Any], seed: int, fidelity: str = "low", steps_limit: int = 1, stop_on_success: bool = False, success_threshold: float = 0.99) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    base_sim = SimulatorCore()
    # Choose simulator
    if USE_LLM_SIMULATOR and 'LLMSimulator' in globals() and LLMSimulator is not None:
        sim = LLMSimulator(core=base_sim, model=os.getenv("LLM_MODEL"), seed=seed)
    else:
        sim = base_sim
    # Choose agent
    if USE_LLM_AGENT and 'LLMAgent' in globals() and LLMAgent is not None:
        agent = LLMAgent(model=os.getenv("LLM_MODEL"), temperature=float(os.getenv("AGENT_TEMP", "1")), seed=seed)
    else:
        agent = DummyAgent()
    # Choose judge
    if USE_LLM_JUDGE and 'LLMJudge' in globals() and LLMJudge is not None:
        judge = LLMJudge(model=os.getenv("LLM_MODEL"), temperature=0.0, seed=seed)
    else:
        judge = Judge()

    obs, start_digest, episode_id = sim.reset(instr, seed, fidelity)
    episode_log: Dict[str, Any] = {
        "episode_id": episode_id,
        "instruction_id": instr.get("id"),
        "seed": seed,
        "start_digest": start_digest,
        "steps": [],
        "components": {
            "simulator": "llm" if USE_LLM_SIMULATOR else "core",
            "agent": "llm" if USE_LLM_AGENT else "dummy",
            "judge": "llm" if USE_LLM_JUDGE else "det",
            "proposer": "llm" if USE_LLM_PROPOSER else "simple",
        },
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
        if stop_on_success:
            end_summary = sim.get_state_summary(episode_id)
            start_summary = {"start_digest": start_digest}
            score_now = judge.evaluate(instr, start_summary, end_summary, episode_log)["score"]
            if score_now >= success_threshold:
                break

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
    parser = argparse.ArgumentParser(description="Run an episode with optional LLM components.")
    parser.add_argument("--seed", type=int, default=int(os.getenv("SEED", "123")))
    parser.add_argument("--fidelity", type=str, default=os.getenv("FIDELITY", "low"), choices=["low", "medium", "high"])
    parser.add_argument("--steps", type=int, default=int(os.getenv("STEPS", "1")))
    parser.add_argument("--llm-agent", action="store_true", default=USE_LLM_AGENT)
    parser.add_argument("--llm-judge", action="store_true", default=USE_LLM_JUDGE)
    parser.add_argument("--llm-proposer", action="store_true", default=USE_LLM_PROPOSER)
    parser.add_argument("--llm-simulator", action="store_true", default=USE_LLM_SIMULATOR)
    parser.add_argument("--instr-file", type=str, default=os.getenv("INSTR_FILE"), help="Path to instruction JSON file")
    parser.add_argument("--instr-json", type=str, default=os.getenv("INSTR_JSON"), help="Instruction JSON string")
    parser.add_argument("--instruction", "--instr-text", dest="instr_text", type=str, default=os.getenv("INSTRUCTION"), help="Freeform instruction text to compile")
    parser.add_argument("--task", type=str, default=os.getenv("TASK"), help="Preset task name (e.g., open-settings)")
    parser.add_argument("--stop-on-success", action="store_true", help="Stop the episode early when success criteria are met")
    parser.add_argument("--success-threshold", type=float, default=float(os.getenv("SUCCESS_THRESHOLD", "0.99")), help="Score threshold to stop when --stop-on-success is set")
    args = parser.parse_args()

    # Reflect CLI toggles to module-level flags
    USE_LLM_AGENT = args.llm_agent
    USE_LLM_JUDGE = args.llm_judge
    USE_LLM_PROPOSER = args.llm_proposer
    USE_LLM_SIMULATOR = args.llm_simulator

    def preset_instruction(name: str) -> Dict[str, Any]:
        name = (name or "").strip().lower()
        if name == "open-settings":
            return {
                "id": "open-settings",
                "description": "Open the Settings from the desktop.",
                "template": "desktop",
                "difficulty": "easy",
                "time_limit": 45,
                "success_criteria": [
                    {"predicate": "element_text_contains:Settings", "weight": 1.0}
                ],
            }
        if name == "open-files":
            return {
                "id": "open-files",
                "description": "Open the Files app from the desktop.",
                "template": "desktop",
                "difficulty": "easy",
                "time_limit": 45,
                "success_criteria": [
                    {"predicate": "element_text_contains:Files", "weight": 1.0}
                ],
            }
        if name == "open-browser":
            return {
                "id": "open-browser",
                "description": "Open the Browser from the desktop.",
                "template": "desktop",
                "difficulty": "easy",
                "time_limit": 45,
                "success_criteria": [
                    {"predicate": "element_text_contains:Browser", "weight": 1.0}
                ],
            }
        # default preset
        return {
            "id": "desktop_demo",
            "description": "Open the Settings from the desktop.",
            "template": "desktop",
            "difficulty": "easy",
            "time_limit": 30,
            "success_criteria": [
                {"predicate": "element_text_contains:Settings", "weight": 1.0}
            ],
        }

    # Resolve instruction from CLI/env
    instruction: Dict[str, Any]
    if args.instr_file:
        with open(args.instr_file, "r", encoding="utf-8") as f:
            instruction = json.load(f)
    elif args.instr_json:
        instruction = json.loads(args.instr_json)
    elif args.instr_text:
        # Compile freeform instruction to Instruction JSON
        try:
            from llm_wrappers import InstructionCompiler
            compiler = InstructionCompiler(model=os.getenv("LLM_MODEL"), temperature=0.0, seed=args.seed)
            instruction = compiler.compile(args.instr_text)
        except Exception:
            # Heuristic fallback for desktop
            txt = (args.instr_text or "").lower()
            if "settings" in txt:
                instruction = {
                    "id": "open-settings",
                    "description": args.instr_text,
                    "template": "desktop",
                    "difficulty": "easy",
                    "time_limit": 60,
                    "success_criteria": [{"predicate": "element_text_contains:Settings", "weight": 1.0}],
                }
            elif "files" in txt:
                instruction = {
                    "id": "open-files",
                    "description": args.instr_text,
                    "template": "desktop",
                    "difficulty": "easy",
                    "time_limit": 60,
                    "success_criteria": [{"predicate": "element_text_contains:Files", "weight": 1.0}],
                }
            elif "browser" in txt:
                instruction = {
                    "id": "open-browser",
                    "description": args.instr_text,
                    "template": "desktop",
                    "difficulty": "easy",
                    "time_limit": 60,
                    "success_criteria": [{"predicate": "element_text_contains:Browser", "weight": 1.0}],
                }
            else:
                instruction = {
                    "id": "desktop-goal",
                    "description": args.instr_text,
                    "template": "desktop",
                    "difficulty": "medium",
                    "time_limit": 90,
                    "success_criteria": [{"predicate": "element_text_contains:Done|Success|Settings|Files|Browser", "weight": 1.0}],
                }
    elif args.task:
        instruction = preset_instruction(args.task)
    else:
        instruction = preset_instruction("open-settings")
    print(
        "Components:",
        f"simulator={'LLM' if USE_LLM_SIMULATOR else 'core'}",
        f"agent={'LLM' if USE_LLM_AGENT else 'dummy'}",
        f"judge={'LLM' if USE_LLM_JUDGE else 'det'}",
        f"proposer={'LLM' if USE_LLM_PROPOSER else 'simple'}",
    )
    log, judge_out = run_episode(instruction, seed=args.seed, fidelity=args.fidelity, steps_limit=args.steps, stop_on_success=args.stop_on_success, success_threshold=args.success_threshold)
    save_episode("runs", log, judge_out)
    print("Saved episode to 'runs/'")
