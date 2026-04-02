# Gmail Task Generation Standard

This document describes the current authoring standard for Gmail tasks in WebAgentBench.

## Source Of Truth

- Task files live in `tasks/gmail/*.yaml`.
- The YAML schema is implemented in `tasks/_schema.py`.
- Seed materialization is handled by `backend/seeders/gmail.py` plus builders in `tasks/_seed_builders*.py`.
- Evaluation is handled by `tasks/_evaluator.py`.
- Variants live in `injector/variants/*.yaml`.

## Task Structure

Each Gmail task should define:

- `task_id`
- `env_id: gmail`
- `title`
- `instruction_template`
- `difficulty`
- `time_limit_seconds`
- `expected_steps`
- `primary_primitives`
- optional `secondary_primitives`
- `start_path`
- `seed`
- `eval`

## Seed Block

The `seed` block controls deterministic mailbox construction.

- `distractors`: generic distractor count added after task-specific seeding.
- `actors`: optional named actors used by the builder pipeline.
- `steps`: ordered builder calls. Each step uses a registered seed builder and can export named outputs.
- `targets`: task-level resolved values exposed to the instruction template and evaluator.

Authoring rules:

- If an actor name is surfaced in the instruction, define it explicitly instead of relying on random fake data.
- Prefer builder outputs and target indirection over hardcoding literal answers.
- Keep seeds deterministic for a fixed `(task_id, seed)` pair.

## Eval Block

The current Gmail benchmark is primarily outcome-validated.

- Prefer structural checks against server state: labels, filters, settings, starred state, reply/forward links, archive/delete state, and counts.
- Use `negative_checks` for meaningful wrong actions that should reduce score without necessarily hard-failing the whole task.
- Use client `benchmark_state` only when the interaction itself matters and server state alone is insufficient. Example: proving that the agent actually performed a search.
- Keep exact composed-text matching rare. If a task requires free-form writing, prefer checking that the right message exists in the right place over forcing an exact phrase unless the instruction gives the exact phrase.

## Variants

Stress/degradation variants live in `injector/variants/*.yaml`.

- Variants must declare the correct `base_task_id`.
- Keep fake network responses schema-compatible with the real API response shape.
- Use variants to stress a target primitive, not to make the task semantically different.

## Validation Checklist

Run these before treating a new task or variant as benchmark-ready:

```bash
python -m pytest -q tests/test_task_linter.py
python -m pytest -q tests/test_scoring_audit.py
python -m pytest -q tests/test_gmail_seed_stability.py
python -m pytest -q tests/test_benchmark_integrity.py
python -m pytest -q tests/test_e2e_integration.py tests/test_canary_trajectories.py
```

Relevant audits:

- `tests/test_task_linter.py`: schema hygiene, answer leakage, target integrity, variant API-shape checks
- `tests/test_scoring_audit.py`: brittle composed-text scoring guardrails
- `tests/test_gmail_seed_stability.py`: deterministic seed behavior
- `tests/test_axtree_audit.py`: AXTree visibility of task-critical state
- `tests/test_canary_trajectories.py`: solvability of standard and degraded tasks

## Practical Guidance

- Make the authoritative evidence live in the simulated Gmail state whenever possible.
- Use instructions that force the agent to resolve ambiguity, recency, thread structure, or policy constraints.
- Add decoys that are behaviorally plausible, not random noise.
- Keep task success tied to the intended outcome, not to one brittle UI path, unless the task explicitly tests that path.
