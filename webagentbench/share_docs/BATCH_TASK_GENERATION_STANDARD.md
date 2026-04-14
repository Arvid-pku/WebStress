# Batch Task Generation Standard

This document extends [TASK_GENERATION_STANDARD.md](TASK_GENERATION_STANDARD.md)
for authors generating or reviewing batches of tasks across any environment.
It is the repo-wide standard for producing benchmark-ready task sets that are:

- high quality
- high diversity
- objectively and correctly graded
- robust across seeds
- valid under degradation variants

This document is environment-agnostic on purpose. Environment-specific
supplements may tighten it, but they must not weaken it.

## Why Batch Generation Needs A Separate Standard

A single good task does not imply a good batch. Batch generation fails in ways
that are invisible when tasks are reviewed one by one:

- Template clones. Superficially different tasks collapse to the same selector,
  action pattern, and evaluator shape.
- Instruction-seed mismatch. The instruction tells the agent to read or find
  content that the seed never generates.
- Hidden-state grading. The evaluator expects facts that exist in internal
  state but are not discoverable in the UI.
- Vacuous correctness. Empty target lists or empty branch targets make `all()`
  checks pass while the intended requirement never exists.
- Fake diversity. Entity names change, but the reasoning pattern and action
  topology do not.
- Degradation drift. A degraded variant changes the semantic task, makes the
  task impossible, or stresses multiple primitives at once.
- Seed fragility. The task works at one canonical seed but breaks or becomes
  ambiguous across realistic seeds.

The batch is benchmark-ready only if those failure modes are controlled at the
batch level, not only the task level.

## Scope

This standard governs:

- YAML task definitions under `webagentbench/tasks/`
- shared task schema in `webagentbench/tasks/_schema.py`
- seed builders and materialization
- evaluators and negative checks
- degradation variants under `webagentbench/injector/variants/*.yaml`
- environment supplements and task-family design docs

In the current checkout, the concrete batch-generation path is:

1. define task YAML matching `TaskDefinition`
2. seed state through builder steps in `seed`
3. materialize with `webagentbench.backend.state.materialize_task_state()`
4. render instruction with `webagentbench.task_materialization.materialize_task()`
5. grade with `eval.checks` plus `eval.negative_checks`
6. optionally apply degradation through `webagentbench.injector`

## Normative Language

The words MUST, MUST NOT, SHOULD, SHOULD NOT, and MAY are normative.

## Core Principle

Every benchmark task is an executable contract between five artifacts:

1. instruction
2. seed/state
3. UI/API surface
4. evaluator
5. degradation variant, if any

The task is valid only when those artifacts agree on the same objective,
evidence model, and completion set.

## Definitions

### Task

A single task YAML plus its seeded state, rendered instruction, evaluator, and
optional degraded variants.

### Task Family

A group of tasks produced from a common conceptual template or workflow shape.
Different family members may vary in entities, selectors, prerequisites,
actions, and decoy structure.

### Batch

A set of tasks intended to represent an environment, a release slice, or a
research study split.

### Selector

The rule that identifies the relevant entity or entities. Examples:

- most recent completed appointment
- highest-dollar denied claim
- earliest overdue assignment with feedback
- newest unread message from the ordering provider

### Discoverability Contract

If the instruction requires the agent to read, compare, verify, or cite some
content, that content MUST exist and MUST be visible or retrievable through the
actual task UI/API.

### Degradation Variant

A task variant that preserves the semantic objective and gold end state while
making one primitive materially more necessary.

### Correct Degradation

A degradation that is:

- semantics-preserving
- solvable with the target primitive
- not a wall
- deterministic enough to evaluate reliably
- compatible with the real frontend/backend state shape

## Batch-Level Quality Objectives

Every benchmark batch MUST satisfy all six objectives below.

### 1. Solvability

For every supported seed, there exists at least one valid trajectory that can
complete the task from the exposed UI/API.

### 2. Objective Grading

The evaluator can distinguish correct from materially incorrect outcomes using
observable state, not author intent or hidden metadata.

### 3. Discoverability

Any fact the instruction asks the agent to read or discover is actually present
in seeded content and surfaced in the product.

### 4. Diversity

The batch spans genuinely different reasoning and interaction patterns, not
just renamed copies of the same task.

### 5. Seed Stability

The task remains well-formed and unambiguous across a wide seed range, not only
at one hand-picked seed.

### 6. Degradation Correctness

