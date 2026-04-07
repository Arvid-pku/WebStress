# WebAgentBench

WebAgentBench is a self-contained benchmark for evaluating web agents through interaction inside simulated application environments. The active benchmark line in this repository is the Gmail environment: a stateful single-page app with seeded mailbox state, task-specific instructions, server-side mutations, and evaluator-side success checks.

This checkout should be read as a Gmail benchmark framework rather than as the retired page-based benchmark described in older historical notes. Task definitions live in `tasks/gmail/`; the current manifest exposes one environment, `gmail`; and the React frontend for that environment lives under `environments/gmail/`.

## Current Scope

- `manifest.json` defines benchmark-level metadata and the environments exposed by the current checkout.
- `tasks/gmail/*.yaml` defines Gmail tasks, instructions, seeded targets, and evaluation checks.
- `injector/variants/*.yaml` defines stress/degradation variants used to probe specific primitives.
- `backend/`, `browsergym_task.py`, and `agent_eval.py` provide runtime, BrowserGym integration, and evaluation flow.

## Evaluation Model

Current Gmail tasks are primarily outcome-validated:

- Most success criteria are evaluated against auditable server-side Gmail state via YAML `eval.checks` and `eval.negative_checks`.
- Selected tasks can additionally require client-side `benchmark_state` evidence when the interaction itself matters. For example, `gmail_search_and_star` requires a recorded search event.
- The current Gmail benchmark is therefore not a general DOM-evidence benchmark. It is a state-grounded interaction benchmark with optional client-event checks where needed.

## Task Authoring

The normative task-quality bar for this repo is [share_docs/TASK_GENERATION_STANDARD.md](share_docs/TASK_GENERATION_STANDARD.md).

For new environments, start from [share_docs/TASK_ENVIRONMENT_SUPPLEMENT_TEMPLATE.md](share_docs/TASK_ENVIRONMENT_SUPPLEMENT_TEMPLATE.md) and keep the resulting supplement subordinate to the repo-wide standard.

Use that document as the authoritative standard for:

- objective, non-equivocal task instructions
- robust, outcome-grounded grading
- format-tolerant evaluation for tasks with multiple valid correct outputs
- decoy and negative-check coverage

Core implementation and validation files:

- `tasks/_schema.py`
- `backend/seeders/gmail.py`
- `tasks/_evaluator.py`
- `tests/test_task_linter.py`
- `tests/test_scoring_audit.py`
- `tests/test_gmail_seed_stability.py`

For a short map of the retired page benchmark and other legacy references still kept for history, see [share_docs/PAST_IMPLEMENTATIONS.md](share_docs/PAST_IMPLEMENTATIONS.md).

## Testing

Python benchmark and integrity suite:

```bash
python -m pytest -q tests
```

If you run tests from the workspace root above `webagentbench/`, use:

```bash
python -m pytest -q webagentbench/tests
```

High-signal subsets:

```bash
python -m pytest -q tests/test_benchmark_integrity.py tests/test_e2e_integration.py tests/test_canary_trajectories.py
python -m pytest -q tests/test_task_linter.py tests/test_scoring_audit.py tests/test_axtree_audit.py
```

Frontend workspace:

```bash
pnpm -C environments build
pnpm -C environments test
pnpm -C environments dev:gmail
```

The built Gmail bundle is written to `static/envs/gmail/`. The FastAPI app marks the environment unavailable when the bundle is missing or stale relative to `environments/gmail/src/` and `environments/shared/src/`.

## Results And Artifacts

Sample review artifacts checked into this repo live under [results/webagentbench/](results/webagentbench/). For the current local artifact layout and naming, see [results/webagentbench/README.md](results/webagentbench/README.md).

These checked-in JSON files are examples and review artifacts, not a canonical leaderboard for the benchmark.

## Historical Note

Older changelog sections and result tables refer to the retired page-based benchmark (`v1`-`v10`). They are kept as archival context, not as the description of the active Gmail benchmark in this checkout.
