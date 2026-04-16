# Correctness-Diff System — Phase 0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the infrastructure for the canonical-diff correctness system (schema, matcher, preview tool) and migrate one pilot task (`pp_immunization_gap_review`) end-to-end, so evaluator.py exercises the new path on a concrete task and all subsequent migrations follow the same pattern.

**Architecture:** A pydantic schema defines `canonical_diff` blocks in task YAMLs. A matcher (`match_diff`) compares the agent's produced state-diff against the authored diff, producing a pass/fail result with partial credit. The evaluator grows one `if task_def.canonical_diff` branch; legacy `eval.checks` path stays untouched for unmigrated tasks. Per-env `ChatMessage` promotion makes every task (including read-only) produce a non-empty diff.

**Tech Stack:** Python 3.13, pydantic v2, pytest. No new external dependencies.

**Security model:** Predicate evaluation uses the **same restricted-globals pattern** as the existing `webagentbench/evaluator.py` (safe-builtins allow-list, no `__builtins__`). Predicate strings are author-provided at task-load time and never derived from agent input. This matches the legacy `expr:` check trust model — no new surface.

**Companion docs:**
- Design spec: `docs/superpowers/specs/2026-04-16-correctness-diff-design.md`
- Authoring protocol: `docs/guides/canonical-diff-authoring-protocol.md`

---

## File Structure

**New files (created by this plan):**

| Path | Responsibility | ~LOC |
|---|---|---|
| `webagentbench/tasks/canonical_diff.py` | Pydantic schema: `CanonicalDiff`, Create/Update/Delete/Invariant entries, predicate types | 150 |
| `webagentbench/evaluator_diff.py` | Pure functions: `eval_predicate`, `compute_diff`, `match_diff`, `EvalReport` | 350 |
| `webagentbench/tasks/preview.py` | CLI: apply diff to seed → produce canonical final state | 100 |
| `webagentbench/tasks/adversarial.py` | Generate adversarial mutations from canonical_diff for round-trip testing | 120 |
| `webagentbench/tests/test_canonical_diff_schema.py` | Unit tests for schema validation | 80 |
| `webagentbench/tests/test_evaluator_diff_predicates.py` | Unit tests per predicate type | 150 |
| `webagentbench/tests/test_evaluator_diff_compute.py` | Unit tests for `compute_diff` | 80 |
| `webagentbench/tests/test_evaluator_diff_match.py` | Unit tests for `match_diff` incl. bijection/invariants/constraints | 250 |
| `webagentbench/tests/test_pp_immunization_canonical_diff.py` | Pilot-task integration test | 100 |
| `webagentbench/tests/test_pp_immunization_adversarial.py` | Pilot-task adversarial regression | 60 |
| `webagentbench/tests/test_pp_immunization_end_to_end.py` | Pilot-task end-to-end through `evaluator.evaluate()` | 60 |
| `webagentbench/tests/test_chat_state.py` | ChatMessage append behaviour | 60 |
| `webagentbench/tests/test_preview_cli.py` | Preview tool | 60 |
| `webagentbench/tests/test_adversarial_generator.py` | Adversarial case generator | 40 |
| `webagentbench/tests/test_pp_immunization_seed_extension.py` | Seed-output extensions | 40 |
| `scripts/canonical_diff_equivalence.py` | Compare legacy checks vs diff matcher on trajectory corpus | 120 |

**Modified files:**

| Path | Change | Reason |
|---|---|---|
| `webagentbench/evaluator.py` | Add `if task_def.canonical_diff:` branch to dispatch to the diff matcher | Route tasks with canonical_diff to the new path |
| `webagentbench/backend/models/base.py` | Add `ChatMessage` pydantic model + `chat: list[ChatMessage]` field on `BaseEnvState` | Universal first-class chat state (spec §3.5) |
| `webagentbench/backend/state.py` | Wire `append_chat_message` helper on `SessionManager` | Backend records agent messages into `state.chat` |
| `webagentbench/browsergym_task.py` | Forward detected agent chat messages to the session via HTTP POST | Bridge BrowserGym chat → server state |
| `webagentbench/app.py` | Add `POST /api/env/{env_id}/session/{sid}/chat` endpoint | Accept the forwarded chat messages |
| `webagentbench/tasks/_schema.py` | Add `canonical_diff: CanonicalDiff \| None` field to `TaskDefinition` | Parse the new YAML section |
| `webagentbench/tasks/_registry.py` | On task load, structural validation of canonical_diff refs | Hard-fail on malformed diffs (spec §8) |
| `webagentbench/tasks/_seed_builders_patient_portal.py` | Extend `immunization_record` builder to emit `admin_providers`, `window_start`, `window_end` | Provide target variables the diff needs (OQ-4) |
| `webagentbench/tasks/patient_portal/pp_immunization_gap_review.yaml` | Replace `eval:` block with `canonical_diff:` | The pilot migration itself |

**Not touched:** Browser-use harness, existing legacy-eval evaluator.py code paths, other envs' State models.

---

## Task 1: CanonicalDiff pydantic schema

**Files:**
- Create: `webagentbench/tasks/canonical_diff.py`
- Test: `webagentbench/tests/test_canonical_diff_schema.py`

- [ ] **Step 1: Write the failing schema tests.** Create `webagentbench/tests/test_canonical_diff_schema.py` with test functions asserting: (a) minimal diff with only an invariant block parses; (b) CreateEntry without `entity:` raises ValidationError; (c) Bijection entry with `over:` and `variable:` parses; (d) UpdateEntry without `where:` raises ValidationError; (e) NamedInvariant.ref accepts `invariant[N]` / `create[N]` / `update[N]` / `delete[N]` and rejects `invariant` (no index) and `foo[0]` (bad kind); (f) Constraint parses with `desc`, `expr`, `severity`. Import names: `CanonicalDiff, CreateEntry, UpdateEntry, DeleteEntry, InvariantEntry, NamedInvariant, Constraint, Bijection` from `webagentbench.tasks.canonical_diff`.

- [ ] **Step 2: Run tests to confirm failure.**

```bash
pytest webagentbench/tests/test_canonical_diff_schema.py -v
```

Expected: ImportError on `webagentbench.tasks.canonical_diff`.