Any degraded variant preserves the task semantics while selectively stressing
its target primitive.

## Required Batch Artifacts

No serious batch effort is complete without explicit authoring artifacts. At
minimum, a benchmark-quality batch SHOULD maintain all of the following:

- a task-family spec describing the major families and why they are distinct
- a diversity matrix covering selector, topology, action, primitive, and decoy
  axes
- a seed/evaluator audit log recording discovered instruction-seed or
  hidden-state mismatches
- a degradation packet for every nontrivial variant
- a validation log summarizing seed sweeps, canaries, and rejected failures

These artifacts do not need to live in one file, but they MUST exist in some
reviewable form before the batch is called benchmark-ready.

### Degradation Packet Contents

When a task or family has degraded variants, the degradation packet SHOULD
contain:

- the target primitive
- the invariance statement
- the chosen injector layer and rationale
- the reused existing actions, or the extension rationale for a new action
- the base-vs-degraded canary summary
- the observed stress signal
  for example retries, extra steps, verification actions, or time increase

## Standard Authoring Workflow

Every new batch SHOULD be authored and reviewed in this order.

### 1. Specify The Family Before Writing YAML

Define the family on paper first:

- target user goal
- target entities
- selector logic
- prerequisite/dependency structure
- intended positive completion state
- major wrong-action classes
- intended primitive coverage
- intended degradation targets, if any

If those cannot be stated clearly before authoring, the task family is not
ready.

### 2. Define The State Contract

Before writing the instruction, specify exactly which seeded artifacts make the
task possible:

- which entities must exist
- which fields must be non-empty
- which facts must appear in user-visible content
- which relationships must hold across entities
- which branch conditions may or may not occur

The seed contract MUST be explicit enough that another author could implement
it without guessing.

### 3. Define The UI Contract

For every required read or write action, list the concrete surface where the
agent can perform it:

- page
- tab
- modal
- table cell
- message body
- attachment view
- API-returned data rendered in UI

A task MUST NOT depend on data that exists only in backend state unless that
backend data is intentionally exposed to the agent.

### 4. Define The Evaluator Contract

List:

- exact positive checks
- exact negative checks
- conditional branches and their guards
- the minimal state evidence required for a pass

If the grader cannot be described before implementation, the task is not ready.

### 5. Define The Degradation Contract

For each degraded variant, declare:

- target primitive
- invariant task objective
- invariant resolved targets
- invariant final success state
- failure mode introduced by the degradation
- why the target primitive resolves it

### 6. Only Then Write YAML And Builders

YAML should be the encoding of a validated task design, not the place where the
design is discovered ad hoc.

### 7. Produce The Review Artifacts

Before merge, the author SHOULD be able to hand a reviewer:

- the family spec
- the diversity matrix
- the seed/evaluator audit
- the degraded-variant packet, if degradations exist
- the validation summary

## Instruction Standard For Batch Generation

The instruction is the public contract. It MUST be sufficient on its own when
combined with the exposed product state.

### Objective Finish Line

The instruction MUST define:

- what must be done
- what counts as done
- what must not be done, if relevant
- any selection rule needed to identify the target entity

Bad:

> Review the relevant claim and resolve the issue.

Good:

> Find the highest-dollar denied claim, review the EOB denial reason, and
> submit an appeal only for that claim.

### No Hidden Selector Logic

If multiple candidate entities may exist, the selector MUST be explicit. The
agent must never be expected to infer the author's intended item from hidden
target IDs or evaluator-only logic.

The instruction MUST define tie-breakers when ties are plausible. If ties are
not allowed, the seed builder MUST prevent them.

### Discoverability Contract

If the agent is told to read, compare, cite, verify, confirm, review, inspect,
or use specific content, that content MUST satisfy all three conditions:

1. seeded
2. non-placeholder
3. exposed in the UI/API the agent actually sees

Typical violations:

- "read the discharge summary" but message bodies are generic placeholder text
- "check the rubric" but rubric arrays are empty
- "review the feedback" but feedback is null
- "use the EOB denial reason" but denial reason is not rendered anywhere
- "contact the ordering provider" but provider identity is not exposed

### Branches Must Be Observable

Conditional branches are allowed only when the branch condition is observable by
the agent.

Bad:

- evaluator checks for a follow-up action if an internal flag is true
- the instruction does not tell the agent how to determine that flag

Good:

- evaluator checks for a follow-up action if the UI visibly shows an approved
  referral, abnormal lab, unpaid invoice, or missing prerequisite

