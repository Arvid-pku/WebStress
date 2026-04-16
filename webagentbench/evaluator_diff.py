"""Diff-based evaluator — pure functions.

Implements the predicate evaluator for the canonical-diff grammar described in
``docs/superpowers/specs/2026-04-16-correctness-diff-design.md`` §3.2.

Public API (will grow in Tasks 3-6):
    eval_predicate(pred, scope) -> bool

The ``{expr: "..."}`` predicate reuses the restricted-globals pattern from the
legacy ``webagentbench/evaluator.py`` — no new security surface is introduced
here.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from webagentbench.evaluator import _fuzzy_eq

__all__ = ["PredicateScope", "eval_predicate"]


# ------------------------------------------------------------------
# Scope
# ------------------------------------------------------------------

@dataclass
class PredicateScope:
    """Bindings available to predicates when they are evaluated.

    Attributes:
        value: The concrete value the predicate is evaluating (bound to ``x``
            in ``expr`` predicates).
        target: The task's ``target`` dict (constants declared in the task
            YAML).
        initial: A snapshot of the pre-action state, if relevant.
        state: A reference to the current full state, if relevant.
        bijection_var: The loop variable from a surrounding bijection, if any
            (bound to ``v`` in ``expr`` predicates).
        session_start: The session start time, if relevant (bound to
            ``session_start`` in ``expr`` predicates).
    """

    value: Any
    target: dict = field(default_factory=dict)
    initial: Any = None
    state: Any = None
    bijection_var: Any = None
    session_start: datetime | None = None


# ------------------------------------------------------------------
# Safe-builtins allowlist for the {expr: "..."} predicate.
# Mirrors webagentbench/evaluator.py line 65, expanded with types the
# canonical-diff expressions legitimately need (Decimal, datetime, etc.).
# ------------------------------------------------------------------

_SAFE_BUILTINS = {
    "str": str,
    "int": int,
    "float": float,
    "len": len,
    "bool": bool,
    "list": list,
    "dict": dict,
    "set": set,
    "tuple": tuple,
    "sum": sum,
    "min": min,
    "max": max,
    "any": any,
    "all": all,
    "range": range,
    "abs": abs,
    "round": round,
    "sorted": sorted,
    "Decimal": Decimal,
    "datetime": datetime,
    "timedelta": timedelta,
}


def _expr_scope(scope: PredicateScope) -> dict[str, Any]:
    """Build the locals dict passed to the restricted eval for ``{expr: "..."}``."""
    return {
        "x": scope.value,
        "v": scope.bijection_var,
        "target": scope.target,
        "initial": scope.initial,
        "state": scope.state,
        "session_start": scope.session_start,
        "now": lambda: datetime.now(timezone.utc),
    }


# ------------------------------------------------------------------
# matches_semantic support
# ------------------------------------------------------------------

def _semantic_match(a: Any, b: Any, threshold: float) -> bool:
    """Fuzzy text-similarity match.

    Falls back to ``_fuzzy_eq`` (exact / numeric-tolerance) first so callers
    who supplied numbers or exact-equal strings short-circuit cheaply; then
    uses ``difflib.SequenceMatcher.ratio()`` to gate on textual similarity.
    The legacy ``_fuzzy_eq`` is binary — it does not accept a threshold — so
    this wrapper is necessary to implement the spec's configurable cutoff.
    """
    if _fuzzy_eq(a, b):
        return True
    if a is None or b is None:
        return False
    sa = str(a)
    sb = str(b)
    return difflib.SequenceMatcher(None, sa, sb).ratio() >= threshold


# ------------------------------------------------------------------
# eval_predicate
# ------------------------------------------------------------------

def eval_predicate(pred: dict, scope: PredicateScope) -> bool:
    """Evaluate a single predicate against ``scope.value``.

    Predicate grammar is specified in the canonical-diff design doc §3.2.
    ``pred`` must be a single-key dict; the key selects the predicate kind.
    """
    if not isinstance(pred, dict) or len(pred) != 1:
        raise ValueError(
            f"predicate must be a single-key dict, got {pred!r}"
        )

    key = next(iter(pred))
    arg = pred[key]
    value = scope.value

    # ── scalar ────────────────────────────────────────────────────
    if key == "eq":
        return value == arg
    if key == "in":
        return value in arg
    if key == "between":
        lo, hi = arg
        return lo <= value <= hi
    if key == "any":
        return True

    # ── collection ────────────────────────────────────────────────
    if key == "set_eq":
        return set(value) == set(arg)
    if key == "subset":
        return set(value).issubset(set(arg))
    if key == "superset":
        return set(value).issuperset(set(arg))
    if key == "contains":
        return arg in value
    if key == "length":
        inner_scope = PredicateScope(
            value=len(value),
            target=scope.target,
            initial=scope.initial,
            state=scope.state,
            bijection_var=scope.bijection_var,
            session_start=scope.session_start,
        )
        return eval_predicate(arg, inner_scope)

    # ── text ──────────────────────────────────────────────────────
    if key == "substring":
        return arg in (value or "")
    if key == "substring_all":
        haystack = value or ""
        return all(s in haystack for s in arg)
    if key == "substring_any":
        haystack = value or ""
        return any(s in haystack for s in arg)
    if key == "regex":
        return re.search(arg, value or "") is not None
    if key == "matches_semantic":
        # Two shapes: {matches_semantic: "text"} or
        # {matches_semantic: {"value" | "s": "text", "threshold": 0.9}}.
        if isinstance(arg, dict):
            target_text = arg.get("value", arg.get("s"))
            threshold = float(arg.get("threshold", 0.8))
        else:
            target_text = arg
            threshold = 0.8
        return _semantic_match(value, target_text, threshold=threshold)

    # ── nested ────────────────────────────────────────────────────
    if key == "fields":
        if not isinstance(value, dict):
            return False
        for sub_field, sub_pred in arg.items():
            inner = PredicateScope(
                value=value.get(sub_field),
                target=scope.target,
                initial=scope.initial,
                state=scope.state,
                bijection_var=scope.bijection_var,
                session_start=scope.session_start,
            )
            if not eval_predicate(sub_pred, inner):
                return False
        return True

    # ── expr (restricted eval) ────────────────────────────────────
    if key == "expr":
        try:
            globs = {"__builtins__": _SAFE_BUILTINS}
            # Restricted eval — mirrors webagentbench/evaluator.py line 76.
            # Only the safe-builtins allowlist is exposed; expression source
            # is author-controlled (task YAML).
            return bool(eval(arg, globs, _expr_scope(scope)))  # noqa: S307
        except Exception:
            return False

    raise ValueError(f"unknown predicate key {key!r}")