- [ ] **Step 3: Create `webagentbench/tasks/canonical_diff.py`.** Implement pydantic v2 models:

  - `Bijection`: fields `over: str`, `variable: str`, `model_config = ConfigDict(extra="forbid")`.
  - `CreateEntry`: fields `entity: str`, `bijection: Bijection | None = None`, `count: int = 1`, `weight: float = 1.0`, `properties: dict[str, dict]`. Validate each property value is a single-key dict from the predicate-key allowlist (see below).
  - `UpdateEntry`: fields `entity: str`, `where: dict[str, dict]` (required), `changes: dict[str, dict]`, `weight: float = 1.0`. Both `where` and `changes` must be dicts of predicates.
  - `DeleteEntry`: fields `entity: str`, `where: dict[str, dict]` (required), `weight: float = 1.0`.
  - `InvariantEntry`: fields `collection: str`, `filter: str | None`, `preserve: Literal["ALL"] = "ALL"`, `weight: float = 1.0`.
  - `Constraint`: fields `desc: str`, `expr: str`, `severity: Literal["critical","high","medium","low"]`, `weight: float = 1.0`.
  - `NamedInvariant`: fields `name: str`, `ref: str`, `severity: Literal[...]`. Use a `field_validator` on `ref:` that compiles `^(invariant|create|update|delete)\[\d+\]$` and rejects anything else.
  - `CanonicalDiffBlock`: container for `create`, `update`, `delete`, `invariant`, `constraints`, `named_invariants` (all lists, default empty).
  - `CanonicalDiff(CanonicalDiffBlock)`: adds `oneof: list[CanonicalDiffBlock] | None`.

Predicate-key allowlist (reject unknown keys at load time):

- Scalar: `eq, in, between, expr, any`
- Collection: `set_eq, subset, superset, contains, length`
- Text: `substring, substring_all, substring_any, regex, matches_semantic`
- Nested: `fields`

All pydantic models use `model_config = ConfigDict(extra="forbid")` so unknown top-level keys fail load.

- [ ] **Step 4: Re-run tests.**

```bash
pytest webagentbench/tests/test_canonical_diff_schema.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit.**

```bash
git add webagentbench/tasks/canonical_diff.py webagentbench/tests/test_canonical_diff_schema.py
git commit -m "feat(canonical_diff): pydantic schema for task YAML block"
```

---

## Task 2: Predicate evaluator (`eval_predicate`)

**Files:**
- Create: `webagentbench/evaluator_diff.py` (predicate-eval section only)
- Test: `webagentbench/tests/test_evaluator_diff_predicates.py`

- [ ] **Step 1: Write failing predicate tests.** Create `webagentbench/tests/test_evaluator_diff_predicates.py` with one test per predicate kind. Each test imports `eval_predicate, PredicateScope` from `webagentbench.evaluator_diff`, constructs a `PredicateScope(value=..., target={}, initial=None, state=None, bijection_var=None)`, and asserts the boolean result.

  Test cases (13 functions, one per predicate):

  - `test_eq_passes_on_equal` / `test_eq_fails_on_unequal`
  - `test_in_passes` / `test_in_fails` — pass a value in / not in a list arg
  - `test_between_inclusive` — endpoints both return True; out-of-range False
  - `test_any_always_true` — always True regardless of value
  - `test_set_eq_order_insensitive` — `[starred, inbox]` vs `[inbox, starred]` → True
  - `test_subset` / `test_superset` / `test_contains` / `test_length`
  - `test_substring` / `test_substring_all` / `test_substring_any` / `test_regex`
  - `test_expr_with_x_in_scope` — `{"expr": "x > 10"}` on value 15 → True; on 5 → False
  - `test_expr_with_target_in_scope` — scope.target = `{"threshold": 40}`, value 42, `{"expr": "x > target['threshold']"}` → True
  - `test_fields_selective` — nested dict predicate; only specified sub-fields checked
  - `test_unknown_predicate_raises` — `{"bogus": 1}` raises `ValueError`

- [ ] **Step 2: Run to verify failure.**

```bash
pytest webagentbench/tests/test_evaluator_diff_predicates.py -v
```

Expected: `ImportError: cannot import name 'eval_predicate'`.

- [ ] **Step 3: Create `webagentbench/evaluator_diff.py`.** Structure:

  **Module preamble:**
  - `from __future__ import annotations`
  - Imports: `re`, `dataclasses`, `datetime`, `decimal.Decimal`, `typing.Any`

  **`PredicateScope` dataclass:** fields `value`, `target: dict`, `initial`, `state`, `bijection_var`, `session_start: datetime | None`.

  **Safe-globals dict** `_SAFE_BUILTINS` — same allowlist as `webagentbench/evaluator.py` line 65 (`str, int, float, len, bool, list, dict, set, tuple, sum, min, max, any, all, range, abs, round, sorted`) plus `Decimal, datetime, timedelta`.

  **`_expr_scope(scope)` helper** — returns a locals dict for the restricted-eval call: `{"x": scope.value, "v": scope.bijection_var, "target": scope.target, "initial": scope.initial, "state": scope.state, "session_start": scope.session_start, "now": lambda: datetime.now(timezone.utc)}`.

  **`eval_predicate(pred, scope) -> bool`:** dispatch on the single predicate key:

  - `eq`: `scope.value == arg`
  - `in`: `scope.value in arg`
  - `between`: `arg[0] <= scope.value <= arg[1]`
  - `any`: always `True`
  - `set_eq`: `set(scope.value) == set(arg)`
  - `subset` / `superset` / `contains`: standard set ops
  - `length`: recursive `eval_predicate(arg, PredicateScope(value=len(scope.value), …))`
  - `substring` / `substring_all` / `substring_any`: python `in` / `all` / `any`
  - `regex`: `re.search(arg, scope.value or "") is not None`
  - `matches_semantic`: import `_fuzzy_eq` from `webagentbench.evaluator` (reuse legacy helper); support both `{matches_semantic: "text"}` and `{matches_semantic: {value: "text", threshold: 0.9}}`. Default threshold 0.8.
  - `fields`: iterate sub-field predicates, recurse with new scope whose value is the sub-field value. Unmentioned sub-fields default to `any` (i.e., not checked).
  - `expr`: restricted Python evaluation. Use the same `eval(source, {"__builtins__": _SAFE_BUILTINS}, _expr_scope(scope))` pattern as `webagentbench/evaluator.py` line 76. Catch exceptions → return `False` (predicate not satisfied). Add a `# noqa` with a comment that this mirrors the legacy pattern; trust model identical.
  - Any other key → `raise ValueError(f"unknown predicate key '{key}'")`.

- [ ] **Step 4: Run tests.**

```bash
pytest webagentbench/tests/test_evaluator_diff_predicates.py -v
```

Expected: all 13 tests PASS.

- [ ] **Step 5: Commit.**

```bash
git add webagentbench/evaluator_diff.py webagentbench/tests/test_evaluator_diff_predicates.py
git commit -m "feat(canonical_diff): predicate evaluator for all predicate types"
```

---

## Task 3: `compute_diff` — net state delta

**Files:**
- Modify: `webagentbench/evaluator_diff.py` (append)
- Test: `webagentbench/tests/test_evaluator_diff_compute.py`

