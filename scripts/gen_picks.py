"""Generate a `picks` JSON array from the human assignments YAML.

Each pick is a ``{"task_id", "variant_filename", "env", "diff", "cond"}`` entry
consumed by ``scripts/run_picks.py`` to drive a batch evaluation run.

Subsets supported:
  primary    — primary_panel: 70 base tasks × 2 conditions (clean + intervention) = 140
  duplicate  — duplicate_subset: 35 task-conditions (both clean and intervention mixed)
  both       — primary ∪ duplicate, deduped by (task_id, variant_filename)

Filters:
  --env ENV ...      only keep these environments
  --diff DIFF ...    only keep these difficulty tiers (easy|medium|hard|expert|frontier)
  --cond {clean,intervention,both}
                     only keep this condition (default: both)

Source of truth: webagentbench/human/assignments_v1.yaml
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSIGNMENTS = REPO_ROOT / "webagentbench" / "human" / "assignments_v1.yaml"


def _parse_flow_rows(section_text: str) -> list[dict]:
    """Parse the flow-style YAML rows the assignments file uses for entries.

    Each entry is one line like ``- {aid: "...", role: primary, ..., base: X, ...}``.
    We pull out the fields we care about with targeted regex rather than a full
    YAML parser, because the flow-style one-liners are narrow and the shape is
    stable.
    """
    rows = []
    for line in section_text.splitlines():
        line = line.strip()
        if not line.startswith("- {"):
            continue
        base = re.search(r"\bbase:\s*([A-Za-z0-9_]+)", line)
        env = re.search(r"\benv:\s*([A-Za-z0-9_]+)", line)
        diff = re.search(r"\bdiff:\s*([a-z]+)", line)
        cond = re.search(r"\bcond:\s*([a-z]+)", line)
        variant_yaml = re.search(r"\bvariant:\s*\{[^}]*yaml:\s*([^\s,}]+)", line)
        if not (base and env and cond):
            continue
        rows.append({
            "base": base.group(1),
            "env": env.group(1),
            "diff": diff.group(1) if diff else None,
            "cond": cond.group(1),
            "variant_yaml": variant_yaml.group(1) if variant_yaml else None,
        })
    return rows


def load_rows(assignments_path: Path) -> tuple[list[dict], list[dict]]:
    src = assignments_path.read_text()
    prim_head = src.index("condition_assignments:")
    dup_head = src.index("duplicate_condition_assignments:")
    primary = _parse_flow_rows(src[prim_head:dup_head])
    duplicate = _parse_flow_rows(src[dup_head:])
    return primary, duplicate


def build_base_variant_map(primary: list[dict], duplicate: list[dict]) -> dict[str, str]:
    """Map base_task_id → variant YAML filename (for intervention condition)."""
    m: dict[str, str] = {}
    for row in primary + duplicate:
        if row["cond"] == "intervention" and row["variant_yaml"]:
            m.setdefault(row["base"], Path(row["variant_yaml"]).name)
    return m


def rows_to_picks(
    rows: list[dict],
    *,
    base_to_variant: dict[str, str],
    cond_filter: str,
    expand_both_conditions: bool,
) -> list[dict]:
    """Convert YAML rows into pick entries.

    If ``expand_both_conditions`` is True, every unique base task expands into
    (clean, intervention) regardless of the row's own cond field — this is
    the "35 base × 2" interpretation of duplicate_subset.

    If False, each row becomes exactly one pick matching its own cond.
    """
    picks: list[dict] = []
    if expand_both_conditions:
        seen = set()
        for row in rows:
            b = row["base"]
            if b in seen:
                continue
            seen.add(b)
            if cond_filter in ("clean", "both"):
                picks.append({
                    "task_id": b,
                    "variant_filename": None,
                    "env": row["env"],
                    "diff": row["diff"],
                    "cond": "clean",
                })
            if cond_filter in ("intervention", "both"):
                picks.append({
                    "task_id": b,
                    "variant_filename": base_to_variant.get(b),
                    "env": row["env"],
                    "diff": row["diff"],
                    "cond": "intervention",
                })
    else:
        for row in rows:
            if cond_filter != "both" and row["cond"] != cond_filter:
                continue
            picks.append({
                "task_id": row["base"],
                "variant_filename": Path(row["variant_yaml"]).name if row["variant_yaml"] else None,
                "env": row["env"],
                "diff": row["diff"],
                "cond": row["cond"],
            })
    return picks


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument(
        "--subset",
        choices=["primary", "duplicate", "both"],
        required=True,
        help="primary = 140 panel, duplicate = 70 (35×2), both = union",
    )
    p.add_argument(
        "--cond",
        choices=["clean", "intervention", "both"],
        default="both",
        help="condition filter (default both)",
    )
    p.add_argument("--env", nargs="*", help="environment filter (amazon booking gmail ...)")
    p.add_argument(
        "--diff",
        nargs="*",
        choices=["easy", "medium", "hard", "expert", "frontier"],
        help="difficulty tier filter",
    )
    p.add_argument(
        "--assignments",
        type=Path,
        default=ASSIGNMENTS,
        help=f"path to assignments YAML (default {ASSIGNMENTS})",
    )
    p.add_argument("--output", "-o", type=Path, required=True, help="write picks JSON here")
    args = p.parse_args()

    primary, duplicate = load_rows(args.assignments)
    base_to_variant = build_base_variant_map(primary, duplicate)

    if args.subset == "primary":
        picks = rows_to_picks(
            primary,
            base_to_variant=base_to_variant,
            cond_filter=args.cond,
            expand_both_conditions=False,
        )
    elif args.subset == "duplicate":
        picks = rows_to_picks(
            duplicate,
            base_to_variant=base_to_variant,
            cond_filter=args.cond,
            expand_both_conditions=True,
        )
    else:
        a = rows_to_picks(
            primary,
            base_to_variant=base_to_variant,
            cond_filter=args.cond,
            expand_both_conditions=False,
        )
        b = rows_to_picks(
            duplicate,
            base_to_variant=base_to_variant,
            cond_filter=args.cond,
            expand_both_conditions=True,
        )
        seen = set()
        picks = []
        for pk in a + b:
            key = (pk["task_id"], pk["variant_filename"])
            if key in seen:
                continue
            seen.add(key)
            picks.append(pk)

    if args.env:
        picks = [p for p in picks if p["env"] in set(args.env)]
    if args.diff:
        picks = [p for p in picks if p["diff"] in set(args.diff)]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(picks, indent=2))

    from collections import Counter
    by_env = Counter(p["env"] for p in picks)
    by_diff = Counter(p["diff"] for p in picks)
    by_cond = Counter(p["cond"] for p in picks)
    print(f"wrote {len(picks)} picks → {args.output}")
    print(f"  by env:  {dict(by_env)}")
    print(f"  by diff: {dict(by_diff)}")
    print(f"  by cond: {dict(by_cond)}")


if __name__ == "__main__":
    main()
