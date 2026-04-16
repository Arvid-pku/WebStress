# Correctness-Diff Design for WebAgentBench Task Evaluation

**Date:** 2026-04-16
**Status:** Design
**Scope:** Evaluation architecture for all WebAgentBench tasks across the 7 environments (gmail, robinhood, amazon, booking, lms, patient_portal, reddit)

---

## 1  Problem

Tasks ship with shallow checks. Concrete example — `pp_immunization_gap_review`:

> *"Review your immunization record. For any vaccines that are overdue (past their next due date), schedule an appointment with the provider who administered the last dose of that vaccine."*

Current `eval.checks`:

1. `len(new_appointments) >= 1`
2. `len(new_appointments) >= len(due_imm_ids)`

These verify **count**. They do not verify:

- Each new appointment's `provider_id` equals the last-administering provider of some due vaccine.
- Each new appointment is linked to a specific overdue vaccine (not a generic appointment that coincidentally happens to exist).
- The bijection between new appointments and due vaccines is well-defined (one-to-one, not any-to-any).
- `scheduled_at` is in the future.
- No appointments on unrelated domains were touched.

The task scores 1.000 on trajectories that book *two random appointments with arbitrary providers*, which is wrong.

The root cause is **check authoring is bottom-up**: the author writes `expr:` strings derived from an unwritten mental model of correctness. Any axis the author's mental model omits is silently missing from the checks. This recurs across environments. The [eval-hardening-playbook.md](../../guides/eval-hardening-playbook.md) catalogues the patterns (§1.5 identity+correctness, §2 isolation, §6 selector-axis audit), but nothing **forces** authors to apply them, so tasks drift.

Previous attempts to fix this via conventions, audit tooling, or adversarial testing all share a weakness: they are **separate safety nets layered on top of hand-written checks**. Each net has a per-env hand-maintained table (identity-critical fields, instruction keyword maps, mutation templates). The tables drift the same way hand-written checks drift. The problem moves up a level; it is not fundamentally solved.

---

## 2  Design Principle: One Primitive

A task's correctness is fully captured by the relation `(initial_state, final_state) → {valid, invalid}`. Everything else — identity, cardinality, isolation, collateral, bijection, negative checks — is a derivable property of that relation.

We represent the relation with **one** primitive: the **canonical state diff**. An authored diff specifies the *minimum transformation from initial state to accepted final state*. Correctness is defined as:

> **Agent's observed state-diff ≡ authored state-diff**, under per-field tolerance on fields marked ambiguous.

All existing check categories collapse into this single property:

| Concern | How diff-equality handles it |
|---|---|
| Identity (right item) | Authored diff entry binds fields; agent diff entry must satisfy predicates |
| Correctness (right values) | Same — field-level predicates on entries |
| Cardinality | Number of authored entries = required count |
| Bijection | Bipartite matching across authored entries with target-parameterized bindings |
| Isolation | Agent diff entries unaccounted-for by authored entries → reject |
| Collateral | Same mechanism as isolation |

**Negative checks remain as a concept for interpretability** — they are *named invariants* layered on top of the diff, not a parallel enforcement system. See §5.

---

## 3  Data Model

### 3.1  The `canonical_diff` block

Replaces `eval.checks` / `eval.negative_checks` in task YAMLs:

```yaml
canonical_diff:
  create:
    - entity: Appointment
      bijection:
        over: target.due_imm_ids         # one entry per element of this set
        variable: v                      # bound name in predicates
      properties:
        provider_id:   {in: target.admin_providers[v]}
        vaccine_ref:   {eq: v.id}
        scheduled_at:  {between: [target.window_start, target.window_end]}
        status:        {eq: scheduled}

  update: []                              # existing entities whose fields must change

  delete: []                              # entities that must be removed

  invariant:
    - collection: state.appointments
      filter: "a.id in target.upcoming_ids"
      preserve: ALL                       # no fields may change
    - collection: state.medications
      preserve: ALL                       # medication list untouched
```

Three kinds of entries — `create`, `update`, `delete` — describe **required** changes. A fourth — `invariant` — describes **forbidden** changes on existing state. Together they bound both what the agent *must* do and what the agent *must not* do.

### 3.2  Predicate vocabulary

Every property binding is a predicate. Equality is the singleton-set case.