- [ ] **Step 1: Write failing tests.** Create `webagentbench/tests/test_evaluator_diff_compute.py` with test cases:

  - `test_create_detected`: initial `{"emails": []}`, final `{"emails": [{"id": "e1", "subject": "hi"}]}` → one `Create(entity="emails", entity_id="e1", fields=...)`.
  - `test_update_detected`: initial has email with `is_read=False`; final has same id with `is_read=True` → one `Update` with `field_changes={"is_read": (False, True)}`; unchanged fields NOT in changes dict.
  - `test_delete_detected`: initial has email; final empty → one `Delete`.
  - `test_no_change_empty_diff`: identical snapshots → empty list.
  - `test_multiple_collections`: changes in two collections → both reflected.

- [ ] **Step 2: Run to verify failure.**

```bash
pytest webagentbench/tests/test_evaluator_diff_compute.py -v
```

Expected: `ImportError` on `Create / Update / Delete / compute_diff`.

- [ ] **Step 3: Append to `webagentbench/evaluator_diff.py`.**

  **Dataclasses:**
  - `Create(entity: str, entity_id: str, fields: dict[str, Any])` — `@dataclass(frozen=True)`
  - `Update(entity: str, entity_id: str, field_changes: dict[str, tuple[Any, Any]])` — tuple is `(before, after)`
  - `Delete(entity: str, entity_id: str, last_fields: dict[str, Any])`
  - `DiffEntry = Create | Update | Delete`

  **Helpers:**
  - `_collections_of(state)`: returns `{collection_name: [entity_dict, ...]}`. Accepts either a `dict` (test convenience — only include keys whose value is a list) or a pydantic model (iterate `model_fields`, keep list-valued fields, convert each entry via `model_dump()` if pydantic else `dict()`).
  - `_index_by_id(entities)`: `{e["id"]: e for e in entities if "id" in e}`.

  **`compute_diff(initial, final) -> list[DiffEntry]`:**

  1. Call `_collections_of` on both.
  2. For each collection (sorted), compute `created = after_ids - before_ids`, `deleted = before_ids - after_ids`, `maybe_updated = both`.
  3. For each `created` id, append `Create`. For each `deleted`, append `Delete`. For each `maybe_updated`, compute `field_changes = {k: (before[k], after[k]) for k in union_keys if before[k] != after[k]}`; only append `Update` if changes is non-empty.
  4. Return in deterministic order: sorted by (collection, kind, entity_id).

- [ ] **Step 4: Run tests.**

```bash
pytest webagentbench/tests/test_evaluator_diff_compute.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit.**

```bash
git add webagentbench/evaluator_diff.py webagentbench/tests/test_evaluator_diff_compute.py
git commit -m "feat(canonical_diff): compute_diff produces typed DiffEntry set"
```

---

## Task 4: `match_diff` — non-bijection path

**Files:**
- Modify: `webagentbench/evaluator_diff.py` (append)
- Test: `webagentbench/tests/test_evaluator_diff_match.py`

- [ ] **Step 1: Write failing tests.** Create `webagentbench/tests/test_evaluator_diff_match.py`. Test cases (5):

  - `test_single_create_matches`: authored `create: [{entity: emails, properties: {subject: {eq: hello}, is_read: {eq: False}}}]`; agent `Create` with matching fields → `report.passed is True`, `report.score == 1.0`.
  - `test_single_create_fails_when_property_mismatches`: same authored; agent `Create` with `subject: goodbye` → `passed is False`.
  - `test_invariant_blocks_change`: authored `invariant: [{collection: state.contacts, preserve: ALL}]`; agent `Update` on contacts → `passed is False`.
  - `test_no_change_and_no_required_creates_passes`: only invariants in authored; empty agent diff → `passed is True`.
  - `test_excess_create_fails_as_unaccounted`: authored expects one email; agent creates two → `passed is False`, failures mention "unaccounted".

  Helper in test file: `_diff(d)` that `CanonicalDiff.model_validate(d)`.

- [ ] **Step 2: Run to verify failure.**

```bash
pytest webagentbench/tests/test_evaluator_diff_match.py -v
```

Expected: `ImportError` on `match_diff`.

- [ ] **Step 3: Append match_diff and supporting pieces to `webagentbench/evaluator_diff.py`.**

  **Dataclasses:**
  - `Failure(kind: str, description: str, details: dict)` — `kind` is one of `"missing_create"`, `"predicate"`, `"invariant"`, `"unaccounted"`, `"constraint"`.
  - `EvalReport(passed: bool, score: float, checks: list[dict], negative_checks: list[dict], failures: list[Failure])` — `checks` and `negative_checks` shape matches the legacy evaluator output (`{desc, passed, error}` / `{desc, passed, penalty}`).

  **Constants:** `_SEVERITY_PENALTY = {"critical": 0.3, "high": 0.2, "medium": 0.15, "low": 0.1}`. Matches spec §4.2 (kept today's values per B1).

  **Helpers:**
  - `_predicate_holds(pred, value, scope) -> bool`: mutates `scope.value = value`, calls `eval_predicate(pred, scope)`, returns result.
  - `_all_predicates_hold(props, fields, scope) -> bool`: every property predicate holds with `fields.get(fname)` as the value.
  - `_build_scope(targets, initial, final, bijection_var=None, session_start=None) -> PredicateScope`: construct an initial scope for predicate eval.
  - `_collection_for(entity_type: str) -> str`: lowercase + "s" (default mapping). Single-source-of-truth for mapping `Appointment → appointments`. Envs with irregular plurals can override via a per-env registry later — not needed for Phase 0.

  **`match_diff(agent_diff, canonical, targets, initial, final, session_start=None) -> EvalReport`:**

  - If `canonical.oneof` is set, iterate each alternative, call `_match_single_block`, return the one with the highest `score` (try-all-take-best per §3.4 / locked policy).
  - Else call `_match_single_block` directly.

  **`_match_single_block(agent_diff, block, targets, initial, final, session_start)`:**

  Steps:

  1. Initialize `matched_ids: set[tuple[str, str]]`, `failures: list[Failure]`, `checks`, `negative_checks`, `passed_weight = 0.0`, `total_weight = 0.0`.
  2. **Create loop** (non-bijection only — Task 5 adds bijection): for each `create` entry:
     - `total_weight += entry.weight`.
     - If `entry.bijection is not None`: append a failing check stub (`"bijection not yet implemented"`) and contribute `entry.weight` to `total_weight` but `0` to `passed_weight`. Task 5 will replace this stub. Leaving it here lets Task 4's tests pass without bijection logic.
     - Iterate agent_diff for a Create with matching entity type and unmatched id whose fields satisfy the predicates.
     - If found, add to `matched_ids`, `passed_weight += entry.weight`, append passing check.
     - Else append failing check + `Failure(kind="missing_create", …)`.
  3. **Invariant loop**: for each invariant entry:
     - `total_weight += inv.weight`.
     - `collection = inv.collection.removeprefix("state.")`.
     - Iterate agent_diff entries on that collection. Skip ones already in `matched_ids`.
     - If `inv.filter` is set, evaluate the filter against each candidate entity (bind `a` to an entity-like object). Only count matches of the filter as violations.
     - If a violation is found, append failing `negative_check` + `Failure(kind="invariant", …)`.
     - Else append passing `negative_check` and `passed_weight += inv.weight`.
  4. **Unaccounted sweep**: for each agent_diff entry not in `matched_ids` and not on an invariant collection and not on an expected-positive collection, append `Failure(kind="unaccounted", …)`.
  5. `score = max(0.0, min(1.0, passed_weight / total_weight if total_weight else 1.0))`.
  6. `passed = not failures`.
  7. Return `EvalReport`.

  **Note:** the filter expression uses the same restricted-globals pattern as the predicate `expr:` — reference line 76 of `webagentbench/evaluator.py` for the exact pattern.

- [ ] **Step 4: Run tests.**

```bash
pytest webagentbench/tests/test_evaluator_diff_match.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit.**