### Avoid Free-Form Language As Primary Evidence

If the benchmark goal is not language generation itself, free-form message
composition SHOULD NOT be the primary graded outcome.

Prefer objective actions such as:

- schedule the correct appointment
- transfer the correct prescription
- apply the correct label
- submit the correct appeal
- choose the correct plan

If text is unavoidable, evaluation MUST focus on a small number of objective,
necessary facts rather than style, phrasing, or broad semantic similarity.

### One Task, One Public Story

The instruction MUST read like a single coherent user objective. It MUST NOT
smuggle in unrelated side quests only to increase difficulty.

## Seed And State Standard

The seed is valid only if it constructs a world that actually supports the
instruction.

### Determinism

The seed builder MUST be deterministic for `(task_id, seed)`.

In this repo, authors SHOULD verify determinism through:

- `webagentbench.backend.state.materialize_task_state()`
- `webagentbench.task_materialization.materialize_task()`

### Target Existence

Every referenced target class MUST exist whenever the instruction implies it
must exist.

Examples:

- if the task says "message from your cardiologist", a cardiologist message
  must exist
- if the task says "upcoming cardiology appointment", such an appointment must
  exist
- if the task says "denied claim", at least one denied claim must exist

### No Vacuous Target Sets

Any resolved target list used in evaluation MUST be non-empty when the
instruction requires that branch or action.

Common failure mode:

- comma-separated IDs resolve to `""`
- evaluator splits them and `all()` passes vacuously

Batch review MUST explicitly test for this class.

### Content Must Be Meaningful

Placeholder content is not benchmark content.

The following are unacceptable when the instruction depends on them:

- generic lorem ipsum
- `ctx.fake.paragraph()` bodies standing in for clinical, academic, or billing
  evidence
- empty arrays used where the instruction implies structured feedback
- nulls in fields the task says the agent should read

If a field matters to task reasoning, it MUST contain semantically relevant
content.

### Relationships Must Be Real, Not Implied

Cross-entity tasks MUST seed the relevant relationships explicitly. Do not rely
on coincidence or parallel generation.

Examples:

- claim linked to appointment
- appeal linked to denial reason
- medication linked to formulary note
- referral linked to specialist appointment
- assignment linked to peer feedback being reviewed

### UI Surface Availability

A task is invalid if the seed stores required evidence in state but the product
never renders it. This is a first-class batch review check.

### Seed-Invariant Design

Whenever possible, tasks SHOULD be seed-invariant by construction:

- do not rely on rare random cases
- do not rely on random provider types, status mixes, or branch outcomes
- directly constrain the seed builder to produce the required structure

Fixing a task only at seed 42 is not sufficient.

## Diversity Standard

High diversity means different tasks require different reasoning programs, not
just different nouns.

### Mandatory Diversity Axes

Each batch MUST be reviewed across at least these axes:

1. target entity type
2. primary action type
3. selector type
4. dependency topology
5. information source shape
6. decoy family
7. branching structure
8. primitive emphasis
9. degradation target primitive, when degradations are present

### Recommended Diversity Matrix

For each task, maintain a row with at least:

- `task_id`
- family
- target entity
- primary action
- selector operator
- prerequisite topology
- information sources read
- positive completion state
- major wrong-action classes
- primary primitives
- degradation target, if any

This matrix SHOULD exist before the batch is declared complete.

### Anti-Clone Rule

Two tasks are clones if they share the same:

- action topology
- selector logic
- dependency structure
- evaluator shape

while differing only in labels, entity names, or cosmetic wording.

Clones MUST be merged, rewritten, or removed.

### Quantitative Batch Targets

For any benchmark batch of at least 30 tasks, authors SHOULD meet all of the
following:

- no single family contributes more than 15 percent of the batch
- no single selector pattern contributes more than 25 percent of the batch
- at least 6 distinct selector patterns
- at least 6 distinct action outcomes
- at least 4 distinct dependency topologies
- at least 4 distinct decoy families
- at least 4 distinct branching shapes, if branching is used

If an environment is small and cannot meet those numbers, the environment
supplement MUST document the reduced target and justify it.

### Diversity Must Include Failure Opportunities

A diverse batch must not only vary target objects. It must vary how an agent can
go wrong:

- wrong entity selected
- prerequisite missed
- stale information trusted
- write action not verified
- hidden decoy taken
- state carried incorrectly across pages
- branch condition misread

## Evaluation Standard

