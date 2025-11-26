import argparse
import json
import os
import sys
from typing import Any, Dict, Optional


def _load_first_instruction(jsonl_path: str, instr_id: Optional[str] = None) -> Dict[str, Any]:
    with open(jsonl_path, "r", encoding="utf-8") as f:
        if instr_id:
            for line in f:
                s = (line or "").strip()
                if not s:
                    continue
                try:
                    obj = json.loads(s)
                except Exception:
                    continue
                if isinstance(obj, dict) and str(obj.get("id")) == str(instr_id):
                    return obj
            raise RuntimeError(f"Instruction id {instr_id} not found in {jsonl_path}")
        else:
            for line in f:
                s = (line or "").strip()
                if not s:
                    continue
                try:
                    obj = json.loads(s)
                except Exception:
                    continue
                if isinstance(obj, dict):
                    return obj
    raise RuntimeError(f"No valid instruction found in {jsonl_path}")


def main() -> None:
    p = argparse.ArgumentParser(description="Profile a single episode using line_profiler")
    p.add_argument("--instr-jsonl", type=str, default=os.getenv("INSTR_JSONL", "instructions/osworld_small.jsonl"))
    p.add_argument("--instr-id", type=str, default=os.getenv("INSTR_ID"), help="Instruction id to run (defaults to first entry)")
    p.add_argument("--seed", type=int, default=int(os.getenv("SEED", "123")))
    p.add_argument("--steps", type=int, default=int(os.getenv("STEPS", "8")))
    p.add_argument("--fidelity", type=str, choices=["low", "medium", "high"], default=os.getenv("FIDELITY", "medium"))
    p.add_argument("--sim-feature-config", type=str, default=os.getenv("SIM_FEATURE_CONFIG"))
    p.add_argument("--log-dir", type=str, default=os.getenv("LOG_DIR", "runs"))
    p.add_argument("--log-profile", type=str, choices=["verbose", "concise", "both"], default=os.getenv("LOG_PROFILE", "concise"))
    p.add_argument("--log-state-snapshots", action="store_true")
    sim_include_env = os.getenv("SIM_INCLUDE_STATE")
    if sim_include_env is None:
        sim_include_default = True
    else:
        sim_include_default = sim_include_env.lower() not in {"0", "false", "no"}
    p.add_argument("--sim-include-state", dest="sim_include_state", action="store_true", default=sim_include_default)
    p.add_argument("--no-sim-include-state", dest="sim_include_state", action="store_false")
    args = p.parse_args()

    # Ensure repository root is on sys.path so imports like 'orchestrator' work
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from simulator_prompt_features import SimulatorPromptFeatures

    try:
        from line_profiler import LineProfiler  # type: ignore
    except Exception as e:  # pragma: no cover
        print("[error] line_profiler is not installed. Please install it and rerun.")
        raise

    # Import target modules and functions to instrument
    import orchestrator
    from agent_llm import LLMAgent
    from judge_llm import LLMJudge
    from simulator_llm import PureLLMSimulator
    from llm_client import LLMClient

    lp = LineProfiler()
    # High-level orchestration
    lp.add_function(orchestrator.run_episode)
    # Agent
    lp.add_function(LLMAgent.act)
    try:
        # internal normalizer
        from agent_llm import LLMAgent as _A
        lp.add_function(_A._normalize_action)  # type: ignore[attr-defined]
    except Exception:
        pass
    # Simulator
    lp.add_function(PureLLMSimulator.reset)
    lp.add_function(PureLLMSimulator.step)
    try:
        lp.add_function(PureLLMSimulator._apply_state_ops)  # type: ignore[attr-defined]
    except Exception:
        pass
    # Judge
    lp.add_function(LLMJudge.evaluate)
    # LLM client
    lp.add_function(LLMClient.complete_json)

    sim_feature_config_raw: Optional[Dict[str, Any]] = None
    sim_feature_config: Optional[SimulatorPromptFeatures] = None
    if args.sim_feature_config:
        try:
            with open(args.sim_feature_config, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if not isinstance(loaded, dict):
                raise ValueError("feature config must be a JSON object")
            sim_feature_config_raw = loaded
            sim_feature_config = SimulatorPromptFeatures.from_dict(loaded)
        except Exception as exc:
            raise RuntimeError(f"Failed to load simulator feature config ({args.sim_feature_config}): {exc}")

    # Build instruction and run one episode through orchestrator.run_episode
    instruction = _load_first_instruction(args.instr_jsonl, args.instr_id)
    feature_controls_fidelity = bool(isinstance(sim_feature_config_raw, dict) and "observation_granularity" in sim_feature_config_raw)
    # Mirror environment-based role configuration used in orchestrator.run_episode
    # (orchestrator.run_episode resolves models/keys internally, so we just pass instruction/args)
    def run_once():
        kwargs = {
            "seed": args.seed,
            "steps_limit": args.steps,
            "stop_on_success": False,
            "success_threshold": 0.99,
            "agent_history": 5,
            "sim_include_state": args.sim_include_state,
            "log_dir": args.log_dir,
            "log_state_snapshots": args.log_state_snapshots,
            "log_profile": args.log_profile,
            "sim_feature_config": sim_feature_config,
        }
        if not feature_controls_fidelity:
            kwargs["fidelity"] = args.fidelity
        log, judge_out = orchestrator.run_episode(instruction, **kwargs)
        # Persist outputs like the main script (concise)
        orchestrator.save_episode(args.log_dir, log, judge_out)

    lp.runcall(run_once)
    lp.print_stats()


if __name__ == "__main__":
    main()
