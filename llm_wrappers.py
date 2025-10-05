import json
import os
from typing import Any, Dict, List, Optional

from llm_client import LLMClient
from validation import validate_action, validate_instruction, validate_judge_output


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")


class LLMAgent:
    def __init__(self, model: Optional[str] = None, temperature: float = 0.2, seed: Optional[int] = None):
        self.client = LLMClient(model=model, temperature=temperature, seed=seed)
        self.system = _read(os.path.join(PROMPTS_DIR, "agent.system.txt"))

    def act(self, observation: Dict[str, Any], instruction: Dict[str, Any]) -> Dict[str, Any]:
        payload = {"instruction": instruction, "observation": observation}
        out = self.client.complete_json(system_prompt=self.system, user_json=payload, max_retries=2)
        validate_action(out)
        return out


class LLMJudge:
    def __init__(self, model: Optional[str] = None, temperature: float = 0.0, seed: Optional[int] = None):
        self.client = LLMClient(model=model, temperature=temperature, seed=seed)
        self.system = _read(os.path.join(PROMPTS_DIR, "judge.system.txt"))

    def evaluate(self, instruction: Dict[str, Any], start_state_summary: Dict[str, Any], end_state_summary: Dict[str, Any], episode_log: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "instruction": instruction,
            "start_state_summary": start_state_summary,
            "end_state_summary": end_state_summary,
            "episode_log": episode_log,
        }
        out = self.client.complete_json(system_prompt=self.system, user_json=payload, max_retries=2)
        validate_judge_output(out)
        return out


class LLMProposer:
    def __init__(self, model: Optional[str] = None, temperature: float = 0.7, seed: Optional[int] = None):
        self.client = LLMClient(model=model, temperature=temperature, seed=seed)
        self.system = _read(os.path.join(PROMPTS_DIR, "proposer.system.txt"))

    def propose_next(self, agent_id: str, recent_episodes: List[Dict[str, Any]], global_task_pool: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        payload = {"agent_id": agent_id, "recent_episodes": recent_episodes, "global_task_pool": global_task_pool or []}
        out = self.client.complete_json(system_prompt=self.system, user_json=payload, max_retries=2)
        validate_instruction(out)
        return out


# Simulator wrapper note: The deterministic core is already implemented in simulator_core.SimulatorCore.
# If desired, wire an LLM in 'high' fidelity mode to generate richer internal reasons/text while preserving
# state transitions in the deterministic core. This keeps determinism at temp=0 while leveraging LLM content.

