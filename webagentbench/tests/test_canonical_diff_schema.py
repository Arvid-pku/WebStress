"""Tests for the CanonicalDiff pydantic schema.

Covers the canonical_diff grammar defined in
``docs/superpowers/specs/2026-04-16-correctness-diff-design.md`` §3.1–§3.7.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from webagentbench.tasks.canonical_diff import (
    Bijection,
    CanonicalDiff,
    Constraint,
    CreateEntry,
    DeleteEntry,
    InvariantEntry,
    NamedInvariant,
    UpdateEntry,
)


def test_minimal_diff_parses() -> None:
    diff = CanonicalDiff.model_validate(
        {"invariant": [{"collection": "state.emails", "preserve": "ALL"}]}
    )
    assert len(diff.invariant) == 1
    assert diff.invariant[0].collection == "state.emails"


def test_create_entry_requires_entity() -> None:
    with pytest.raises(ValidationError):
        CreateEntry.model_validate({"properties": {"foo": {"eq": "bar"}}})


def test_bijection_entry_parses() -> None:
    entry = CreateEntry.model_validate(
        {
            "entity": "Appointment",
            "bijection": {"over": "target.due_ids", "variable": "v"},
            "properties": {
                "provider_id": {"in": "target.admin_providers[v]"},
                "status": {"eq": "scheduled"},
            },
        }
    )
    assert entry.entity == "Appointment"
    assert entry.bijection is not None
    assert entry.bijection.variable == "v"
    assert entry.bijection.over == "target.due_ids"
    assert entry.properties["status"] == {"eq": "scheduled"}


def test_update_entry_requires_where() -> None:
    with pytest.raises(ValidationError):
        UpdateEntry.model_validate(
            {"entity": "Email", "changes": {"is_read": {"eq": True}}}
        )


def test_named_invariant_ref_grammar() -> None:
    # Valid refs
    for ref in ("invariant[0]", "create[2]", "update[0]", "delete[0]"):
        named = NamedInvariant.model_validate({"name": "X", "ref": ref})
        assert named.ref == ref

    # "invariant" without brackets is invalid
    with pytest.raises(ValidationError):
        NamedInvariant.model_validate({"name": "X", "ref": "invariant"})

    # Unknown kind
    with pytest.raises(ValidationError):
        NamedInvariant.model_validate({"name": "X", "ref": "foo[0]"})


def test_constraints_block() -> None:
    c = Constraint.model_validate(
        {
            "desc": "no overlapping appointments",
            "expr": "not any(a.start == b.start for a in ...)",
            "severity": "high",
        }
    )
    assert c.severity == "high"
    assert c.desc == "no overlapping appointments"