| Predicate | Meaning | Example |
|---|---|---|
| `{eq: x}` | Field value equals `x` | `{eq: scheduled}` |
| `{in: [...]}` | Field value is in the given set | `{in: target.admin_providers[v]}` |
| `{between: [lo, hi]}` | Numeric/date range (inclusive) | `{between: [target.week_start, target.week_end]}` |
| `{predicate: "<expr>"}` | Arbitrary boolean over the field value `x` and state | `{predicate: "len(x) > 0"}` |
| `{any: true}` | Explicit wildcard — field may take any value, recorded for audit | `{any: true}` |

Missing predicate on a field on an authored entry is a **compile error**: every field the entity schema marks as set-by-agent must either be bound or explicitly waived with `{any: true}`. (The schema is per-env, but the rule is universal: the compiler does not let an author silently omit a field.)

### 3.3  Bijection semantics

When a `create` / `update` entry has a `bijection:` block, it stands for *many* entries — one per element of the target set. The `variable:` name is bound inside all predicates of that entry.

Correctness under bijection: there must exist a **perfect matching** between the agent's new entities and the set `{v for v in bijection.over}` such that every pairing satisfies all property predicates with `v` bound to the paired target. If no perfect matching exists, the task fails. If multiple matchings exist, the task passes (symmetry is handled automatically).

### 3.4  Multi-valued correctness via disjunction

When the task admits genuinely different valid approaches (reply-or-forward, different action types), the author writes multiple `canonical_diff` blocks:

```yaml
canonical_diff:
  oneof:
    - create: [...]       # approach A: reply to the thread
    - create: [...]       # approach B: forward to the team
```

The agent's observed diff must match one. Not both.

---

## 4  Diff-Equality Algorithm

Given `authored_diff` and `agent_diff = diff(initial_state, final_state)`:

```
matched = set()
for each entry in authored_diff.{create, update, delete}:
    candidates = agent_diff entries of matching kind and entity type
    if entry has bijection:
        build bipartite graph:
            left  = elements of bijection.over
            right = candidates (excluding ones in `matched`)
            edge  = predicate satisfied
        find maximum matching
        require matching saturates the left side
        add matched right-side entries to `matched`
    else:
        require exactly one candidate (not in `matched`) whose fields satisfy predicates
        add it to `matched`

for each invariant entry:
    require no agent_diff entry touches the filtered collection

unmatched = agent_diff \ matched
require unmatched is empty (modulo `any:true` waivers)

success = all requirements hold
```

This is the whole enforcement engine. Bipartite matching uses standard Hopcroft-Karp (trivial at task-level sizes). Everything else is set arithmetic.

---

## 5  Named Invariants (Negative Checks, Kept for Interpretability)

The diff engine rejects *anything outside the authored diff*. That's correct but terse. A failing task output should say "*agent cancelled an existing appointment*", not just "*agent diff contained one unaccounted entry on appointments.status*". Named invariants give humans a vocabulary.

### 5.1  Declaration

Authors may optionally attach labeled invariants to the `canonical_diff`:

```yaml
canonical_diff:
  ...
  named_invariants:
    - name: "Agent did not cancel existing non-immunization appointments"
      derived_from: invariant[0]            # references diff.invariant entry by index
      severity: high
    - name: "Agent did not book more appointments than due vaccines"
      derived_from: cardinality(create[0])  # references the cardinality bound on a create entry
      severity: medium
```

The `derived_from:` field uses a small, closed grammar (not free text):

- `invariant[N]` — references the N-th entry in the diff's `invariant:` list.
- `cardinality(create[N])` — references the bijection/count bound on the N-th `create:` entry.
- `property(create[N].<field>)` — references a specific field predicate (e.g. `property(create[0].provider_id)`).
- `delete[N]` / `update[N]` — same convention for the other diff categories.

### 5.2  Compile-time verification

The compiler verifies each named invariant **structurally**: the `derived_from:` reference must resolve to a diff entry that exists and is of a kind capable of implying the invariant's name. The compiler does not attempt semantic implication (undecidable in general); it verifies:

1. The reference parses and resolves to a real diff entry.
2. The diff entry's *kind* matches the invariant's *shape*. A named invariant of the form "Agent did not X" must derive from an `invariant[]` entry (which forbids change) or a cardinality bound (which forbids excess); it cannot derive from a `create[]` property predicate (which asserts a positive fact).
3. The referenced entry is actually present in the diff.

This ensures a named invariant cannot reference a nonexistent or type-incompatible diff entry. **Named invariants are metadata; the diff is the truth.** The author writes human-readable labels; the compiler keeps them honest to the structure.

