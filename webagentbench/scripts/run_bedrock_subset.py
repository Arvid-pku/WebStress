"""Run an 8-task / 16-trajectory subset on AWS Bedrock Claude, then visualize.

Eight base tasks spanning all 7 environments (gmail twice), each run under:
  (a) no degradation — baseline
  (b) a hand-picked 2026-04 variant — exercises the new degradation framework

Output layout::

    results/bedrock_subset/standard.json               # 8 trajectories
    results/bedrock_subset/stress_<variant>.json * 8   # 1 trajectory each
    results/bedrock_subset/merged.json                 # 16 trajectories
    webagentbench/static/bedrock_subset_viz.html       # served at /static/...

Prerequisites (one-time):
  uv sync
  playwright install chromium
  pnpm -C webagentbench/environments install && pnpm -C webagentbench/environments build

Run:
  python -m webagentbench.scripts.run_bedrock_subset
  # default model: us.anthropic.claude-sonnet-4-6
  # overrides: --model, --seed, --no-viz

After completion the launcher at http://127.0.0.1:8080/launch stays up and the
trajectory viz is available at::

    http://127.0.0.1:8080/static/bedrock_subset_viz.html
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# The 8 tasks and their paired intervention variants. Every pairing covers a
# different environment, a different primitive, and a different NEW action.
# ---------------------------------------------------------------------------

SUBSET: list[tuple[str, str]] = [
    ("gmail_action_item_extraction",
     "gmail_action_item_extraction__phishing_inbox.yaml"),        # seed / grounding
    ("gmail_ambiguous_inbox_cleanup",
     "gmail_ambiguous_inbox_cleanup__double_submit.yaml"),        # client / verification
    ("amazon_cart_optimization",
     "amazon_cart_optimization__misleading_success.yaml"),        # network / verification
    ("reddit_clear_notifications",
     "reddit_clear_notifications__rate_limit.yaml"),              # network / patience
    ("rh_buy_market_order",
     "rh_buy_market_order__adjacent_selection.yaml"),             # client / verification
    ("booking_budget_comparison",
     "booking_budget_comparison__tail_latency.yaml"),             # network / patience
    ("lms_check_assignment_grade",
     "lms_check_assignment_grade__correlated_window.yaml"),       # network / patience
    ("pp_cancel_appointment",
     "pp_cancel_appointment__phishing_message.yaml"),             # seed / grounding
]


def _load_env_file() -> None:
    """Populate env from webagentbench/.env if present."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.is_file():
        load_dotenv(env_path, override=False)


def _run_one(
    *,
    model: str,
    provider: str,
    task_id: str,
    variant_filename: str | None,
    output_path: Path,
    seed: int,
    headless: bool,
    verbose: bool,
) -> dict:
    """Run a single task through agent_eval.run_evaluation. Returns the result
    dict (not the full envelope)."""
    from webagentbench.agent_eval import run_evaluation

    output_path.parent.mkdir(parents=True, exist_ok=True)
    results = run_evaluation(
        model=model,
        provider=provider,
        task_filter=[task_id],
        degradation=variant_filename,
        seed=seed,
        headless=headless,
        verbose=verbose,
        output_path=str(output_path),
    )
    if not results:
        return {
            "task_id": task_id,
            "evaluation": {"score": 0.0, "success": False, "reasoning": "run_evaluation returned no results"},
            "agent": {"model": model, "provider": provider, "steps": 0, "elapsed_seconds": 0, "completed": False, "trajectory": [], "messages": []},
        }
    return results[0]


def _tag_result(result: dict, *, configuration: str, variant_filename: str | None) -> dict:
    """Attach a 'configuration' marker so the viz distinguishes the 16 runs."""
    tagged = dict(result)
    base_task = tagged.get("task_id", "")
    tagged["task_id"] = f"{base_task}__{configuration}"
    tagged["base_task_id"] = base_task
    tagged["configuration"] = configuration
    if variant_filename:
        tagged.setdefault("degradation", {})
        tagged["degradation"].setdefault("variant_filename", variant_filename)
    return tagged


def _merge(results: list[dict], *, model: str, provider: str) -> dict:
    """Build the agent_eval envelope the visualizer expects."""
    import json as _json
    from datetime import datetime, timezone

    manifest_path = Path(__file__).resolve().parent.parent / "manifest.json"
    manifest = _json.loads(manifest_path.read_text())

    total = len(results)
    passed = sum(1 for r in results if r.get("evaluation", {}).get("success"))
    scores = [r.get("evaluation", {}).get("score", r.get("evaluation", {}).get("final_score", 0.0)) for r in results]
    steps = [r.get("agent", {}).get("steps", 0) for r in results]
    times = [r.get("agent", {}).get("elapsed_seconds", 0) for r in results]

    return {
        "benchmark": "WebAgentBench",
        "version": manifest.get("version", ""),
        "format": "browsergym",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": {"model": model, "provider": provider},
        "results": results,
        "summary": {
            "total_tasks": total,
            "passed": passed,
            "failed": total - passed,
            "average_score": round(sum(scores) / total, 3) if total else 0,
            "average_steps": round(sum(steps) / total, 1) if total else 0,
            "average_elapsed_seconds": round(sum(times) / total, 1) if total else 0,
        },
    }


