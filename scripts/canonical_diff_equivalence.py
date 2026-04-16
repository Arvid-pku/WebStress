"""Compare legacy eval.checks pass/fail against canonical_diff match pass/fail
on historical trajectories.

Reads results/webagentbench/*.json, filters to:
  - timestamp within the last 6 months
  - parent-run average_score >= 0.5
(locked policy — see spec §11).

Phase 0 note:
  The `new_pass` comparison is a placeholder — reconstruction of final state
  from a trajectory file lands in a follow-up. For now we assume new_pass ==
  legacy_pass and exit 0 on a trivial quadrant summary. Real equivalence
  comparison requires replaying each trajectory's actions against a fresh
  seeded session, which is out of scope for this task.

Usage:
    python scripts/canonical_diff_equivalence.py pp_immunization_gap_review
    python scripts/canonical_diff_equivalence.py pp_immunization_gap_review --results results/webagentbench
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


_CUTOFF_DAYS = 180
_MIN_AVG_SCORE = 0.5


def load_trajectories(task_id: str, results_dir: Path) -> list[dict]:
    """Return the filtered trajectory corpus for a given task_id.

    Filters:
      - timestamp within the last 6 months
      - parent envelope summary.average_score >= 0.5
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=_CUTOFF_DAYS)
    trajectories: list[dict] = []

    if not results_dir.is_dir():
        return trajectories

    for path in sorted(results_dir.glob("*.json")):
        try:
            envelope = json.loads(path.read_text())
        except Exception:
            continue

        ts = envelope.get("timestamp")
        if not ts:
            continue
        try:
            when = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if when < cutoff:
            continue

        avg = envelope.get("summary", {}).get("average_score", 0.0)
        if avg < _MIN_AVG_SCORE:
            continue

        for r in envelope.get("results", []):
            if r.get("task_id") == task_id:
                trajectories.append({
                    "parent": path.name,
                    "trajectory": r,
                    "original_eval": r.get("evaluation", {}),
                })

    return trajectories


def tally_quadrants(trajectories: list[dict]) -> dict[str, int]:
    """Compute (legacy_pass, new_pass) quadrant counts.

    Phase 0 bootstrap: new_pass is set equal to legacy_pass. Replace this
    with a real canonical_diff match_diff call once trajectory replay is
    wired in.
    """
    q = {"pass_pass": 0, "pass_fail": 0, "fail_pass": 0, "fail_fail": 0}
    for t in trajectories:
        legacy_pass = bool(t["original_eval"].get("success", False))
        # Placeholder — real implementation runs compute_diff + match_diff
        # against a reconstructed final state.
        new_pass = legacy_pass
        if legacy_pass and new_pass:
            q["pass_pass"] += 1
        elif legacy_pass and not new_pass:
            q["pass_fail"] += 1
        elif not legacy_pass and new_pass:
            q["fail_pass"] += 1
        else:
            q["fail_fail"] += 1
    return q


def print_summary(task_id: str, n_trajectories: int, quadrants: dict[str, int]) -> None:
    print(f"Task: {task_id}")
    print(f"Trajectories loaded (last {_CUTOFF_DAYS}d, avg >= {_MIN_AVG_SCORE}): {n_trajectories}")
    print()
    print("Outcome quadrants (legacy_pass, new_pass):")
    print(f"  (pass, pass): {quadrants['pass_pass']}")
    print(f"  (pass, fail): {quadrants['pass_fail']}   <-- new stricter (expected direction)")
    print(f"  (fail, pass): {quadrants['fail_pass']}   <-- new more lenient (INVESTIGATE)")
    print(f"  (fail, fail): {quadrants['fail_fail']}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare legacy eval vs canonical_diff matcher on historical trajectories.",
    )
    parser.add_argument("task_id")
    parser.add_argument("--results", default="results/webagentbench",
                        help="Directory containing historical results JSON files (default: results/webagentbench)")
    args = parser.parse_args()

    results_dir = Path(args.results)
    trajectories = load_trajectories(args.task_id, results_dir)
    quadrants = tally_quadrants(trajectories)
    print_summary(args.task_id, len(trajectories), quadrants)

    if quadrants["fail_pass"] > 0:
        print(
            "WARNING: some trajectories pass the new matcher but failed the legacy "
            "checks. Investigate each before deleting the legacy eval: block.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