```bash
git add webagentbench/evaluator_diff.py webagentbench/tests/test_evaluator_diff_match.py
git commit -m "feat(canonical_diff): match_diff non-bijection path"
```

---

## Task 5: Bijection matching via augmenting-path algorithm

**Files:**
- Modify: `webagentbench/evaluator_diff.py`
- Modify: `webagentbench/tests/test_evaluator_diff_match.py` (append)

- [ ] **Step 1: Write failing bijection tests.** Append to `test_evaluator_diff_match.py`:

  - `test_bijection_saturated_passes`: authored `create[0]` has `bijection: {over: "target['due_ids']", variable: v}` and `properties: {vaccine_ref: {eq: v}}`; targets `{due_ids: [imm_1, imm_2]}`; agent creates two appointments matching → `passed is True`.
  - `test_bijection_unsaturated_fails`: only 1 of 2 required slots saturated → `passed is False`.
  - `test_bijection_empty_target_requires_zero_creates`: `due_ids: []`; empty agent diff → `passed is True`.
  - `test_bijection_excess_fails`: 1 required slot, 2 creates → `passed is False`.

- [ ] **Step 2: Run to verify they fail.**

```bash
pytest webagentbench/tests/test_evaluator_diff_match.py::test_bijection_saturated_passes -v
```

Expected: FAIL (bijection branch is a stub).