### State-Grounded Primary Checks

Primary pass criteria MUST be grounded in observable state changes or preserved
state invariants. This remains the repo-wide rule.

### Negative Checks Are Required

Each task MUST include negative checks that reject plausible wrong completions,
especially the dominant decoy paths.

### Conditional-Action Pattern

If a task contains a conditional branch:

1. the branch guard must be observable
2. the seed must make the branch meaningful
3. the evaluator must check the branch only when the guard is true
4. the evaluator must reject the branch action when the guard is false, if that
   action would be incorrect

### No Hidden Evaluation Inputs

The evaluator MUST NOT require facts that were never exposed to the agent.

This includes:

- internal IDs not visible in UI when the UI offers no mapping
- state-only metadata
- invisible relationship fields
- backend-only messages or attachments

### Exactness Only When It Is The Skill Under Test

Exact textual equality SHOULD be used only when exact wording is the intended
benchmark target. Otherwise prefer structured state checks or factual substring
checks tied to objective requirements.

### The Evaluator Must Accept All Materially Correct Trajectories

If two different action sequences yield the same correct end state, both should
pass unless the path itself is part of the benchmark objective.

## Degradation Standard

This section is the bar for correct degraded variants.

### Primitive Taxonomy Source

All degraded variants MUST use the canonical seven-primitive taxonomy defined in
`webagentbench/primitives.py`:

- grounding
- planning
- state_tracking
- backtracking
- patience
- exploration
- verification

### Semantic Invariance

A degraded variant MUST preserve:

- the user goal
- the resolved target entities
- the required final success state

It MAY change how hard it is to perceive, remember, verify, recover, or wait,
but it MUST NOT change what counts as success.

### Single-Primitive Intent

Each degraded variant MUST name one `target_primitive` and SHOULD primarily
stress that primitive, not several at once.

In this repo, the degradation schema is defined in
`webagentbench/injector/config.py`.

### Filter, Not Wall

A correct degradation makes the target primitive necessary, not the task
impossible.

The author must be able to explain:

- what information/action is obstructed
- what signal still remains
- why an agent with the target primitive can still recover

Whenever possible, at least one independent path to the truth SHOULD remain.
For example, if one cue is degraded, another cue such as structure, timestamp,
entity relationship, or confirmation state should still exist.

### Use Existing Infra First

Degradation authors MUST treat the current injector stack as the default design
surface, not as an implementation detail to bypass.

In this checkout, the reusable degradation infrastructure includes:

- `webagentbench/injector/config.py`
  including `DegradationConfig` and `default_for_primitive()`
- `webagentbench/injector/apply.py`
  for seed/server application
- `webagentbench/injector/middleware.py`
  as the canonical runtime path for network degradation
- `webagentbench/injector/seed.py`
  for content- and evidence-shaping mutations
- `webagentbench/injector/server.py`
  for state-structure perturbations
- `webagentbench/scripts/generate_missing_hard_variants.py`
  as a bootstrap generator for missing hard variants

Authors SHOULD compose existing actions and behaviors before inventing new
injector actions.

### Preserve API And UI Shape

Fake or degraded responses MUST preserve the schema expected by the frontend.
For example:

- silent failures should still return structurally valid response bodies
- stale data should still match the product's expected payload format
- client mutations should not destroy unrelated functionality

### Prefer Deterministic Critical-Path Injections

For benchmark reliability, critical degradations SHOULD be deterministic or
count-bounded rather than low-probability.

Good:

- first write silently fails
- first two matching requests return 503
- delay increases after N calls

Risky:

- 10 percent intermittent failure in a short task

### Behavior Mode Selection

When an injector action supports `behavior.mode`, authors SHOULD choose the
mode intentionally:

- `once`
  Default for critical-path benchmark behavior. Best when the task should
  reliably force one recovery or verification episode.
- `intermittent`
  Use only when the task is long enough that probabilistic behavior still
  fires often enough to measure the target primitive.
- `progressive`
  Best for patience or planning variants where the challenge should ramp with
  repeated calls rather than trigger as a single event.

If the task is short or the recovery episode is benchmark-critical, `once`
SHOULD be preferred over `intermittent`.

### Prefer Middleware-Backed Server Or Network Over Fragile Client Tricks

In this checkout, network degradation is applied server-side via
`webagentbench/injector/middleware.py`, and seed/server degradation is applied
through `webagentbench/injector/apply.py`.

