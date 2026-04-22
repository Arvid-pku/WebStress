"""Run a list of (task_id, variant_filename) pairs via stock_browseruse_eval.

Input: JSON array of ``{"task_id": str, "variant_filename": str | null, ...}``.
Results aggregated into one output JSON.

By default picks are run sequentially. Set ``--concurrency N`` to run up to N
episodes in parallel — each episode owns its own Browser + temp dir, so the
only shared resource is the backend. Budget ~400 MB RAM and ~1 CPU core per
concurrent episode.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from webagentbench.stock_browseruse_eval import run_episode  # noqa: E402


def _format_row(idx: int, total: int, pick: dict) -> str:
    tag = f" (+{pick['variant_filename']})" if pick.get("variant_filename") else ""
    return f"[{idx}/{total}] {pick['task_id']}{tag}"


def _error_stub(pick: dict, model: str, provider: str, exc: BaseException) -> dict:
    return {
        "task_id": pick["task_id"],
        "variant_filename": pick.get("variant_filename"),
        "evaluation": {"score": 0.0, "success": False, "reasoning": f"harness error: {exc}"},
        "agent": {"model": model, "provider": provider, "steps": 0, "elapsed_seconds": 0},
        "pick_metadata": pick,
    }


async def _run_one(
    idx: int,
    total: int,
    pick: dict,
    *,
    args: argparse.Namespace,
    sem: asyncio.Semaphore,
) -> dict:
    async with sem:
        header = _format_row(idx, total, pick)
        print(header, flush=True)
        try:
            ep = await run_episode(
                task_id=pick["task_id"],
                model=args.model,
                provider=args.provider,
                variant_filename=pick.get("variant_filename"),
                server_host=args.server_host,
                backend_port=args.backend_port,
                frontend_port=args.frontend_port,
                max_steps=args.max_steps,
                timeout_seconds=args.timeout,
                max_actions_per_step=args.max_actions_per_step,
                verbose=False,
            )
        except Exception as exc:
            print(f"  EXCEPTION ({header}): {exc}", flush=True)
            traceback.print_exc(limit=3)
            return _error_stub(pick, args.model, args.provider, exc)

        ep["variant_filename"] = pick.get("variant_filename")
        ep.setdefault("pick_metadata", pick)
        score = ep.get("evaluation", {}).get("score", 0.0)
        ok = "PASS" if ep.get("evaluation", {}).get("success") else "FAIL"
        elapsed = ep.get("agent", {}).get("elapsed_seconds", 0)
        print(f"  [{ok}] {header[1:].split(']')[0]}] score={score:.2f}  ({elapsed}s)", flush=True)
        return ep


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
    p.add_argument(
        "--concurrency", type=int, default=1,
        help="run up to N episodes in parallel (default 1 = sequential). "
             "Each concurrent episode uses ~400MB RAM + ~1 CPU core.",
    )
    args = p.parse_args()

    if args.concurrency < 1:
        raise SystemExit("--concurrency must be >= 1")

    picks = json.loads(Path(args.picks).read_text())
    if args.limit:
        picks = picks[: args.limit]
    total = len(picks)

    mode = "sequential" if args.concurrency == 1 else f"concurrency={args.concurrency}"
    print(f"Running {total} tasks, model={args.model} provider={args.provider} ({mode})", flush=True)

    sem = asyncio.Semaphore(args.concurrency)
    t0 = time.time()
    # Preserve pick order in output despite concurrent completion order.
    tasks = [
        asyncio.create_task(_run_one(i, total, pick, args=args, sem=sem))
        for i, pick in enumerate(picks, 1)
    ]
    results = await asyncio.gather(*tasks)
    wall = time.time() - t0

    passed = sum(1 for r in results if r.get("evaluation", {}).get("success"))
    avg = sum(r.get("evaluation", {}).get("score", 0.0) for r in results) / max(1, total)
    print(f"\nSUMMARY: {passed}/{total} passed, avg={avg:.3f}, wall={wall:.1f}s", flush=True)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "model": args.model,
        "provider": args.provider,
        "concurrency": args.concurrency,
        "n": total,
        "passed": passed,
        "avg_score": avg,
        "wall_seconds": wall,
        "results": results,
    }, indent=2, default=str))
    print(f"Wrote {out}", flush=True)


if __name__ == "__main__":
    asyncio.run(_main())