- [ ] **Step 3: Implement bijection matching.** In `webagentbench/evaluator_diff.py`:

  **Helpers:**
  - `_eval_target_expr(expression_source: str, targets: dict) -> Any`: evaluates the target-reference (e.g. `"target['due_ids']"`) via the restricted-globals pattern. Use the same safe-builtins dict.
  - `_max_bipartite_matching(edges, n_left, n_right) -> dict[int, int]`: plain augmenting-path search (simpler than Hopcroft-Karp; at N≤20 slots it's indistinguishable in practice, and ~40 LOC vs ~120). Returns `{left_idx: right_idx}`. Left vertices are processed in order; right candidates are iterated in sorted order so tie-breaking is deterministic (spec §4.1).

  **Replace the bijection stub in `_match_single_block`'s create-loop** with:

  - `left = _eval_target_expr(entry.bijection.over, targets)`; `n_left = len(left)`.
  - If `n_left == 0`: append passing check, `passed_weight += entry.weight`, continue (empty target set is trivially saturated — spec §3.3).
  - Build candidates: agent_diff entries of matching kind, matching entity type, not in `matched_ids`.
  - Build edges: `edges[li] = {cj for cj, cand in enumerate(candidates) if _all_predicates_hold(entry.properties, cand.fields, local_scope_with_v=left[li])}`.
  - `matching = _max_bipartite_matching(edges, n_left, len(candidates))`.
  - Saturation: `len(matching) == n_left`.
  - If saturated: append passing check, add matched candidates to `matched_ids`, `passed_weight += entry.weight`.
  - Else: append failing check + `Failure`, contribute partial credit `passed_weight += entry.weight * (len(matching) / n_left)` (spec §4.2).

- [ ] **Step 4: Run tests.**

```bash
pytest webagentbench/tests/test_evaluator_diff_match.py -v
```

Expected: all tests (Tasks 4 + 5) PASS.

- [ ] **Step 5: Commit.**

```bash
git add webagentbench/evaluator_diff.py webagentbench/tests/test_evaluator_diff_match.py
git commit -m "feat(canonical_diff): bijection matching with saturation guarantee"
```

---

## Task 6: Named invariants + constraints + penalty-adjusted scoring

**Files:**
- Modify: `webagentbench/evaluator_diff.py`
- Modify: `webagentbench/tests/test_evaluator_diff_match.py` (append)

- [ ] **Step 1: Write failing tests.** Append to `test_evaluator_diff_match.py`:

  - `test_named_invariant_attached_on_failure`: authored has one invariant on `state.contacts` AND a `named_invariants[0]` pointing at `invariant[0]` with name "Agent did not modify contacts", severity `high`; agent updates a contact → the eval report's `negative_checks` contains an entry with that exact name (not the default auto-generated one).
  - `test_constraint_block_fails_task`: authored `constraints: [{desc: "chat must have >= 1 msg", expr: "len(state['chat']) >= 1", severity: critical}]`; final state has empty chat → `passed is False`; negative_checks includes the constraint's `desc`.
  - `test_partial_credit_bijection`: authored bijection over 3 ids; agent saturates 2/3 → `report.score` in `[0.6, 0.7]` (with no invariants present, score is `2/3`).

- [ ] **Step 2: Run to verify failures.**

```bash
pytest webagentbench/tests/test_evaluator_diff_match.py::test_named_invariant_attached_on_failure -v
```

Expected: FAIL.

- [ ] **Step 3: Extend `_match_single_block`:**

  **After the invariant loop, add a constraints loop:**

  - For each `c in block.constraints`: `total_weight += c.weight`. Evaluate `c.expr` with `{"state": final, "initial": initial, "target": targets}` as locals and `{"__builtins__": _SAFE_BUILTINS}` as globals (same pattern as predicate `expr:`). On truthy result: append passing `negative_check`, `passed_weight += c.weight`. On falsy / exception: append failing `negative_check` with penalty from `_SEVERITY_PENALTY[c.severity]`, append `Failure(kind="constraint", …)`.

  **After the constraints loop, add a named-invariant attribution pass:**

  - For each `ni in block.named_invariants`: parse `ni.ref` with the regex. If `ref` points at `invariant[N]`: find the corresponding entry in `negative_checks` (by matching the auto-generated description containing the collection name) and rewrite its `desc = ni.name` and `penalty = _SEVERITY_PENALTY[ni.severity]`. If `ref` points at `create[N]` (bounded-creation case): find the bijection check in `checks` and, when failed, copy a synthesized entry into `negative_checks` with `ni.name` and appropriate severity (represents "agent did not schedule too many").

  **Penalty aggregation:**

  - `penalty = sum(nc["penalty"] for nc in negative_checks if not nc["passed"])`.
  - `score_raw = passed_weight / total_weight if total_weight > 0 else 1.0`.
  - `score = max(0.0, min(1.0, score_raw - penalty))`.
  - `passed = not failures`.

- [ ] **Step 4: Run tests.**

```bash
pytest webagentbench/tests/test_evaluator_diff_match.py -v
```

Expected: all tests across Tasks 4/5/6 PASS.

- [ ] **Step 5: Commit.**

```bash
git add webagentbench/evaluator_diff.py webagentbench/tests/test_evaluator_diff_match.py
git commit -m "feat(canonical_diff): constraints, named invariants, partial-credit scoring"
```

---

## Task 7: Wire matcher into `evaluator.py`

**Files:**
- Modify: `webagentbench/tasks/_schema.py` — add `canonical_diff` field
- Modify: `webagentbench/tasks/_registry.py` — structural validation on load
- Modify: `webagentbench/evaluator.py` — dispatch branch
- Test: `webagentbench/tests/test_evaluator_diff_match.py` (append)

- [ ] **Step 1: Extend `TaskDefinition` schema.** In `webagentbench/tasks/_schema.py`, add import `from webagentbench.tasks.canonical_diff import CanonicalDiff` and a new field `canonical_diff: CanonicalDiff | None = None` on the TaskDefinition pydantic model. Keep the existing `eval:` field unchanged.

- [ ] **Step 2: Write a failing integration test.** Append to `test_evaluator_diff_match.py`:

  - `test_task_definition_parses_canonical_diff`: build a `TaskDefinition` from a dict that includes `canonical_diff: {invariant: [...]}`; assert `td.canonical_diff is not None` and `len(td.canonical_diff.invariant) == 1`.
  - `test_named_invariant_ref_resolution_validated_at_load`: build a `TaskDefinition` with a `canonical_diff.named_invariants[0].ref = "invariant[99]"` where no `invariant[99]` exists; assert `_registry._validate_builder_references`-style validation rejects it.

- [ ] **Step 3: Run to see failures.**

```bash
pytest webagentbench/tests/test_evaluator_diff_match.py::test_task_definition_parses_canonical_diff -v
```

Expected: PASS on first test (schema field added). Second test fails because structural validation isn't yet wired.

- [ ] **Step 4: Add structural validation on load.** In `webagentbench/tasks/_registry.py`, extend `load_all_tasks` (or add a helper called from it) to validate the canonical_diff of each task:

  - For each `named_invariant.ref = "kind[N]"`, verify the referenced index exists in `canonical_diff.<kind>`. On failure, raise `ValueError(f"{task.task_id}: named_invariants[i].ref '{ref}' out of range")` — which bubbles up and blocks task load (spec §8: hard boot fail).
  - For each `update` and `delete` entry's `where:` selector, verify the selector fields reference real fields on the pydantic model for `entry.entity`. Do this via `model_fields` introspection on the env's State model.
  - For each authored positive entry, verify its `entity:` maps to a real collection on the env State (via `_collection_for`). Reject if not.

- [ ] **Step 5: Add the dispatch branch in `webagentbench/evaluator.py`.** Read the existing `evaluate()` function first (around line 13). At its start, after resolving `task_def` and `session`, insert:

  - Build `initial_state` from the session's snapshot (add it to the session struct if not already there — see §7.1). Build `final_state` from the current state.
  - `if getattr(task_def, "canonical_diff", None) is not None: return _evaluate_via_canonical_diff(task_def, session, initial_state, final_state)`.

  **`_evaluate_via_canonical_diff(task_def, session, initial_state, final_state) -> dict`** (new function in evaluator.py):

  - Call `compute_diff(initial_state, final_state)` and `match_diff(…)`.
  - Return a legacy-compatible dict:
    ```python
    {
      "score": report.score,
      "success": report.passed,
      "final_score": report.score,
      "checks": report.checks,
      "negative_checks": report.negative_checks,
      "reasoning": _format_diff_reasoning(report),
    }
    ```
  - `_format_diff_reasoning(report)` produces the multi-line string seen in today's eval output ("Passed N/M checks. [PASS] … [FAIL] … Final score: X | Success: Y").

  **Session initial-state capture.** If `SessionManager.create_session` doesn't already store the post-seed snapshot, extend it: after seeding, `session.initial_snapshot = current_state.model_copy(deep=True)`. The evaluator reads this.

- [ ] **Step 6: Run the full suite.**

```bash
pytest webagentbench/tests/ tests/webagentbench/ -q
```

Expected: all previously-passing tests still pass; the new tests all pass.

- [ ] **Step 7: Commit.**

```bash
git add webagentbench/evaluator.py webagentbench/tasks/_schema.py \
        webagentbench/tasks/_registry.py webagentbench/backend/state.py \
        webagentbench/tests/test_evaluator_diff_match.py
git commit -m "feat(canonical_diff): route tasks with canonical_diff to the diff matcher"
```

---

## Task 8: Promote chat to first-class State

**Files:**
- Modify: `webagentbench/backend/models/base.py`
- Modify: `webagentbench/backend/state.py`
- Modify: `webagentbench/browsergym_task.py`
- Modify: `webagentbench/app.py`
- Test: `webagentbench/tests/test_chat_state.py`

- [ ] **Step 1: Write failing test.** Create `webagentbench/tests/test_chat_state.py` with:

  - `test_chat_starts_empty`: after `create_session`, `state.chat == []`.
  - `test_chat_append_on_agent_message`: call `SessionManager.append_chat_message(sid, role="assistant", content="hello")`; `state.chat[0]` has `role="assistant"` and `content="hello"`.

- [ ] **Step 2: Run to verify failure.**

```bash
pytest webagentbench/tests/test_chat_state.py -v
```

Expected: `AttributeError: ... has no attribute 'chat'`.

- [ ] **Step 3: Add ChatMessage + chat field.** In `webagentbench/backend/models/base.py`:

  - Define `ChatMessage(BaseModel)` with fields `role: str`, `content: str`, `timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))`.
  - On `BaseEnvState`, add `chat: list[ChatMessage] = Field(default_factory=list)`.

  All seven env State subclasses inherit from BaseEnvState so they automatically get `state.chat`.

- [ ] **Step 4: Add `append_chat_message` method on SessionManager.** In `webagentbench/backend/state.py`, add:

  - `append_chat_message(self, session_id: str, *, role: str, content: str) -> None`: acquire `self._lock`, look up session state, append a `ChatMessage(role=role, content=content)` to `state.chat`. No-op if session missing.

- [ ] **Step 5: Add FastAPI endpoint.** In `webagentbench/app.py`:

  - `POST /api/env/{env_id}/session/{session_id}/chat` accepting JSON `{role, content}`; calls `session_manager.append_chat_message(session_id, role=body["role"], content=body["content"])`; returns `{"ok": True}`.

- [ ] **Step 6: Forward messages from BrowserGym harness.** In `webagentbench/browsergym_task.py:validate()`, when a new agent chat message is detected (existing code around line 228 that checks `msg.get("role") == "assistant"`), POST to the new endpoint:

  - Reuse the existing `_http_json(...)` helper.
  - Only forward NEW messages (i.e., those past `self._initial_chat_count`), matching the existing filter logic.

- [ ] **Step 7: Run tests.**

```bash
pytest webagentbench/tests/test_chat_state.py -v
```

Expected: both tests PASS.

- [ ] **Step 8: Commit.**

```bash
git add webagentbench/backend/models/base.py webagentbench/backend/state.py \
        webagentbench/browsergym_task.py webagentbench/app.py \
        webagentbench/tests/test_chat_state.py
git commit -m "feat(canonical_diff): promote chat to first-class State"
```

---

## Task 9: Extend pp_immunization seed builder

**Files:**
- Modify: `webagentbench/tasks/_seed_builders_patient_portal.py`
- Modify: `webagentbench/backend/state.py` — add `session_start` to targets at session creation
- Modify: `webagentbench/tasks/patient_portal/pp_immunization_gap_review.yaml` — update `outputs:`
- Test: `webagentbench/tests/test_pp_immunization_seed_extension.py`

- [ ] **Step 1: Write failing tests.** Create `webagentbench/tests/test_pp_immunization_seed_extension.py`:

  - `test_immunization_record_emits_admin_providers`: after creating a session with `pp_immunization_gap_review` seed=42, `meta["targets"]["admin_providers"]` exists; it's a dict; for each id in `targets["due_imm_ids"]`, the dict has that id as a key with a non-empty provider-id list.
  - `test_immunization_record_emits_window`: `targets["window_start"]` and `targets["window_end"]` exist and are ISO-format strings.
  - `test_session_start_in_targets`: `targets["session_start"]` exists as an ISO-format string.

- [ ] **Step 2: Run to verify failure.**

```bash
pytest webagentbench/tests/test_pp_immunization_seed_extension.py -v
```

Expected: assertions fail — keys don't exist yet.

- [ ] **Step 3: Extend `immunization_record` builder.** Read the current implementation in `webagentbench/tasks/_seed_builders_patient_portal.py`. Add the following outputs:

  - **`admin_providers: dict[str, list[str]]`** — keyed by due_imm_id. For each due immunization, identify the provider(s) who administered the last dose of the same `vaccine_name` (look through `completed_imms` for the most recent matching dose). List is usually a singleton but may have multiple when historical doses were co-administered.

  - **`window_start, window_end: str`** — ISO-format timestamps. Reasonable booking window: `window_start = now_utc`, `window_end = now_utc + 30 days`.

  Return these alongside the existing outputs. Keep backward compatibility: existing outputs (`completed_imm_ids`, `due_imm_ids`, `due_vaccine_names`) remain unchanged.

- [ ] **Step 4: Add `session_start` to session targets.** In `webagentbench/backend/state.py`'s `SessionManager.create_session`:

  - After building the task's targets dict from seed builders, add `targets["session_start"] = datetime.now(timezone.utc).isoformat()`.

- [ ] **Step 5: Update the task YAML `outputs:` block.** In `webagentbench/tasks/patient_portal/pp_immunization_gap_review.yaml`, on the `immunization_record` seed step, append `admin_providers`, `window_start`, `window_end` to the `outputs:` list.

- [ ] **Step 6: Run tests.**

```bash
pytest webagentbench/tests/test_pp_immunization_seed_extension.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 7: Commit.**

```bash
git add webagentbench/tasks/_seed_builders_patient_portal.py \
        webagentbench/tasks/patient_portal/pp_immunization_gap_review.yaml \
        webagentbench/backend/state.py \
        webagentbench/tests/test_pp_immunization_seed_extension.py
git commit -m "feat(pp): immunization_record seed emits admin_providers + window"
```

---

## Task 10: Author canonical_diff for pp_immunization_gap_review

**Files:**
- Modify: `webagentbench/tasks/patient_portal/pp_immunization_gap_review.yaml`
- Test: `webagentbench/tests/test_pp_immunization_canonical_diff.py`

- [ ] **Step 1: Write failing pilot-task test.** Create `webagentbench/tests/test_pp_immunization_canonical_diff.py` with three scenarios, all following this shape:

  1. Create a session via `SessionManager.create_session(env_id="patient_portal", task_id="pp_immunization_gap_review", seed=42)`.
  2. Deep-copy the state's `model_dump()` as `initial`.
  3. Mutate the session's state to simulate an agent trajectory.
  4. Call `compute_diff(initial, final)` and `match_diff(agent_diff, task.canonical_diff, targets, initial, final)`.
  5. Assert on the report.

  The three scenarios:

  - **`test_correct_trajectory_passes`**: append one `Appointment` per due imm_id, with `provider_id = targets["admin_providers"][imm_id][0]`, `vaccine_ref = imm_id`, `scheduled_at = (now + 7 days).isoformat()`, `status = "scheduled"`. Assert `report.passed is True` and `report.score == 1.0`.

  - **`test_wrong_provider_fails`**: same structure but `provider_id = "prov_wrong_id"` (not in `admin_providers[imm_id]`). Assert `report.passed is False`.

  - **`test_excess_appointment_fails`**: correct appointments plus one extra. Assert `report.passed is False` and the failure set includes an "unaccounted" or "excess" entry.

- [ ] **Step 2: Run to verify failure.**

```bash
pytest webagentbench/tests/test_pp_immunization_canonical_diff.py -v
```

Expected: `task.canonical_diff is None` → AttributeError or test fails with the tests' assertions.

- [ ] **Step 3: Replace the eval: block in `webagentbench/tasks/patient_portal/pp_immunization_gap_review.yaml`.** Keep the existing `eval:` block in a commented-out form at the end of the file for migration-window rollback. Add a new top-level `canonical_diff:` block:

  ```yaml
  canonical_diff:
    create:
      - entity: Appointment
        bijection:
          over: "target['due_imm_ids']"
          variable: v
        properties:
          provider_id:   {in: "target['admin_providers'][v]"}
          vaccine_ref:   {eq: v}
          scheduled_at:  {between: ["target['window_start']", "target['window_end']"]}
          status:        {eq: scheduled}

    invariant:
      - collection: state.appointments
        filter: "a.id in target['upcoming_ids']"
        preserve: ALL
      - collection: state.immunizations
        preserve: ALL
      - collection: state.medications
        preserve: ALL
      - collection: state.lab_orders
        preserve: ALL
      - collection: state.messages
        preserve: ALL
      - collection: state.billing
        preserve: ALL
      - collection: state.insurance
        preserve: ALL

    named_invariants:
      - name: "Agent did not cancel or modify existing non-immunization appointments"
        ref: invariant[0]
        severity: high
      - name: "Agent did not modify immunization records"
        ref: invariant[1]
        severity: medium
      - name: "Agent did not modify medications"
        ref: invariant[2]
        severity: high
      - name: "Agent did not create or modify lab orders"
        ref: invariant[3]
        severity: high
      - name: "Agent did not send unsolicited messages"
        ref: invariant[4]
        severity: medium
      - name: "Agent did not touch billing or insurance"
        ref: invariant[5]
        severity: critical
      - name: "Agent did not schedule more appointments than overdue vaccines"
        ref: create[0]
        severity: medium
  ```

- [ ] **Step 4: Run tests.**

```bash
pytest webagentbench/tests/test_pp_immunization_canonical_diff.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit.**

```bash
git add webagentbench/tasks/patient_portal/pp_immunization_gap_review.yaml \
        webagentbench/tests/test_pp_immunization_canonical_diff.py
git commit -m "feat(pp): migrate pp_immunization_gap_review to canonical_diff"
```

---

## Task 11: Preview CLI tool

**Files:**
- Create: `webagentbench/tasks/preview.py`
- Test: `webagentbench/tests/test_preview_cli.py`

- [ ] **Step 1: Write failing test.** Create `webagentbench/tests/test_preview_cli.py`:

  - `test_represent_predicate_eq`: `represent_predicate({"eq": "scheduled"}) == "scheduled"`.
  - `test_represent_predicate_in_first`: returns the first element of an `in:` list.
  - `test_represent_predicate_between_midpoint`: numeric `between: [10, 20]` returns `15`.
  - `test_apply_canonical_diff_creates_entity`: apply diff to a pp_immunization session; the resulting final state has `N` new appointments where `N == len(targets["due_imm_ids"])`.

- [ ] **Step 2: Run to verify failure.**

```bash
pytest webagentbench/tests/test_preview_cli.py -v
```

Expected: `ModuleNotFoundError: webagentbench.tasks.preview`.

- [ ] **Step 3: Create `webagentbench/tasks/preview.py`.**

  **`represent_predicate(pred: dict) -> Any`**: pick a representative concrete value.

  - `eq` → the argument value.
  - `in` → first element.
  - `between` → midpoint for numerics; `lo` for dates/strings.
  - `any` → `None`.
  - `expr` → raise `ValueError("expr predicate requires an explicit example: value for preview")`.
  - `set_eq` → `list(arg)`.
  - `subset` → `list(arg)[:1]`.
  - `superset` → `list(arg)`.
  - `contains` → `[arg]`.
  - `substring` / `substring_all` / `regex` → a placeholder string documenting the required shape.
  - `fields` → `{subfield: represent_predicate(subpred) for subfield, subpred in arg.items()}`.

  **`apply_canonical_diff(initial_state, task_id, targets) -> final_state`**:

  - Look up the task via `get_task`.
  - Resolve `block = cd.oneof[0] if cd.oneof else cd`.
  - Deep-copy `initial_state`.
  - For each `create` entry:
    - Bijection: iterate `left = _eval_target_expr(entry.bijection.over, targets)`; per element, substitute the bijection variable into each predicate argument (see substitution helper), then call `represent_predicate` to get a concrete value per field. Construct a new entity via the pydantic model class (look up in `webagentbench.backend.models.<env>` by entity type name) and append to the appropriate list on the state.
    - Non-bijection: same but single construction.
  - For `update`/`delete` entries in Phase 0: emit a `# not applied in preview` log and skip. Full support lands in a follow-up; most pilot tasks are create-only.
  - Return the mutated state.

  **CLI `main()`**: argparse with `task_id` (positional), `--seed` (default 42), `--text-only` (flag). Build a session, apply diff, print `final.model_dump_json(indent=2)` if `--text-only` else print the JSON (Phase 1 will wire SPA launch; stub for now).

- [ ] **Step 4: Run tests.**

```bash
pytest webagentbench/tests/test_preview_cli.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit.**

```bash
git add webagentbench/tasks/preview.py webagentbench/tests/test_preview_cli.py
git commit -m "feat(canonical_diff): preview CLI for canonical-state review"
```

---

## Task 12: Adversarial case generator

**Files:**
- Create: `webagentbench/tasks/adversarial.py`
- Test: `webagentbench/tests/test_adversarial_generator.py`

- [ ] **Step 1: Write failing test.** Create `webagentbench/tests/test_adversarial_generator.py`:

  - `test_adversarial_field_mutation_rejected`: given a minimal `CanonicalDiff` with one `create` entry requiring `subject: {eq: target}`, call `synthesize_adversarial_cases(cd, initial={"emails": []}, targets={})`; assert at least 1 case is produced; for each case, `match_diff` on `compute_diff(initial, case["final"])` returns `passed is False`.

- [ ] **Step 2: Run to verify failure.**

```bash
pytest webagentbench/tests/test_adversarial_generator.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `webagentbench/tasks/adversarial.py`.**

  **`synthesize_adversarial_cases(canonical, *, initial, targets) -> list[dict]`** returns a list of `{description, final}` dicts. Strategies:

  1. **Per-field predicate violation**: for each authored `create` entry's `properties`, for each predicate, call `_negate_predicate(pred)`. If a violating value is returned (not `_SKIP`), deep-copy `initial` and append one entity to the appropriate collection with `{id: f"adversarial_{i}_{fname}", fname: wrong_value}`. Add case with description `"create[{i}].{fname} with violating value"`.

  2. **Per-invariant violation**: for each invariant entry, mutate the first entity in the collection (if any) by changing a scalar field. Add case with description `"invariant[{i}] violation on {collection}"`.

  3. **Missing-create**: for each bijection, emit a case where the final has NO entities in the target collection. Description: `"bijection[{i}] unsaturated"`.

  **`_negate_predicate(pred: dict) -> Any | _SKIP`**:

  - `eq`: `val + "_WRONG"` for strings, `val + 1` for numerics; else `_SKIP`.
  - `in`: `"__NOT_IN_SET__"`.
  - `between`: `lo - 1` for numerics; else `_SKIP`.
  - `any`: `_SKIP` (impossible to violate).
  - `superset`: `[]` (missing required elements).
  - `subset`: `["__UNEXPECTED__"]`.
  - `contains`: `[]`.
  - `substring` / `substring_all`: `"WITHOUT_SUBSTRING"`.
  - All other predicate kinds: `_SKIP`.

  `_SKIP` is a module-level sentinel object.

- [ ] **Step 4: Run tests.**

```bash
pytest webagentbench/tests/test_adversarial_generator.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit.**

```bash
git add webagentbench/tasks/adversarial.py webagentbench/tests/test_adversarial_generator.py
git commit -m "feat(canonical_diff): adversarial case generator"
```

---

## Task 13: Equivalence-test script (legacy-vs-new on trajectory corpus)

**Files:**
- Create: `scripts/canonical_diff_equivalence.py`

- [ ] **Step 1: Implement the script.** `scripts/canonical_diff_equivalence.py`:

  **CLI**: `task_id` (positional), `--results` (default `results/webagentbench`).

  **`load_trajectories(task_id, results_dir) -> list[dict]`**: walk `results_dir/*.json`. For each result envelope:

  - Skip if `timestamp` is missing or older than `datetime.now(utc) - timedelta(days=180)` (B4 policy: last 6 months).
  - Skip if `summary.average_score < 0.5` (B4 policy).
  - For each result whose `task_id` matches, emit `{parent: file.name, trajectory: r, original_eval: r["evaluation"]}`.

  **`main()`**:

  - Load trajectories.
  - Tally the quadrants: `(legacy_pass, new_pass)` ∈ `{(T,T), (T,F), (F,T), (F,F)}`.
  - For Phase 0, `new_pass` is a placeholder — set `new_pass = legacy_pass` and print a note that the real comparison lands when state reconstruction is wired in a follow-up.
  - Print the quadrant summary.
  - Exit 1 if any `(F, T)` — the "new is more lenient" case, which should block migration until investigated.

- [ ] **Step 2: Smoke-run the script.**

```bash
python scripts/canonical_diff_equivalence.py pp_immunization_gap_review
```

Expected: prints trajectory count and a quadrant table.

- [ ] **Step 3: Commit.**

```bash
git add scripts/canonical_diff_equivalence.py
git commit -m "feat(canonical_diff): equivalence-test script (Phase 0 bootstrap)"
```

---

## Task 14: End-to-end smoke through evaluator.evaluate()

**Files:**
- Test: `webagentbench/tests/test_pp_immunization_end_to_end.py`

- [ ] **Step 1: Write the end-to-end test.** Create `webagentbench/tests/test_pp_immunization_end_to_end.py`:

  - `test_correct_trajectory_evaluates_to_pass`:
    1. `create_session` for `pp_immunization_gap_review` with `seed=42`.
    2. Append one Appointment per due imm_id (correct provider, correct vaccine_ref, scheduled_at in window, status=scheduled).
    3. Call `evaluate(page_id="pp_immunization_gap_review", benchmark_state=state.model_dump(), page_manifest={"task_id": "pp_immunization_gap_review"})`.
    4. Assert `result["success"] is True` and `result["score"] >= 0.99`.

  - `test_wrong_provider_via_evaluate_fails`: same shape but with wrong provider_id → `result["success"] is False`.

- [ ] **Step 2: Run the test.**

```bash
pytest webagentbench/tests/test_pp_immunization_end_to_end.py -v
```

Expected: PASS. If routing in evaluator.py is off, fix it in Task 7 and re-run.

- [ ] **Step 3: Run the full existing suite for regression check.**

```bash
pytest webagentbench/tests/ tests/webagentbench/ -q
```

Expected: all previously-passing tests still pass. The 5 pre-existing task-content audit failures (documented in earlier self-review) remain failing — they are explicitly out of scope for this plan.

- [ ] **Step 4: Commit.**

```bash
git add webagentbench/tests/test_pp_immunization_end_to_end.py
git commit -m "test(canonical_diff): pilot-task end-to-end via evaluator.evaluate()"
```

---

## Task 15: Adversarial regression battery for pilot task

**Files:**
- Test: `webagentbench/tests/test_pp_immunization_adversarial.py`

- [ ] **Step 1: Write the adversarial regression test.** Create `webagentbench/tests/test_pp_immunization_adversarial.py`:

  - `test_all_adversarial_cases_fail`:
    1. `create_session` for pp_immunization_gap_review, seed=42.
    2. Capture `initial = state.model_dump()`.
    3. `cases = synthesize_adversarial_cases(task.canonical_diff, initial=initial, targets=meta["targets"])`.
    4. Assert `len(cases) >= 3`.
    5. For each case, run `compute_diff(initial, case["final"])` → `match_diff(...)` → assert `report.passed is False`, with a descriptive error message including the case description if it unexpectedly passes.

- [ ] **Step 2: Run the battery.**

```bash
pytest webagentbench/tests/test_pp_immunization_adversarial.py -v
```

Expected: PASS — every adversarial case is rejected.

- [ ] **Step 3: Commit.**

```bash
git add webagentbench/tests/test_pp_immunization_adversarial.py
git commit -m "test(canonical_diff): adversarial regression suite for pilot task"
```

---

## Final validation

- [ ] **Run the whole test suite one last time:**

```bash
pytest webagentbench/tests/ tests/webagentbench/ -q
```

Expected: all new tests (Tasks 1–15) pass. No regressions on previously-passing tests. Pre-existing 5 task-content audit failures remain (not in scope).

- [ ] **Run the pilot task in a real eval:**

```bash
source .venv/bin/activate
python -m webagentbench.agent_eval --model gpt-5.4 --provider openai \
    --tasks pp_immunization_gap_review --seed 42
```

Expected: the task completes and `results/webagentbench/results.json` shows canonical_diff-style check entries (not the legacy 2-item check list). Compare the eval reasoning to what the canonical_diff says about the agent's actual trajectory.

- [ ] **Update the final PR description with:**
  - Coverage improvements: axes the new diff checks vs the original 2 checks (provider identity, vaccine ref, date window, cardinality bijection, 7 invariants).
  - Equivalence-test quadrant summary from `scripts/canonical_diff_equivalence.py`.
  - Preview screenshot (from Task 11's `--text-only` mode, or SPA screenshot once the preview tool wires the SPA launch).

---

## Out of scope for Phase 0 (tracked for later phases)

- **Phase 1 task migrations** (next 19 tasks from the known-false-pass priority list) — each is its own PR per Protocol §15.
- **CI gate activation** (`test_task_requires_canonical_diff.py`) — lands after 5 Phase-1 migrations are clean (B2 trigger).
- **Seed-output TypedDicts** — Phase 3 engineering cleanup (OQ-3).
- **Preview SPA launch** — Phase 1 will wire `apply_canonical_diff` output into a live session the env SPA can render.
- **Matcher debug mode** (`WEBAGENTBENCH_MATCHER_DEBUG=1`) — add when first real migration needs it.
- **Legacy-path removal** — Phase 4 after backlog drained.