The legacy Playwright helper modules in `webagentbench/injector/network.py` and
`webagentbench/injector/client.py` document the intended semantics, but they
are not the primary benchmark path. Client mutations should be treated as
supplementary unless the environment supplement has validated them thoroughly.

Where possible:

- prefer seed/server/network degradations for benchmark-critical behavior
- use client-layer degradation as supplementary, not the sole source of truth,
  unless the environment supplement has validated it thoroughly

### Distributed, Not One-Shot

Degradations SHOULD persist across the relevant interaction window. A single
blink-and-miss mutation often measures luck more than capability.

### Degradation Design Pipeline

Every hand-written degraded variant SHOULD be authored in the following order.

#### 1. Start From A Strong Base Task

Do not degrade a weak or ambiguous base task. First confirm:

- the base task is objectively defined
- the base evaluator is correct
- the base task is solvable across seeds
- the base task has a known correct trajectory

#### 2. Identify The Exact Failure Point

Localize the moment in the base trajectory where the target primitive matters.

Examples:

- a write appears to succeed but must be verified
- the right entity is visually confusable with decoys
- the correct answer requires revisiting a previous assumption
- the agent must wait through transient failure instead of acting on stale state

The primitive should be attached to one concrete failure mechanism, not to a
vague notion of "making the task harder."

#### 3. Choose The Lowest-Risk Layer

Choose the injector layer that expresses the challenge while preserving the
task semantics.

As a default rule:

- use `seed` when the challenge is about what evidence exists or how it is
  distributed
- use `server` when the challenge is about state ordering, presence, or feature
  visibility without changing semantic truth
- use `network` when the challenge is about retry, waiting, or verifying write
  outcomes
- use `client` only when the intended challenge truly depends on presentation
  and the behavior has been validated for both humans and agents

#### 4. Reuse Existing Actions Before Extending Infra

First try to express the variant with existing action families.

Current high-value reusable families include:

- `seed`: `add_confusing_decoys`, `split_information`,
  `add_contradictory_update`, `plant_wrong_answer`,
  `increase_distractors`, `alias_entities`,
  `hide_in_non_obvious_location`
- `server`: `scramble_timestamps`, `shuffle_contacts`,
  `hide_prerequisite`, `inject_distractor_emails`, `corrupt_state`
- `network`: `delay`, `silent_fail`, `stale_data`,
  `error_then_success`

Only add a new injector action when both are true:

- the intended failure mode cannot be expressed compositionally with existing
  actions
- the new action is generic enough to matter across more than one task or
  environment

#### 5. Write The Invariance Statement

Before writing the YAML, record a short invariance note:

- same instruction semantics
- same resolved targets
- same final pass state
- same dominant wrong actions
- only the route to success changes

If that note cannot be written cleanly, the variant is likely drifting.

#### 6. Write The Variant YAML

The variant YAML should be a thin, auditable encoding of the design, not the
place where the failure mode is improvised.

#### 7. Compare Base And Degraded Gold Trajectories

The degraded gold trajectory may include more retries, verification steps,
extra search, or more careful entity selection. It MUST NOT require a different
semantic objective or a different final answer.

#### 8. Promote Or Reject The Variant

Reject the variant if it:

- changes the answer
- removes the only real signal
- breaks the frontend
- fires unreliably
- stresses several primitives at once
- yields a challenge that looks hard but is actually luck-dependent

### Layer Selection Matrix

Use the following matrix as the default starting point.

| Primitive | First-choice layer | Typical existing actions | Review risk |
| --- | --- | --- | --- |
| `grounding` | `seed`, `server` | `add_confusing_decoys`, `alias_entities`, `inject_distractor_emails`, `shuffle_contacts` | Decoys may accidentally change selector semantics |
| `planning` | `seed`, `server` | `split_information`, `add_contradictory_update`, `hide_prerequisite`, `scramble_timestamps` | Hidden prerequisites can become invisible rather than merely harder |
| `state_tracking` | `seed`, `server` | `split_information`, `increase_distractors`, `scramble_timestamps`, `shuffle_contacts` | Timeline perturbations can destroy stable ordering if overused |
| `backtracking` | `network`, `seed`, `server` | `error_then_success`, `plant_wrong_answer`, `hide_prerequisite` | Wrong-answer plants can become better answers if semantics drift |
| `patience` | `network` | `delay`, `error_then_success` | Low-probability failures often underfire and stop measuring patience |
| `exploration` | `seed`, `client` | `hide_in_non_obvious_location`, `add_confusing_decoys`, `inject_distractor_emails` | Client-only hiding often becomes flaky or invisible to the agent |
| `verification` | `network`, `seed` | `silent_fail`, `stale_data`, `add_contradictory_update`, `split_information` | Fake success must preserve payload shape and recovery path |

