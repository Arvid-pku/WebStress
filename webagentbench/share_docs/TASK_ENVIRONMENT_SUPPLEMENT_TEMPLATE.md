# Environment Task Supplement Template

Use this template when adding a new WebAgentBench environment or when tightening
task standards for an existing environment.

This document is a supplement, not a replacement. It must refine
`share_docs/TASK_GENERATION_STANDARD.md` and remain consistent with it.

## How To Use This Template

- Copy this file to `share_docs/<ENVIRONMENT>_TASK_SUPPLEMENT.md`.
- Replace placeholder text with environment-specific requirements.
- Keep repo-wide quality rules in the core standard. Put only environment-specific
  details here.
- If this supplement conflicts with the core standard, fix the supplement.

## Purpose And Scope

Describe:

- what the environment simulates
- what classes of agent behavior it is intended to test
- which tasks are in scope
- which tasks are explicitly out of scope

Example:

- `This environment simulates a ticketing system with projects, issues, comments, labels, and workflow transitions.`
- `It is designed to test navigation, state tracking, policy grounding, and correct state mutation under realistic decoys.`

## Environment State Model

Document the durable state that the grader can reliably inspect.

Include:

- primary object types
- stable identifiers
- parent/child or thread/revision relationships
- mutable fields
- protected or system-owned fields
- any important derived views shown in the UI

Template:

- Primary objects:
  - `<object type A>` with stable ID `<field>`
  - `<object type B>` with stable ID `<field>`
- Key relationships:
  - `<relationship description>`
- Durable mutations:
  - `<state field or operation>`
- Non-durable or UI-only signals:
  - `<transient indicator>`

## Task Definition Shape

Describe the task-definition contract for this environment.

Include:

- required metadata fields
- environment-specific seed/materialization fields
- environment-specific evaluation fields
- any optional fields with strong conventions

Template:

- Required top-level fields:
  - `task_id`
  - `env_id: <environment>`
  - `title`
  - `instruction_template`
  - `<environment-specific field>`
- Required task-state construction fields:
  - `<field>`
- Required evaluation fields:
  - `<field>`

## Instruction Rules For This Environment

Specify what must be explicit in instructions for this environment.

Document:

- how objects are identified
- how revisions, recency, or tie-breaks are resolved
- how protected items are surfaced
- when exact wording is allowed
- what ambiguity traps are common in this environment

Template:

- Object selectors must name:
  - `<ID / title / sender / project / status / date / owner>`
- If multiple revisions may exist, instructions must specify:
  - `<latest by timestamp / latest by revision number / final approved state>`
- If an action is prohibited on protected objects, instructions must surface:
  - `<protected list / locked state / ownership boundary>`

Environment-specific bad patterns:

- `Open the correct item and fix it.`
- `Use the latest version.` without defining what "latest" means
- `Choose the relevant entry.` without a selector

Environment-specific good patterns:

- `<concrete example 1>`
- `<concrete example 2>`

## State Construction And Decoy Design

Describe how seeded or materialized state should be built.

Document:

- deterministic construction requirements
- realistic decoy patterns
- common shallow heuristics the benchmark should defeat
- required contrast cases for selectors and exclusions

Template:

- Determinism rules:
  - `<seed behavior>`
- Required decoy classes:
  - similar-name objects
  - stale revisions
  - superseded summaries
  - policy-exception items
  - near-miss filters or searches
- If the task depends on a comparison rule, seed:
  - at least one plausible wrong candidate that a shallow heuristic would choose

## Evaluation Standard For This Environment

Define what counts as strong evidence in this environment.

Document:

- preferred positive evidence
- required negative evidence
- what constitutes durable proof of completion
- what is too UI-path-specific to be a primary success criterion

Template:

- Preferred positive evidence:
  - stable object IDs
  - state fields reflecting the requested mutation
  - routing / assignee / destination fields
  - revision links or parent-child links
- Preferred negative evidence:
  - protected objects unchanged
  - wrong decoys untouched
  - superseded revisions not acted on
  - exact-cardinality constraints enforced
- Use transient DOM evidence only when:
  - `<condition>`

## Format-Tolerant Grading Rules

Document how to accept all materially correct outputs.

Include:

- what content must be present
- what formatting variation is acceptable
- when exact text is required
- how free-form outputs should be decomposed into smaller checks

Template:

- Accept semantic equivalence across:
  - ordering differences
  - bullet vs prose formatting
  - harmless punctuation differences
  - casing differences
- Require exact text only when:
  - the instruction provides exact text
  - the literal text is itself the skill being tested

## Required Negative-Check Categories

List the wrong actions that should usually be penalized in this environment.

Template:

- wrong-object mutation
- stale/superseded-object mutation
- protected-object mutation
- extra outputs beyond instructed cardinality
- routing to wrong destination
- partial completion masked as completion

## Variants

Explain how degradations should work in this environment.

Include:

- what primitives variants may stress
- what invariants must remain unchanged
- what fake responses or client degradation must preserve

Template:

- Variants may stress:
  - perception
  - memory
  - grounding
  - verification
- Variants must not change:
  - task objective
  - authoritative answer
  - grading contract

## Validation Suite

List the required validation commands for this environment.

Template:

```bash
python -m pytest -q tests/test_task_linter.py
python -m pytest -q tests/test_scoring_audit.py
python -m pytest -q tests/test_<environment>_seed_stability.py
python -m pytest -q tests/test_<environment>_integrity.py
python -m pytest -q tests/test_canary_trajectories.py
```

Add any environment-specific audits here:

- `tests/test_<environment>_<something>.py`: `<purpose>`

## Environment-Specific Anti-Patterns

List the mistakes that tend to produce benchmark noise in this environment.

Template:

- scoring on visible text alone when durable state exists
- proving that something happened without proving it happened to the correct object
- grading one UI path instead of the outcome
- using unrealistic decoys that no competent agent would confuse
- requiring exact prose where semantic checks would suffice

## Environment Readiness Checklist

Before adding or revising tasks in this environment, verify:

- the supplement still agrees with `TASK_GENERATION_STANDARD.md`
- the environment exposes durable state for authoritative grading
- selectors and tie-break rules are documented for common ambiguity classes
- decoys reflect realistic failure modes
- free-form outputs are graded semantically when appropriate
- variants preserve the same semantic task
- the validation suite covers the environment's unique failure modes
