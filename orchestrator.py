import argparse
import json
import os
import time
from typing import Any, Dict, Tuple, Optional

USE_LLM_AGENT = True
USE_LLM_JUDGE = True
USE_LLM_PROPOSER = True
USE_LLM_SIMULATOR = True

# Always attempt to import LLM wrappers; they lazily create clients.
try:
    from agent_llm import LLMAgent
    from judge_llm import LLMJudge
    from proposer_llm import LLMProposer
    from simulator_llm import PureLLMSimulator
except Exception:
    LLMAgent = None  # type: ignore
    LLMJudge = None  # type: ignore
    LLMProposer = None  # type: ignore
    PureLLMSimulator = None  # type: ignore


class DummyAgent:
    """A minimal agent that emits a single action causing a rejection, then stops."""

    def act(self, observation: Dict[str, Any], instruction: Dict[str, Any]) -> Dict[str, Any]:
        # Prefer element_id targeting per spec
        # This naive agent double-clicks the Settings icon on desktop.
        return {"type": "double_click", "target": {"element_id": "icon_settings"}}


def run_episode(
    instr: Dict[str, Any],
    seed: int,
    fidelity: str = "low",
    steps_limit: int = 1,
    stop_on_success: bool = False,
    success_threshold: float = 0.99,
    agent_history: int = 5,
    sim_history: int = 5,
    sim_include_state: bool = False,
    log_dir: str | None = None,
    log_state_snapshots: bool = False,
    log_profile: str = "both",
    sim_mode: str = "deterministic",
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    # Helper to resolve role-specific configuration
    def _role_conf(role: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        r = role.upper()
        model = os.getenv(f"{r}_MODEL") or os.getenv("LLM_MODEL")
        base = os.getenv(f"{r}_OPENAI_BASE_URL") or os.getenv("OPENAI_BASE_URL")
        key = os.getenv(f"{r}_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        return model, base, key

    # Choose simulator (LLM-only)
    if 'PureLLMSimulator' in globals() and PureLLMSimulator is not None:
        sim_model, sim_base, sim_key = _role_conf("SIMULATOR")
        sim = PureLLMSimulator(model=sim_model, seed=seed, history_window=sim_history, include_full_state=sim_include_state, mode=sim_mode, base_url=sim_base, api_key=sim_key)
    else:
        raise RuntimeError("PureLLMSimulator not available. Ensure simulator_llm.py is present.")
    # Choose agent
    if USE_LLM_AGENT and 'LLMAgent' in globals() and LLMAgent is not None:
        agent_model, agent_base, agent_key = _role_conf("AGENT")
        agent = LLMAgent(model=agent_model, temperature=float(os.getenv("AGENT_TEMP", "1")), seed=seed, base_url=agent_base, api_key=agent_key)
    else:
        agent = DummyAgent()
    # Choose judge (LLM-only)
    if 'LLMJudge' in globals() and LLMJudge is not None:
        judge_model, judge_base, judge_key = _role_conf("JUDGE")
        judge = LLMJudge(model=judge_model, temperature=0.0, seed=seed, base_url=judge_base, api_key=judge_key)
    else:
        raise RuntimeError("LLMJudge not available. Ensure judge_llm.py is present.")

    obs, start_digest, episode_id = sim.reset(instr, seed, fidelity)

    # Prepare episode-specific logs
    episode_dir = None
    agent_log_path = None
    sim_log_path = None
    agent_readable_path = None
    sim_readable_path = None
    judge_readable_path = None
    if log_dir:
        episode_dir = os.path.join(log_dir, episode_id)
        os.makedirs(episode_dir, exist_ok=True)
        want_verbose = log_profile in ("verbose", "both")
        want_concise = log_profile in ("concise", "both")
        if want_verbose:
            agent_log_path = os.path.join(episode_dir, "agent.log.jsonl")
            sim_log_path = os.path.join(episode_dir, "simulator.log.jsonl")
        if want_concise:
            agent_readable_path = os.path.join(episode_dir, "agent.readable.log")
            sim_readable_path = os.path.join(episode_dir, "simulator.readable.log")
            judge_readable_path = os.path.join(episode_dir, "judge.readable.log")
        llm_dir = os.path.join(episode_dir, "llm")
        os.makedirs(llm_dir, exist_ok=True)
        # Write initial simulator log for reset (verbose)
        if sim_log_path:
            with open(sim_log_path, "a", encoding="utf-8") as sf:
                entry = {
                    "t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "phase": "reset",
                    "observation": obs,
                    "start_digest": start_digest,
                }
                if hasattr(sim, "_last_call") and isinstance(getattr(sim, "_last_call"), dict):
                    entry["llm"] = getattr(sim, "_last_call")  # type: ignore[assignment]
                sf.write(json.dumps(entry) + "\n")
        # Readable reset summary (concise)
        if agent_readable_path and sim_readable_path:
            t0 = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            try:
                with open(sim_readable_path, "a", encoding="utf-8") as rf:
                    pg = (obs.get("meta") or {}).get("page") if isinstance(obs, dict) else None
                    rf.write(f"{t0} reset page={pg} start_digest={start_digest[:10]}...\n")
            except Exception:
                pass
        # Save raw/error LLM IO for reset if present
        try:
            if sim_log_path and hasattr(sim, "_last_call") and isinstance(getattr(sim, "_last_call"), dict):
                lc = getattr(sim, "_last_call")  # type: ignore[index]
                raw = lc.get("raw")
                err = lc.get("error")
                if raw:
                    with open(os.path.join(llm_dir, "simulator_reset.json"), "w", encoding="utf-8") as f:
                        json.dump(raw, f, indent=2, sort_keys=True)
                if err:
                    with open(os.path.join(llm_dir, "simulator_reset.error.json"), "w", encoding="utf-8") as f:
                        json.dump({"input": lc.get("input"), "error": err}, f, indent=2, sort_keys=True)
        except Exception:
            pass
    episode_log: Dict[str, Any] = {
        "episode_id": episode_id,
        "instruction_id": instr.get("id"),
        "instruction": instr,
        "seed": seed,
        "fidelity": fidelity,
        "sim_mode": sim_mode,
        "agent_history": agent_history,
        "sim_history": sim_history,
        "sim_include_state": sim_include_state,
        "start_digest": start_digest,
        "steps": [],
        "components": {
            "simulator": "llm",
            "agent": "llm" if USE_LLM_AGENT else "dummy",
            "judge": "llm" if USE_LLM_JUDGE else "det",
            "proposer": "llm" if USE_LLM_PROPOSER else "simple",
        },
    }

    done = False
    steps = 0
    history: list[Dict[str, Any]] = []
    while not done and steps < steps_limit:
        # Provide recent observation/action history to the agent (agent-visible only)
        hist_slice = history[-agent_history:] if agent_history and agent_history > 0 else []
        try:
            action = agent.act(obs, instr, hist_slice)  # type: ignore[arg-type]
        except TypeError:
            action = agent.act(obs, instr)  # type: ignore[call-arg]
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        out = sim.step(episode_id, action, now, 0)

        # Agent log (LLM or dummy) — verbose JSON
        if agent_log_path:
            agent_entry = {
                "t": now,
                "step": steps,
                "instruction_id": instr.get("id"),
                "history_len": len(hist_slice),
                "action": action,
            }
            # Include LLM payload/output if available
            if hasattr(agent, "_last_call") and isinstance(getattr(agent, "_last_call"), dict):
                agent_entry["llm"] = getattr(agent, "_last_call")  # type: ignore[assignment]
            with open(agent_log_path, "a", encoding="utf-8") as af:
                af.write(json.dumps(agent_entry) + "\n")
        # Agent human-readable summary — concise
        if agent_readable_path:
            try:
                tgt = (action.get("target") or {}) if isinstance(action, dict) else {}
                tid = tgt.get("element_id") if isinstance(tgt, dict) else None
                txt = action.get("text") if isinstance(action, dict) else None
                keys = action.get("keys") if isinstance(action, dict) else None
                summary = [f"{now}", f"step={steps}", f"type={action.get('type')}" if isinstance(action, dict) else "type=?"]
                if tid:
                    summary.append(f"target={tid}")
                elif isinstance(tgt, dict) and ("x" in tgt or "y" in tgt):
                    summary.append(f"target=({tgt.get('x')},{tgt.get('y')})")
                if txt:
                    summary.append(f"text={txt}")
                if keys:
                    summary.append(f"keys={keys}")
                with open(agent_readable_path, "a", encoding="utf-8") as rf:
                    rf.write(" ".join(summary) + "\n")
            except Exception:
                pass
        # Save raw agent LLM IO to separate file per step (verbose)
        try:
            if agent_log_path and 'llm_dir' in locals() and hasattr(agent, "_last_call") and isinstance(getattr(agent, "_last_call"), dict):
                raw = getattr(agent, "_last_call").get("raw")  # type: ignore[index]
                if raw:
                    with open(os.path.join(llm_dir, f"agent_step_{steps:04d}.json"), "w", encoding="utf-8") as f:
                        json.dump(raw, f, indent=2, sort_keys=True)
        except Exception:
            pass

        # Simulator log entry — verbose JSON
        if sim_log_path:
            sim_entry = {
                "t": now,
                "step": steps,
                "action": action,
                "internal_result": out.get("internal_result"),
                "event_log": out.get("event_log"),
                "state_diff": out.get("state_diff"),
                "state_digest": out.get("state_digest"),
                "observation": out.get("observation"),
            }
            if hasattr(sim, "_last_call") and isinstance(getattr(sim, "_last_call"), dict):
                sim_entry["llm"] = getattr(sim, "_last_call")  # type: ignore[assignment]
            if log_state_snapshots:
                try:
                    # type: ignore[attr-defined]
                    snapshot = sim.snapshot(episode_id)
                    sim_entry["state_snapshot"] = snapshot
                except Exception:
                    pass
            with open(sim_log_path, "a", encoding="utf-8") as sf:
                sf.write(json.dumps(sim_entry) + "\n")
        # Simulator human-readable summary — concise
        if sim_readable_path:
            try:
                ir = out.get("internal_result") or {}
                res = ir.get("result") if isinstance(ir, dict) else None
                reason = ir.get("reason") if isinstance(ir, dict) else None
                pg = None
                obs = out.get("observation") or {}
                if isinstance(obs, dict):
                    meta = obs.get("meta") or {}
                    if isinstance(meta, dict):
                        pg = meta.get("page")
                diffs = out.get("state_diff")
                diff_str = ",".join(diffs) if isinstance(diffs, list) else ""
                # include action summary for readability
                a = action if isinstance(action, dict) else {}
                atype = a.get("type")
                tgt = a.get("target") if isinstance(a.get("target"), dict) else {}
                tid = tgt.get("element_id") if isinstance(tgt, dict) else None
                tgt_str = tid or (f"({tgt.get('x')},{tgt.get('y')})" if isinstance(tgt, dict) and ("x" in tgt or "y" in tgt) else "-")
                with open(sim_readable_path, "a", encoding="utf-8") as rf:
                    line = f"{now} step={steps} result={res}"
                    if reason:
                        line += f" reason={reason}"
                    line += f" page={pg} diff=[{diff_str}] action={atype}:{tgt_str}"
                    rf.write(line + "\n")
            except Exception:
                pass
        # Save raw/error simulator LLM IO per step (verbose)
        try:
            if sim_log_path and 'llm_dir' in locals() and hasattr(sim, "_last_call") and isinstance(getattr(sim, "_last_call"), dict):
                lc = getattr(sim, "_last_call")  # type: ignore[index]
                raw = lc.get("raw")
                err = lc.get("error")
                if raw:
                    with open(os.path.join(llm_dir, f"simulator_step_{steps:04d}.json"), "w", encoding="utf-8") as f:
                        json.dump(raw, f, indent=2, sort_keys=True)
                if err:
                    with open(os.path.join(llm_dir, f"simulator_step_{steps:04d}.error.json"), "w", encoding="utf-8") as f:
                        json.dump({"input": lc.get("input"), "error": err}, f, indent=2, sort_keys=True)
        except Exception:
            pass

        episode_log["steps"].append({
            "t": now,
            "action": action,
            "internal_result": out["internal_result"],
            "event_log": out["event_log"],
            "state_diff": out["state_diff"],
            "state_digest": out["state_digest"],
            "observation": out["observation"],  # store agent-visible obs for replay/judge
        })
        # Append to history for next step
        if agent_history and agent_history > 0:
            history.append({
                "t": now,
                "action": action,
                "observation": obs,
                "result_observation": out["observation"],
            })
            if len(history) > agent_history:
                history = history[-agent_history:]

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
    # Log LLM judge I/O if applicable
    if episode_dir and hasattr(judge, "_last_call") and isinstance(getattr(judge, "_last_call"), dict):
        want_verbose = log_profile in ("verbose", "both")
        want_concise = log_profile in ("concise", "both")
        if want_verbose:
            judge_log_path = os.path.join(episode_dir, "judge.log.jsonl")
            with open(judge_log_path, "a", encoding="utf-8") as jf:
                jf.write(json.dumps({
                    "t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "phase": "final",
                    "llm": getattr(judge, "_last_call"),  # type: ignore[arg-type]
                    "judgement": judgement,
                }) + "\n")
        if want_concise:
            try:
                with open(os.path.join(episode_dir, "judge.readable.log"), "a", encoding="utf-8") as rf:
                    rf.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} final score={judgement.get('score')} feedback={judgement.get('feedback')}\n")
            except Exception:
                pass
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
    parser.add_argument("--instr-file", type=str, default=os.getenv("INSTR_FILE"), help="Path to instruction JSON file")
    parser.add_argument("--instr-json", type=str, default=os.getenv("INSTR_JSON"), help="Instruction JSON string")
    parser.add_argument("--instr-jsonl", type=str, default=os.getenv("INSTR_JSONL"), help="Path to JSONL file with one Instruction JSON per line (batch mode)")
    parser.add_argument("--instruction", "--instr-text", dest="instr_text", type=str, default=os.getenv("INSTRUCTION"), help="Freeform instruction text to compile (LLM)")
    parser.add_argument("--stop-on-success", action="store_true", help="Stop the episode early when success criteria are met")
    parser.add_argument("--success-threshold", type=float, default=float(os.getenv("SUCCESS_THRESHOLD", "0.99")), help="Score threshold to stop when --stop-on-success is set")
    parser.add_argument("--agent-history", type=int, default=int(os.getenv("AGENT_HISTORY", "5")), help="Number of recent (action, observation) steps to pass to the agent")
    parser.add_argument("--sim-history", type=int, default=int(os.getenv("SIM_HISTORY", "5")), help="Number of recent simulator steps to include in simulator input")
    parser.add_argument("--sim-include-state", action="store_true", default=os.getenv("SIM_INCLUDE_STATE", "0") == "1", help="Always include full current_state in simulator LLM input (compat mode)")
    parser.add_argument("--sim-mode", type=str, default=os.getenv("SIM_MODE", "deterministic"), choices=["deterministic", "diverse"], help="Simulator mode: deterministic (stable) or diverse (varied)")
    parser.add_argument("--log-dir", type=str, default=os.getenv("LOG_DIR", "runs"), help="Directory for logs")
    parser.add_argument("--log-state-snapshots", action="store_true", help="Include full state snapshots in simulator logs (verbose only)")
    parser.add_argument(
        "--log-profile",
        type=str,
        default=os.getenv("LOG_PROFILE", "both"),
        choices=["verbose", "concise", "both"],
        help="Logging profile: verbose (detailed JSON + raw LLM IO), concise (human-readable summaries), or both",
    )
    parser.add_argument("--propose-count", type=int, default=int(os.getenv("PROPOSE_COUNT", "0")), help="Run propose→run loop for N episodes (LLMProposer adapts using recent_episodes)")
    parser.add_argument("--global-task-pool", type=str, default=os.getenv("GLOBAL_TASK_POOL"), help="Optional JSON file: array of candidate instructions to bias the proposer")
    parser.add_argument("--agent-id", type=str, default=os.getenv("AGENT_ID", "agent"), help="Agent identifier to pass to the proposer")
    parser.add_argument("--export-html", action="store_true", help="[Deprecated] HTML export is default; use --no-export-html to disable")
    parser.add_argument("--no-export-html", action="store_true", help="Disable HTML summary export")
    args = parser.parse_args()

    # Reflect CLI toggles to module-level flags
    USE_LLM_AGENT = args.llm_agent
    USE_LLM_JUDGE = args.llm_judge
    USE_LLM_PROPOSER = args.llm_proposer
    USE_LLM_SIMULATOR = True  # Always LLM simulator

    # Prepare runtime log path early
    os.makedirs(args.log_dir, exist_ok=True)
    runtime_log_path = os.path.join(args.log_dir, "runtime.log.jsonl")
    runtime_readable_path = os.path.join(args.log_dir, "runtime.readable.log")

    # Removed preset rule-based tasks; default to LLMProposer below.

    # Batch mode: JSONL of instructions
    if args.instr_jsonl:
        # Read all instructions first (skip blank/malformed lines)
        instrs: list[Dict[str, Any]] = []
        try:
            with open(args.instr_jsonl, "r", encoding="utf-8") as f:
                for ln in f:
                    s = (ln or "").strip()
                    if not s:
                        continue
                    try:
                        obj = json.loads(s)
                        if isinstance(obj, dict):
                            instrs.append(obj)
                    except Exception:
                        continue
        except Exception as e:
            raise RuntimeError(f"Failed to read --instr-jsonl {args.instr_jsonl}: {e}")

        # Batch start log
        with open(runtime_log_path, "a", encoding="utf-8") as rf:
            rf.write(json.dumps({
                "t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "event": "batch_start",
                "count": len(instrs),
                "seed": args.seed,
                "fidelity": args.fidelity,
                "sim_mode": args.sim_mode,
            }) + "\n")
        if args.log_profile in ("concise", "both"):
            try:
                with open(runtime_readable_path, "a", encoding="utf-8") as rrf:
                    rrf.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} batch start count={len(instrs)} sim_mode={args.sim_mode}\n")
            except Exception:
                pass

        total = 0
        successes = 0
        scores: list[float] = []
        summaries: list[Dict[str, Any]] = []
        for instruction in instrs:
            total += 1
            # For readability
            iid = instruction.get("id") if isinstance(instruction, dict) else None
            print(
                "Components:",
                f"simulator=llm({args.sim_mode})",
                f"agent={'LLM' if USE_LLM_AGENT else 'dummy'}",
                f"judge={'LLM' if USE_LLM_JUDGE else 'det'}",
                f"proposer={'LLM' if USE_LLM_PROPOSER else 'simple'}",
                f"instr={iid}",
            )
            log, judge_out = run_episode(
                instruction,
                seed=args.seed,
                fidelity=args.fidelity,
                steps_limit=args.steps,
                stop_on_success=args.stop_on_success,
                success_threshold=args.success_threshold,
                agent_history=args.agent_history,
                sim_history=args.sim_history,
                log_dir=args.log_dir,
                log_state_snapshots=args.log_state_snapshots,
                log_profile=args.log_profile,
                sim_include_state=args.sim_include_state,
                sim_mode=args.sim_mode,
            )
            episode_dir = os.path.join(args.log_dir)
            save_episode(episode_dir, log, judge_out)
            do_export_html = not getattr(args, "no_export_html", False)
            if do_export_html:
                try:
                    from tools.export_html import export_episode_html
                    html_path = export_episode_html(args.log_dir, log.get("episode_id"))
                    if html_path:
                        print(f"Exported HTML summary: {html_path}")
                except Exception as e:
                    print(f"[warn] HTML export failed: {e}")
            sc = float(judge_out.get("score") or 0.0)
            scores.append(sc)
            ok = sc >= float(args.success_threshold)
            successes += 1 if ok else 0
            summaries.append({
                "id": iid,
                "score": sc,
                "success": ok,
                "episode_id": log.get("episode_id"),
            })

        # Final metrics
        acc = (successes / total) if total else 0.0
        mean_score = (sum(scores) / len(scores)) if scores else 0.0
        print(f"Batch complete: total={total} success={successes} accuracy={acc:.3f} mean_score={mean_score:.3f}")
        # Persist batch summary
        summary = {
            "t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total": total,
            "successes": successes,
            "accuracy": acc,
            "mean_score": mean_score,
            "threshold": args.success_threshold,
            "items": summaries,
        }
        try:
            with open(os.path.join(args.log_dir, "batch_summary.json"), "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2, sort_keys=True)
        except Exception:
            pass
        with open(runtime_log_path, "a", encoding="utf-8") as rf:
            rf.write(json.dumps({
                "t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "event": "batch_end",
                "summary": {k: v for k, v in summary.items() if k != "items"},
            }) + "\n")
        if args.log_profile in ("concise", "both"):
            try:
                with open(runtime_readable_path, "a", encoding="utf-8") as rrf:
                    rrf.write(
                        f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} batch end total={total} success={successes} acc={acc:.3f} mean={mean_score:.3f}\n"
                    )
            except Exception:
                pass
        raise SystemExit(0)

    # Resolve single instruction from CLI/env (non-batch)
    instruction: Dict[str, Any]
    if args.instr_file:
        with open(args.instr_file, "r", encoding="utf-8") as f:
            instruction = json.load(f)
    elif args.instr_json:
        instruction = json.loads(args.instr_json)
    elif args.instr_text:
        # Compile freeform instruction using LLM (no heuristic fallback)
        from proposer_llm import InstructionCompiler
        def _role_conf(role: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
            r = role.upper()
            model = os.getenv(f"{r}_MODEL") or os.getenv("LLM_MODEL")
            base = os.getenv(f"{r}_OPENAI_BASE_URL") or os.getenv("OPENAI_BASE_URL")
            key = os.getenv(f"{r}_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
            return model, base, key
        comp_model, comp_base, comp_key = _role_conf("COMPILER")
        compiler = InstructionCompiler(model=comp_model, temperature=0.0, seed=args.seed, base_url=comp_base, api_key=comp_key)
        instruction = compiler.compile(args.instr_text)
        # Log compiler I/O
        try:
            if hasattr(compiler, "_last_call") and isinstance(getattr(compiler, "_last_call"), dict):
                with open(runtime_log_path, "a", encoding="utf-8") as rf:
                    rf.write(json.dumps({
                        "t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "event": "compile_instruction",
                        "llm": getattr(compiler, "_last_call"),  # type: ignore[arg-type]
                    }) + "\n")
                if args.log_profile in ("concise", "both"):
                    try:
                        with open(runtime_readable_path, "a", encoding="utf-8") as rrf:
                            rrf.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} compiled instruction via LLM id={instruction.get('id')}\n")
                    except Exception:
                        pass
        except Exception:
            pass
    else:
        # Default: Use LLMProposer to propose the next instruction
        if 'LLMProposer' not in globals() or LLMProposer is None:
            raise RuntimeError("LLMProposer not available. Ensure proposer_llm.py is present.")
        def _role_conf(role: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
            r = role.upper()
            model = os.getenv(f"{r}_MODEL") or os.getenv("LLM_MODEL")
            base = os.getenv(f"{r}_OPENAI_BASE_URL") or os.getenv("OPENAI_BASE_URL")
            key = os.getenv(f"{r}_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
            return model, base, key
        prop_model, prop_base, prop_key = _role_conf("PROPOSER")
        proposer = LLMProposer(model=prop_model, temperature=0.2, seed=args.seed, base_url=prop_base, api_key=prop_key)
        instruction = proposer.propose_next(agent_id="agent", recent_episodes=[])
        # Log proposer I/O
        try:
            if hasattr(proposer, "_last_call") and isinstance(getattr(proposer, "_last_call"), dict):
                with open(runtime_log_path, "a", encoding="utf-8") as rf:
                    rf.write(json.dumps({
                        "t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "event": "propose_instruction",
                        "llm": getattr(proposer, "_last_call"),  # type: ignore[arg-type]
                    }) + "\n")
                if args.log_profile in ("concise", "both"):
                    try:
                        with open(runtime_readable_path, "a", encoding="utf-8") as rrf:
                            rrf.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} proposed instruction via LLM id={instruction.get('id')}\n")
                    except Exception:
                        pass
        except Exception:
            pass
    print(
        "Components:",
        f"simulator=llm({args.sim_mode})",
        f"agent={'LLM' if USE_LLM_AGENT else 'dummy'}",
        f"judge={'LLM' if USE_LLM_JUDGE else 'det'}",
        f"proposer={'LLM' if USE_LLM_PROPOSER else 'simple'}",
    )
    # Runtime log boot message
    # Ensure runtime log dir exists (already created above)
    # Start runtime logs
    with open(runtime_log_path, "a", encoding="utf-8") as rf:
        rf.write(json.dumps({
            "t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "event": "start",
            "seed": args.seed,
            "fidelity": args.fidelity,
            "components": {
                "simulator": "llm",
                "agent": "llm" if USE_LLM_AGENT else "dummy",
                "judge": "llm" if USE_LLM_JUDGE else "det",
                "proposer": "llm" if USE_LLM_PROPOSER else "simple",
            },
            "sim_mode": args.sim_mode,
            "instruction": instruction,
            "log_profile": args.log_profile,
        }) + "\n")
    if args.log_profile in ("concise", "both"):
        try:
            with open(runtime_readable_path, "a", encoding="utf-8") as rrf:
                rrf.write(
                    f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} start seed={args.seed} fidelity={args.fidelity} sim_mode={args.sim_mode} comp=sim:llm,agent:{'LLM' if USE_LLM_AGENT else 'dummy'},judge:{'LLM' if USE_LLM_JUDGE else 'det'} instr={instruction.get('id')}\n"
                )
        except Exception:
            pass

    # Propose→run loop if requested; otherwise run single episode
    if args.propose_count and args.propose_count > 0:
        # Load optional global task pool
        global_task_pool = None
        if args.global_task_pool:
            try:
                with open(args.global_task_pool, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        global_task_pool = data
            except Exception:
                pass
        # Proposer instance
        if 'LLMProposer' not in globals() or LLMProposer is None:
            raise RuntimeError("LLMProposer not available. Ensure proposer_llm.py is present.")
        def _role_conf(role: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
            r = role.upper()
            model = os.getenv(f"{r}_MODEL") or os.getenv("LLM_MODEL")
            base = os.getenv(f"{r}_OPENAI_BASE_URL") or os.getenv("OPENAI_BASE_URL")
            key = os.getenv(f"{r}_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
            return model, base, key
        prop_model, prop_base, prop_key = _role_conf("PROPOSER")
        proposer = LLMProposer(model=prop_model, temperature=0.2, seed=args.seed, base_url=prop_base, api_key=prop_key)
        # Keep a small recent window
        recent_episodes: list[Dict[str, Any]] = []
        # If instruction not provided, the earlier branch already proposed one.
        for i in range(int(args.propose_count)):
            log, judge_out = run_episode(
                instruction,
                seed=args.seed,
                fidelity=args.fidelity,
                steps_limit=args.steps,
                stop_on_success=args.stop_on_success,
                success_threshold=args.success_threshold,
                agent_history=args.agent_history,
                sim_history=args.sim_history,
                log_dir=args.log_dir,
                log_state_snapshots=args.log_state_snapshots,
                log_profile=args.log_profile,
                sim_include_state=args.sim_include_state,
                sim_mode=args.sim_mode,
            )
            episode_dir = os.path.join(args.log_dir)
            save_episode(episode_dir, log, judge_out)
            print(f"Saved episode to '{episode_dir}/'")
            do_export_html = not getattr(args, "no_export_html", False)
            if do_export_html:
                try:
                    from tools.export_html import export_episode_html
                    html_path = export_episode_html(args.log_dir, log.get("episode_id"))
                    if html_path:
                        print(f"Exported HTML summary: {html_path}")
                except Exception as e:
                    print(f"[warn] HTML export failed: {e}")
            # Append summary for proposer
            try:
                recent_episodes.append({
                    "t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "instruction_id": instruction.get("id") if isinstance(instruction, dict) else None,
                    "score": judge_out.get("score"),
                    "feedback": judge_out.get("feedback"),
                    "subscores": judge_out.get("subscores"),
                })
                if len(recent_episodes) > 10:
                    recent_episodes = recent_episodes[-10:]
            except Exception:
                pass
            # Propose next if more episodes remain
            if (i + 1) < int(args.propose_count):
                next_instr = proposer.propose_next(agent_id=args.agent_id, recent_episodes=recent_episodes, global_task_pool=global_task_pool)
                # Log proposer I/O
                try:
                    if hasattr(proposer, "_last_call") and isinstance(getattr(proposer, "_last_call"), dict):
                        with open(runtime_log_path, "a", encoding="utf-8") as rf:
                            rf.write(json.dumps({
                                "t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                "event": "propose_instruction",
                                "llm": getattr(proposer, "_last_call"),
                            }) + "\n")
                        if args.log_profile in ("concise", "both"):
                            try:
                                with open(runtime_readable_path, "a", encoding="utf-8") as rrf:
                                    rrf.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} proposed instruction via LLM id={next_instr.get('id')}\n")
                            except Exception:
                                pass
                except Exception:
                    pass
                instruction = next_instr
    else:
        log, judge_out = run_episode(
            instruction,
            seed=args.seed,
            fidelity=args.fidelity,
            steps_limit=args.steps,
            stop_on_success=args.stop_on_success,
            success_threshold=args.success_threshold,
            agent_history=args.agent_history,
            sim_history=args.sim_history,
            log_dir=args.log_dir,
            log_state_snapshots=args.log_state_snapshots,
            log_profile=args.log_profile,
            sim_include_state=args.sim_include_state,
            sim_mode=args.sim_mode,
        )
        episode_dir = os.path.join(args.log_dir)
        save_episode(episode_dir, log, judge_out)
        print(f"Saved episode to '{episode_dir}/'")
        # Default HTML export (disable with --no-export-html)
        do_export_html = not getattr(args, "no_export_html", False)
        if do_export_html:
            try:
                from tools.export_html import export_episode_html
                html_path = export_episode_html(args.log_dir, log.get("episode_id"))
                if html_path:
                    print(f"Exported HTML summary: {html_path}")
            except Exception as e:
                print(f"[warn] HTML export failed: {e}")