This matrix is a starting point, not a substitute for task-specific reasoning.

### Degradation Diversity Standard

Degradation diversity is a separate quality axis from task diversity.

A batch can have diverse base tasks but still have poor degraded coverage if
most variants reduce to the same perturbation pattern, such as:

- every grounding variant being a "near-duplicate decoy"
- every backtracking variant being "first request returns 503"
- every verification variant being "silent fail on first write"

That kind of primitive-action monoculture weakens diagnosis. It measures whether
an agent has memorized one house pattern rather than whether it robustly has the
primitive.

### Mandatory Degradation Diversity Axes

Any mature degraded suite SHOULD be reviewed across at least these axes:

1. target primitive
2. injector layer
3. action family
4. behavior mode
5. temporal profile
6. residual signal shape
7. recovery pattern demanded from the agent
8. perturbation scope
9. task-coupling level

These axes mean:

- `behavior mode`
  whether the degradation is `once`, `intermittent`, `progressive`, or another
  explicit temporal contract
- `temporal profile`
  whether the challenge is immediate, delayed, escalating, repeated, or only
  revealed after a branch
- `residual signal shape`
  what truthful evidence remains
  for example structural cues, timestamps, relationship evidence, later
  confirmation, or alternative surfaces
- `recovery pattern`
  what the agent must do differently
  for example retry, verify, re-read, revisit a prior choice, inspect another
  surface, or search more broadly
- `perturbation scope`
  whether the perturbation affects one entity, one action, one page, one route,
  or a whole session
- `task-coupling level`
  whether the variant is a generic fallback, a composed generic variant, or a
  task-coupled variant with task-specific evidence shaping

### Degradation Diversity Matrix

For each degraded variant, the review matrix SHOULD include at least:

- `variant_id`
- `base_task_id`
- target primitive
- injector layer
- action family
- behavior mode
- temporal profile
- residual signal shape
- required recovery pattern
- perturbation scope
- task-coupling level

This makes it possible to see whether a suite only looks diverse because the
URL patterns differ.

### Degradation Anti-Clone Rule

Two degraded variants are clones if they share the same:

- target primitive
- injector layer
- action family
- behavior mode
- residual signal shape
- required recovery pattern

while differing only in route names, entity names, or task labels.

Clone variants SHOULD be collapsed unless the underlying base tasks are so
different that the same degradation genuinely tests a different recovery
program.

### Primitive-Action Monoculture Is A Review Failure

For a mature environment, a primitive SHOULD NOT be represented almost entirely
by one action family.

Examples of monoculture smell:

- grounding represented almost only by one `add_confusing_decoys` pattern
- backtracking represented almost only by one `error_then_success` pattern
- verification represented almost only by one `silent_fail` pattern

If that pattern appears, authors SHOULD add variants that reach the same
primitive through different mechanisms before adding more copies of the dominant
pattern.

### Quantitative Targets For Degradation Diversity

For any environment or batch with at least 12 degraded variants for a given
primitive, authors SHOULD target all of the following:

- at least 3 distinct action families for that primitive
- at least 2 distinct recovery patterns for that primitive
- at least 2 distinct residual signal shapes for that primitive
- no single action family contributes more than 65 percent of variants for that
  primitive
- at least 1 task-coupled variant at quality ladder level 3 or higher for that
  primitive

For any environment or batch with at least 30 degraded variants total, authors
SHOULD also target:

- at least 3 injector layers represented overall, when the environment can
  support them safely
- at least 2 behavior modes represented overall
- no single layer contributes more than 80 percent of all degraded variants

If an environment cannot meet these targets because of product structure or
reliability constraints, the environment supplement SHOULD say so explicitly and
document the fallback plan.

### Recommended Primitive Mechanism Mix

The following are not hard caps, but they are the intended direction for a
research-grade suite:

- `grounding`
  mix lexical/entity twins, structural ambiguity, alias confusion, and
  presentation ambiguity
- `planning`
  mix hidden prerequisites, constraint revelation, stale ordering, and
  multi-step dependency disruption
- `state_tracking`
  mix information distribution, contradictory updates, timestamp/order
  perturbation, and state-noise accumulation