### 5.3  Runtime output

At evaluation time, when a diff mismatch occurs, the engine reports:

- Which authored entries failed to match, with predicate-level detail
- Which named invariants the unmatched agent-diff entries violated
- The existing `passed/failed` summary format in the runtime is preserved for backward compat (see §7)

---

## 6  Author Workflow: Canonical State Preview

The diff is **executable**. Applying it to the seeded initial state produces the canonical final state — exactly one concrete final state per element of the predicate's value range.

### 6.1  Preview command

```bash
python -m webagentbench.tasks.preview pp_immunization_gap_review --seed 42
```

Output:

1. Applies seed builders to produce `initial_state`.
2. For each predicate in the authored diff, picks a representative value:
   - `{eq: x}` → `x`
   - `{in: [...]}` → first element
   - `{between: [lo, hi]}` → midpoint
   - `{predicate: "..."}` → the author must provide an `example:` value alongside the predicate for preview to work (compile error otherwise)
   - `{any: true}` → retain the field's seed-time value; if the field is new on a created entity, use the env schema's default
   Then apply the resulting transformation to `initial_state`.
3. Opens the env SPA in a browser, pre-loaded with the canonical final state.

The author *looks at the UI* and confirms it matches the task's intended outcome. If the canonical state is obviously wrong (wrong provider shown, no vaccine linkage visible, date in the past), the author edits the diff and re-previews.

This is the mechanical replacement for the three-layer validation approach considered earlier (schema completeness + instruction keyword map + adversarial rejection). Visual review of the canonical final state catches axes the diff failed to bind, because those axes render with visibly-incorrect values.

### 6.2  Multi-diff preview

For `oneof:` blocks, the preview renders each alternative and labels them A/B/... so authors verify all alternatives are legitimately correct.

### 6.3  Bijection preview

For bijection entries with target sets of size N, the preview renders N concrete canonical states — one per target element — so the author sees each pairing.

---

## 7  Runtime Integration — Compile to YAML

The runtime is unchanged. The compiler writes generated checks back into the same task YAML in a marked block:

```yaml
# BEGIN GENERATED FROM canonical_diff — DO NOT EDIT BY HAND
eval:
  source: server_state
  checks:
    - expr: ...           # compiled from create[0].properties
      desc: ...
  negative_checks:
    - expr: ...           # compiled from invariant[0]
      desc: "Agent did not cancel existing non-immunization appointments"
      penalty: 0.2
# END GENERATED
```

- The `canonical_diff` block is the source of truth; the generated `eval:` block is always regenerable.
- Migration is per-task: any task can stay on hand-written checks until converted. The compiler only rewrites `eval:` when a `canonical_diff:` block is present.
- Git diffs remain reviewable. Generated checks are plain expr strings — same format as today, same runtime path, same evaluator logic.
- A CI check `scripts/assert_generated_blocks_are_fresh.py` fails if a `canonical_diff:` has been edited without regenerating. Prevents drift between source and generated.

---

## 8  Migration Strategy

The 507 existing tasks do not migrate in one pass.

**Phase 0 — infrastructure (no task changes):**
Build the compiler, preview tool, and CI freshness check. Ship behind a feature flag. Run it against one sample task end-to-end.

**Phase 1 — hardest-failing tasks first:**
Audit results (e.g. the pp_immunization_gap_review class) identify tasks with known check gaps. Convert these first; each conversion removes a real false-pass from the benchmark. Target: 20 tasks.

**Phase 2 — new tasks must use canonical_diff:**
Block merging any new task without a `canonical_diff:` block. Old tasks continue to work; the corpus only grows in the new format.

**Phase 3 — opportunistic backfill:**
When touching an existing task for any reason (seed update, instruction reword, evaluator fix), convert it to `canonical_diff` as part of the change. Target: 6 months to fully migrate.

**Phase 4 — remove legacy path:**
After full migration, the `eval.checks` hand-authored path is removed. Compiler becomes the only way to produce `eval:` blocks.

There is no coordination requirement. Any task can be migrated independently. Reversal (back to hand-written checks) is also trivial during the migration window — delete the `canonical_diff:` block, restore hand-written `eval:`.

---

## 9  What Stays, What Goes

