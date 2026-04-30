"""Merge shard outputs from a pixel-mode slurm-array sweep into one summary.

Each shard (one slurm array task) writes its results to
``<base_dir>/shard_NN/{summary.json,run_manifest.json,tasks/...}``. After all
shards complete this script combines them into a single ``summary.json``,
``run_manifest.json``, and a unified ``tasks/`` tree (symlinks, no copies).

Usage:
    python scripts/pixel_aggregate.py /usr/xtmp/$USER/wab-runs/pixel-gemini5-12345
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def aggregate(base_dir: Path) -> dict:
    shard_dirs = sorted(base_dir.glob("shard_*"))
    if not shard_dirs:
        raise SystemExit(f"No shard_* subdirs found in {base_dir}")

    all_results: list[dict] = []
    trajectory_paths: list[str | None] = []
    walls: list[float] = []
    started_ats: list[str] = []
    ended_ats: list[str] = []
    manifests: list[dict] = []

    for sd in shard_dirs:
        sf = sd / "summary.json"
        mf = sd / "run_manifest.json"
        if not sf.exists():
            print(f"  WARN: missing {sf}", file=sys.stderr)
            continue
        s = json.loads(sf.read_text())
        for entry in s.get("results", []):
            all_results.append(entry)
            tpath = entry.get("trajectory_path")
            if tpath:
                trajectory_paths.append(f"{sd.name}/{tpath}")
            else:
                trajectory_paths.append(None)
        walls.append(float(s.get("wall_seconds", 0)))
        if s.get("started_at"):
            started_ats.append(s["started_at"])
        if s.get("ended_at"):
            ended_ats.append(s["ended_at"])
        if mf.exists():
            manifests.append(json.loads(mf.read_text()))

    n = len(all_results)
    passed = sum(1 for r in all_results if r.get("success"))
    avg = sum(r.get("score", 0.0) for r in all_results) / max(n, 1)

    summary = {
        "n_tasks": n,
        "n_shards": len(shard_dirs),
        "passed": passed,
        "avg_score": round(avg, 4),
        "wall_seconds_max": round(max(walls or [0.0]), 1),  # parallel runtime
        "wall_seconds_total_cpu": round(sum(walls), 1),     # equivalent serial cost
        "started_at": min(started_ats) if started_ats else None,
        "ended_at": max(ended_ats) if ended_ats else None,
        "results": [
            dict(entry, shard=sd.name)
            for sd, entry in zip(shard_dirs, all_results)
        ],
        # Re-list with shard prefixed paths for convenience
        "trajectory_paths": trajectory_paths,
    }

    # Single merged manifest — take the first one as base, include shard count
    if manifests:
        merged_manifest = dict(manifests[0])
        merged_manifest["n_shards"] = len(shard_dirs)
        merged_manifest["wall_seconds_max"] = summary["wall_seconds_max"]
        merged_manifest["wall_seconds_total_cpu"] = summary["wall_seconds_total_cpu"]
    else:
        merged_manifest = {"n_shards": len(shard_dirs)}

    (base_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    (base_dir / "run_manifest.json").write_text(json.dumps(merged_manifest, indent=2, default=str))

    # Build a symlink tree so `<base_dir>/tasks/<slug>/` resolves to the shard
    # that owns it. Skips re-linking on repeated runs.
    base_tasks = base_dir / "tasks"
    base_tasks.mkdir(exist_ok=True)
    linked = 0
    for sd in shard_dirs:
        st = sd / "tasks"
        if not st.is_dir():
            continue
        for entry in st.iterdir():
            tgt = base_tasks / entry.name
            if not tgt.exists():
                rel = os.path.relpath(entry, base_tasks)
                tgt.symlink_to(rel)
                linked += 1

    print(f"Aggregated {n} runs from {len(shard_dirs)} shards.")
    print(f"  passed: {passed}/{n}  avg: {avg:.3f}")
    print(f"  wall: max={summary['wall_seconds_max']:.0f}s (parallel) "
          f"vs total_cpu={summary['wall_seconds_total_cpu']:.0f}s (serial-equivalent)")
    print(f"  linked {linked} task dirs into {base_tasks}/")
    print(f"  wrote {base_dir}/summary.json and run_manifest.json")
    return summary


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("base_dir", help="Sweep root containing shard_* subdirs")
    args = p.parse_args()
    aggregate(Path(args.base_dir).resolve())


if __name__ == "__main__":
    main()