- `backtracking`
  mix transient write failures, plausible wrong initial answers, late
  prerequisite revelation, and reversible branch dead ends
- `patience`
  mix pure latency, transient error-then-success, progressive slowdown, and
  delayed consistency
- `exploration`
  mix hidden affordances, non-obvious locations, deep decoy surfaces, and
  broader search pressure
- `verification`
  mix silent failure, stale reads, partial confirmation, inconsistent success
  signals, and post-action contradiction

### Variant Quality Ladder

Not all variants are equal. The expected maturity order is:

1. `default_for_primitive()` fallback
   Good for coverage bootstrapping. Not sufficient evidence of a high-quality
   research-grade variant on its own.
2. Composed generic variant using existing actions
   Good when the task is structurally simple and the failure mode is generic.
3. Task-coupled variant reusing existing actions with task-aware parameters
   Preferred for serious benchmark tasks.
4. New infra action plus task-coupled variant
   Justified only when a repeated, cross-task failure mode cannot otherwise be
   expressed.

Frontier or flagship tasks SHOULD target level 3 or level 4, not only level 1.

### Reuse Before Extension Rule

Before extending the injector stack, the author SHOULD explicitly answer:

- Why does `default_for_primitive()` not capture the failure mode?
- Why do existing `seed`, `server`, or `network` actions not suffice?
- Why is the new action generic rather than one-off?
- How will the new action preserve determinism and schema shape?

If those answers are weak, the new action should not be added.

### Degradation Failure Taxonomy

Reviewers SHOULD classify failures using this taxonomy:

- semantic drift
  The degraded task no longer asks for the same thing.
- signal destruction
  The only path to the truth is removed rather than stressed.
- schema mismatch
  Fake or stale responses break the frontend contract.
- non-firing degradation
  The variant rarely triggers, so the target primitive is not actually tested.
- over-firing degradation
  The variant dominates the task and turns it into generic chaos.
- primitive contamination
  The variant stresses several primitives at once, obscuring diagnosis.
- client invisibility
  A DOM mutation is not reliably visible to agent perception.
- seed fragility
  The variant works for one seed but collapses across others.
- canary divergence
  The degraded success path needs a different answer rather than extra care.

### Variant YAML Skeleton

Use a minimal, auditable YAML shape like this:

```yaml
variant_id: my_task__verification_v1
base_task_id: my_task
target_primitive: verification
description: First save silently fails; agent must verify outcome and retry.
injections:
  - layer: network
    params:
      action: silent_fail
      url_pattern: "**/api/env/myenv/save"
      methods: ["POST"]
      response_body:
        success: true
      fail_count: 1
      behavior:
        mode: once
```

For task-coupled variants, add a short review note alongside the YAML or in the
PR description stating:

- why this primitive is the right diagnosis
- why the chosen layer is correct
- which signal remains for successful recovery
- how base and degraded success states are identical

### Degradation-Specific Acceptance Questions

Every degraded variant MUST answer yes to all of the following:

- Does the same task instruction still make sense?
- Are the same resolved targets still correct?
- Is the degraded task still solvable from the real UI?
- Is the failure mode attributable mainly to the declared primitive?
- Does the frontend continue to function?
- Does the evaluator still grade the same end state?

## Batch Validation Protocol

No batch is complete without validation evidence.

### A. Static Review

For every task:

- inspect the instruction template
- inspect the seed steps and outputs
- inspect the resolved targets
- inspect evaluator checks and negative checks
- verify discoverability of every required read fact
- verify existence of every referenced entity class
- verify every branch target is non-vacuous

### B. Materialization Sweep

Materialize tasks across a broad seed range, not just the canonical seed.

At minimum, review should include:

- rendered instruction
- resolved targets
- state shape summary
- task-specific non-empty target assertions

Authors SHOULD use:

- `webagentbench.backend.state.materialize_task_state()`
- `webagentbench.task_materialization.materialize_task()`

### C. Seed Sweep

For each task family, run a sweep over many seeds and assert:

- no target lists collapse unexpectedly
- no required entity class disappears
- no selector ambiguity appears
- no branch becomes impossible without instruction changes
- no required content falls back to placeholders

### D. Simulated Correctness Check

For every task family, maintain at least one canonical correct trajectory or
scripted canary that proves the task is actually completable.

For degraded variants, maintain at least one recovery-aware canary or gold
trajectory that succeeds under the variant.

For any degraded/base pair, reviewers SHOULD confirm that:

