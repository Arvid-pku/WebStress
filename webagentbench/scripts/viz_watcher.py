"""Incremental trajectory visualizer.

Watches results/bedrock_subset/ for per-task result JSONs written by
run_bedrock_subset.py, merges whatever has completed so far into one envelope,
and regenerates webagentbench/static/bedrock_subset_viz.html every ``interval``
seconds. Open http://127.0.0.1:8080/static/bedrock_subset_viz.html (or the
/trajectories page) at any point to see current progress — no need to wait
for the full 112-task run to finish.

Usage:
    python -m webagentbench.scripts.viz_watcher
    python -m webagentbench.scripts.viz_watcher --interval 10
    python -m webagentbench.scripts.viz_watcher --once    # single pass
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def _env_from_task(task_id: str) -> str:
    prefix = task_id.split("_", 1)[0]
    return {"rh": "robinhood", "pp": "patient_portal"}.get(prefix, prefix)


def _tag(result: dict, *, configuration: str, variant_filename: str | None) -> dict:
    tagged = dict(result)
    base = tagged.get("task_id", "")
    tagged["task_id"] = f"{base}__{configuration}"
    tagged["base_task_id"] = base
    tagged["configuration"] = configuration
    if variant_filename:
        tagged.setdefault("degradation", {})
        tagged["degradation"].setdefault("variant_filename", variant_filename)
    return tagged


def _collect(results_dir: Path) -> list[dict]:
    """Read every standard_*.json and stress_*.json that exists, produce a
    uniformly-tagged list of result entries."""
    aggregated: list[dict] = []

    for path in sorted(results_dir.glob("standard_*.json")):
        try:
            envelope = json.loads(path.read_text())
        except Exception:
            continue
        for r in envelope.get("results", []):
            aggregated.append(_tag(r, configuration="standard", variant_filename=None))

    for path in sorted(results_dir.glob("stress_*.json")):
        try:
            envelope = json.loads(path.read_text())
        except Exception:
            continue
        for r in envelope.get("results", []):
            variant_filename = None
            deg = r.get("degradation") or envelope.get("degradation") or {}
            if isinstance(deg, dict):
                variant_filename = deg.get("variant_filename")
            if not variant_filename:
                variant_filename = f"{path.stem.removeprefix('stress_')}.yaml"
            aggregated.append(_tag(r, configuration="degraded", variant_filename=variant_filename))

    return aggregated


def _envelope(results: list[dict], model: str, provider: str, manifest_version: str) -> dict:
    total = len(results)
    passed = sum(1 for r in results if r.get("evaluation", {}).get("success"))
    scores = [r.get("evaluation", {}).get("score", r.get("evaluation", {}).get("final_score", 0.0)) for r in results]
    steps = [r.get("agent", {}).get("steps", 0) for r in results]
    times = [r.get("agent", {}).get("elapsed_seconds", 0) for r in results]
    return {
        "benchmark": "WebAgentBench",
        "version": manifest_version,
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
            "in_progress": True,
        },
    }


def _rebuild(results_dir: Path, *, model: str, provider: str,
             root: Path, expected_total: int) -> tuple[int, int, Path]:
    """One regeneration pass. Returns (count, passed, viz_path)."""
    from webagentbench.result_utils import build_manifest_task_meta, load_embedded_task_meta
    from webagentbench.visualize import generate_html

    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text())

    results = _collect(results_dir)
    envelope = _envelope(results, model, provider, manifest.get("version", ""))

    # Attach task_meta for the viz
    task_meta = load_embedded_task_meta(envelope)
    envelope["task_meta"] = {**build_manifest_task_meta(manifest), **task_meta}

    # Write merged.json snapshot + viz HTML
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "merged.json").write_text(json.dumps(envelope, indent=2, default=str))
    static_path = root / "static" / "bedrock_subset_viz.html"
    results_viz = results_dir / "viz.html"
    viz_html = generate_html(envelope, "http://127.0.0.1:8080")
    static_path.write_text(viz_html)
    results_viz.write_text(viz_html)

    passed = envelope["summary"]["passed"]
    return len(results), passed, static_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--interval", type=int, default=20, help="seconds between regenerations")
    parser.add_argument("--once", action="store_true", help="rebuild once and exit")
    parser.add_argument("--model", default="us.anthropic.claude-sonnet-4-6")
    parser.add_argument("--provider", default="bedrock")
    parser.add_argument("--expected", type=int, default=112, help="total trajectories expected")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    results_dir = root.parent / "results" / "bedrock_subset"

    if not results_dir.is_dir():
        print(f"Waiting for {results_dir} to appear...", flush=True)

    last_count = -1
    while True:
        try:
            count, passed, viz_path = _rebuild(
                results_dir,
                model=args.model, provider=args.provider, root=root,
                expected_total=args.expected,
            )
        except FileNotFoundError:
            count, passed, viz_path = 0, 0, root / "static" / "bedrock_subset_viz.html"
        if count != last_count:
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"[{ts}] {count}/{args.expected} trajectories  |  {passed} passed  |  {viz_path}",
                  flush=True)
            last_count = count
        if args.once or count >= args.expected:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