def main() -> int:
    _load_env_file()

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default="us.anthropic.claude-sonnet-4-6",
                        help="Bedrock model ID (default: us.anthropic.claude-sonnet-4-6)")
    parser.add_argument("--provider", default="bedrock")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-headless", action="store_true",
                        help="Run Playwright with a visible browser window")
    parser.add_argument("--quiet", "-q", action="store_true")
    parser.add_argument("--no-viz", action="store_true",
                        help="Skip the visualization step (just run + merge)")
    parser.add_argument("--only-standard", action="store_true",
                        help="Skip the degraded runs (8 trajectories instead of 16)")
    parser.add_argument("--only-degraded", action="store_true",
                        help="Skip the standard runs (8 trajectories instead of 16)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    root = Path(__file__).resolve().parent.parent
    results_dir = root.parent / "results" / "bedrock_subset"
    results_dir.mkdir(parents=True, exist_ok=True)

    aggregated: list[dict] = []

    # --- Standard runs --------------------------------------------------
    if not args.only_degraded:
        for idx, (task_id, _) in enumerate(SUBSET, start=1):
            if not args.quiet:
                print(f"\n[{idx}/{len(SUBSET)}] STANDARD   {task_id}")
            out = results_dir / f"standard_{task_id}.json"
            try:
                result = _run_one(
                    model=args.model, provider=args.provider,
                    task_id=task_id, variant_filename=None,
                    output_path=out, seed=args.seed,
                    headless=not args.no_headless, verbose=not args.quiet,
                )
                aggregated.append(_tag_result(result, configuration="standard", variant_filename=None))
            except Exception as exc:
                logger.error("standard %s failed: %s", task_id, exc, exc_info=True)

    # --- Degraded runs --------------------------------------------------
    if not args.only_standard:
        for idx, (task_id, variant) in enumerate(SUBSET, start=1):
            if not args.quiet:
                print(f"\n[{idx}/{len(SUBSET)}] DEGRADED   {task_id}  ({variant})")
            out = results_dir / f"stress_{Path(variant).stem}.json"
            try:
                result = _run_one(
                    model=args.model, provider=args.provider,
                    task_id=task_id, variant_filename=variant,
                    output_path=out, seed=args.seed,
                    headless=not args.no_headless, verbose=not args.quiet,
                )
                aggregated.append(_tag_result(result, configuration="degraded", variant_filename=variant))
            except Exception as exc:
                logger.error("degraded %s (%s) failed: %s", task_id, variant, exc, exc_info=True)

    # --- Merge ----------------------------------------------------------
    merged = _merge(aggregated, model=args.model, provider=args.provider)
    merged_path = results_dir / "merged.json"
    merged_path.write_text(json.dumps(merged, indent=2, default=str))
    print(f"\nAggregated {len(aggregated)} trajectories into {merged_path}")
    print(f"Pass rate: {merged['summary']['passed']}/{merged['summary']['total_tasks']}  "
          f"avg score: {merged['summary']['average_score']:+.3f}")

    if args.no_viz:
        return 0

    # --- Visualize ------------------------------------------------------
    print("\nGenerating visualization...")
    try:
        from webagentbench.result_utils import build_manifest_task_meta, load_embedded_task_meta
        from webagentbench.visualize import generate_html
    except Exception as exc:
        logger.error("Could not import visualizer: %s", exc)
        return 1

    task_meta = load_embedded_task_meta(merged)
    try:
        manifest = json.loads((root / "manifest.json").read_text())
        merged["task_meta"] = {**build_manifest_task_meta(manifest), **task_meta}
    except Exception:
        merged["task_meta"] = task_meta

    viz_html = generate_html(merged, "http://127.0.0.1:8080")
    static_path = root / "static" / "bedrock_subset_viz.html"
    results_viz_path = results_dir / "viz.html"
    static_path.write_text(viz_html)
    results_viz_path.write_text(viz_html)

    print(f"\nViz written to:")
    print(f"  {static_path}   (served)")
    print(f"  {results_viz_path}   (portable)")
    print(f"\nOpen on your launcher:")
    print(f"  http://127.0.0.1:8080/static/bedrock_subset_viz.html")
    print(f"\n(Start the server with: python -m webagentbench.app --port 8080)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
