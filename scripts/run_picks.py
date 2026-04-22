"""Run a list of (task_id, variant_filename) pairs via stock_browseruse_eval.

Input: JSON array of ``{"task_id": str, "variant_filename": str | null, ...}``.
Each pair is run sequentially. Results aggregated into one output JSON.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from webagentbench.stock_browseruse_eval import run_episode  # noqa: E402


async def _main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--picks", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--provider", default="bedrock")
    p.add_argument("--backend-port", type=int, default=8080)
    p.add_argument("--frontend-port", type=int, default=8080)
    p.add_argument("--server-host", default="127.0.0.1")
    p.add_argument("--max-steps", type=int, default=40)
    p.add_argument("--timeout", type=int, default=600)
    p.add_argument("--max-actions-per-step", type=int, default=4)
    p.add_argument("--output", required=True)
    p.add_argument("--limit", type=int, default=None)
    args = p.parse_args()

    picks = json.loads(Path(args.picks).read_text())
    if args.limit:
        picks = picks[: args.limit]

    print(f"Running {len(picks)} tasks, model={args.model} provider={args.provider}")

    results = []
    t0 = time.time()
    for i, pick in enumerate(picks, 1):
        tid = pick["task_id"]
        var = pick.get("variant_filename")
        tag = f" (+{var})" if var else ""
        print(f"[{i}/{len(picks)}] {tid}{tag}")
        try:
            ep = await run_episode(
                task_id=tid,
                model=args.model,
                provider=args.provider,
                variant_filename=var,
                server_host=args.server_host,
                backend_port=args.backend_port,
                frontend_port=args.frontend_port,
                max_steps=args.max_steps,
                timeout_seconds=args.timeout,
                max_actions_per_step=args.max_actions_per_step,
                verbose=False,
            )
        except Exception as exc:
            import traceback
            print(f"  EXCEPTION: {exc}")
            traceback.print_exc(limit=3)
            ep = {
                "task_id": tid,
                "variant_filename": var,
                "evaluation": {"score": 0.0, "success": False, "reasoning": f"harness error: {exc}"},
                "agent": {"model": args.model, "provider": args.provider, "steps": 0, "elapsed_seconds": 0},
            }
        else:
            ep["variant_filename"] = var
            ep.setdefault("pick_metadata", pick)

        score = ep.get("evaluation", {}).get("score", 0.0)
        ok = "PASS" if ep.get("evaluation", {}).get("success") else "FAIL"
        elapsed = ep.get("agent", {}).get("elapsed_seconds", 0)
        print(f"  [{ok}] score={score:.2f}  ({elapsed}s)")
        results.append(ep)

    total = time.time() - t0
    passed = sum(1 for r in results if r.get("evaluation", {}).get("success"))
    avg = sum(r.get("evaluation", {}).get("score", 0.0) for r in results) / max(1, len(results))
    print(f"\nSUMMARY: {passed}/{len(results)} passed, avg={avg:.3f}, wall={total:.1f}s")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "model": args.model,
        "provider": args.provider,
        "n": len(results),
        "passed": passed,
        "avg_score": avg,
        "wall_seconds": total,
        "results": results,
    }, indent=2, default=str))
    print(f"Wrote {out}")


if __name__ == "__main__":
    asyncio.run(_main())