**Stays:**
- The `eval:` runtime in `webagentbench/evaluator.py` — unchanged.
- The `expr:` check language for runtime evaluation — unchanged.
- The per-env pydantic state schemas (`backend/gmail/state.py`, etc.) — used by the compiler to know field types.
- Negative checks as a concept in eval output — retained for interpretability via named invariants.
- Penalty semantics — named invariants carry a `severity` which maps to existing penalty bands.

**Goes (after full migration):**
- Hand-authored `eval.checks` / `eval.negative_checks` blocks in YAMLs.
- The eval-hardening-playbook patterns §1.1–§1.6, §2.1–§2.5, §6 — these become compiler invariants; authors never re-derive them.
- The informal "audit procedure" in playbook §12.

**Goes immediately (not end-of-migration):**
- Nothing. The compiler is strictly additive in Phase 0–2. Existing tasks continue to run.

---

## 10  Component Boundaries

Three new files, three clear responsibilities:

| File | Responsibility | Dependencies |
|---|---|---|
| `webagentbench/tasks/_canonical_diff_schema.py` | Pydantic model for `canonical_diff` block + predicate vocabulary | pydantic only |
| `webagentbench/tasks/_canonical_diff_compiler.py` | Compile `canonical_diff` → `eval.checks`/`eval.negative_checks` expr strings; verify named invariants are implied by diff | `_canonical_diff_schema` + per-env state schema |
| `webagentbench/tasks/_canonical_diff_preview.py` | Apply diff to seeded state, open SPA for visual review | `_canonical_diff_schema` + runtime server |

Each file is testable in isolation. Compiler is a pure function (YAML in, YAML out); preview is an I/O wrapper. Schema has no runtime side effects.

---

## 11  Testing Strategy

The compiler's correctness is itself testable using the same primitive:

- **Golden-file tests:** a small corpus of canonical_diff YAMLs + expected compiled `eval:` blocks. CI diff-checks the output.
- **Round-trip tests:** for each golden diff, apply it to seed → verify the compiled checks pass. Mutate one field of the applied result → verify at least one compiled check fails.
- **Equivalence tests:** for each task migrated, both old hand-authored checks and new compiled checks are run on a corpus of historical agent trajectories (from `results/webagentbench/*.json`). Divergence flags either a compiler bug or a latent check bug in the original; both are fixed before deleting the hand-written version.

The equivalence test is the most valuable guardrail for migration: no task migrates without its compiled checks being proven equivalent-or-stricter than the hand-written ones on real trajectory data.

---

## 12  Open Questions

**OQ-1: Derived predicates evaluated at final-state time.**
Some instructions require predicates over state the agent discovers (e.g., "*reply to the sender who mentioned X*" where X is only visible in email bodies). This requires the predicate to be evaluated against `final_state` rather than seed-time targets. The `{predicate: "..."}` escape hatch covers this, but we haven't decided whether to make derived predicates a first-class category (alongside `eq`/`in`/`between`) or keep them under `predicate:`.

**OQ-2: Tolerance on nested objects.**
Fields like `Email.headers` are dicts. How does `{eq: {...}}` compare? Deep equality? Subset? We propose: dicts default to subset-equality unless the schema marks the field `strict`.

**OQ-3: Author-side type-checking.**
Predicates reference target-dict keys like `target.admin_providers[v]`. If the seed builder didn't emit `admin_providers`, the compile error should point at the seed, not the check. Needs a build-time link between seed-builder output schemas and canonical_diff predicate references.

**OQ-4: Seed builder additions.**
Several existing tasks lack the target data their new `canonical_diff` needs (e.g., immunization has no `admin_providers` output yet). Migrating those tasks requires extending the seed builder first. Is this in-scope for Phase 1 or a prerequisite?

These can be resolved during implementation planning — they do not change the architecture.

---

## 13  Success Criteria

The design succeeds if, once implemented and the first 20 tasks are migrated:

1. No task with a `canonical_diff:` block can pass an evaluation run where the agent produces a final state the author did not intend. (Verified by an adversarial trajectory corpus.)
2. Authors reviewing a canonical diff + preview UI consistently catch missing bindings that the previous hand-written-check review missed. (Verified by blind review test: give authors two versions of a task, one with a known gap, and measure catch rate.)
3. Migrated tasks show measurable pass-rate drops on agents known to produce near-correct-but-wrong trajectories (baseline GPT-5.4 browser-use). A drop indicates the new checks caught gaps the old checks missed.
4. The playbook's §1-§2 patterns are deleted from the docs — the compiler enforces them structurally.