- both pass to the same final state
- the degraded run differs only in recovery behavior, not in answer semantics
- the degraded run exercises the declared primitive at the intended step

### E. Wrong-Action Check

At least one dominant wrong path per family SHOULD be tested to confirm the
evaluator rejects it.

### F. Diversity Review

Before merge, inspect the diversity matrix and explicitly review for clones.

### G. Degraded Pair Invariance Review

For each degraded variant, explicitly compare the base and degraded task on the
same seed and verify:

- same rendered instruction semantics
- same resolved targets
- same final positive state
- same final negative state definitions
- different effort profile caused by the declared primitive stress

### H. Stress-Signal Review

Degradation review SHOULD not rely on score delta alone.

Authors SHOULD also inspect whether the variant changes:

- steps to completion
- retries
- verification actions
- elapsed time
- recovery actions

This matters because a correct patience or planning degradation may preserve the
pass rate while still materially increasing effort.

### I. Infra Reuse Review

If a variant adds new injector behavior, the review MUST include:

- why existing action families were insufficient
- why the new action is general-purpose
- how it preserves schema shape
- how it is deterministic enough for benchmark use

### J. Degradation Diversity Review

For any batch with degraded variants, reviewers SHOULD explicitly inspect:

- whether any primitive is dominated by one action family
- whether the suite includes more than one recovery pattern per primitive
- whether the residual truthful signal varies across variants
- whether task-coupled variants exist, rather than only generic templates
- whether clone variants differ only cosmetically

The review should reject suites that are formally large but mechanistically
narrow.

## Release Criteria

A batch is benchmark-ready only if all of the following are true:

- every task satisfies [TASK_GENERATION_STANDARD.md](TASK_GENERATION_STANDARD.md)
- every task satisfies this batch standard
- no instruction-seed mismatch remains
- no hidden-state grading remains
- no vacuous target-list branch remains
- diversity review finds no unresolved clones
- seed sweep shows stable, discoverable targets
- degraded variants are semantics-preserving and solvable
- degraded variants have passed invariance review
- degraded variants have passed degradation diversity review
- any new injector behavior has passed infra reuse review

## Required Evidence For Batch Review

Every serious batch PR or release review SHOULD provide:

- a family/diversity matrix
- a list of seed-sweep ranges used
- a summary of discovered failures and fixes
- examples of positive and negative evaluation evidence
- for degraded variants, a short rationale per variant explaining why it is a
  correct filter and not a wall
- for degraded variants, a base-vs-degraded invariance note
- for degraded variants, a degradation diversity matrix or equivalent summary
- when new injector behavior is introduced, a short extension rationale and
  validation note

## Author Checklist

- Did I write the selector explicitly?
- Did I guarantee every required entity exists?
- Did I seed every fact the instruction tells the agent to read?
- Is that fact visible in the UI/API?
- Are all resolved target lists non-empty when required?
- Is the evaluator based on visible state?
- Does the evaluator reject the dominant wrong path?
- Is this task materially different from nearby tasks?
- Does the task still work across many seeds?
- If degraded, does the variant preserve the same semantic objective?

## Reviewer Checklist

- Can I identify the correct target from the instruction alone?
- Can the agent observe every fact the evaluator expects it to use?
- Are any fields null, generic, or placeholder where task reasoning depends on
  them?
- Are there ties or empty branches the author did not notice?
- Is the task family genuinely new, or just a renamed clone?
- Does the degraded variant stress one primitive cleanly?
- Is the degraded task still solvable and objectively graded?

## Relationship To Environment Supplements

Environment supplements should add:

- environment-specific entity models
- environment-specific decoy patterns
- environment-specific selector families
- environment-specific validation helpers
- environment-specific degradation guidance

They MUST NOT weaken:

- the discoverability contract
- the no-vacuous-target rule
- the state-grounded grading rule
- the filter-not-wall degradation rule
- the diversity and anti-clone review requirement

## Final Standard

High-quality benchmark batches are not produced by generating many tasks quickly.
They are produced by maintaining a strict contract among instruction, seed, UI,
evaluation, and degradation, then verifying that contract across seeds and
across the whole batch.

If a batch is diverse but not objective, it is not benchmark-ready.
If it is objective but full of clones, it is not benchmark-ready.
If it is diverse and objective but degrades into impossibility, it is not
benchmark-ready.

The correct standard is all three at once:

- high quality
- high diversity
- correct degradation
