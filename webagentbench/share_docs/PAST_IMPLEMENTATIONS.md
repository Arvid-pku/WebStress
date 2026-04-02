# Past Implementations

The current mainline WebAgentBench checkout is the Gmail environment/task benchmark.

Older references in the repository still mention a retired page-based benchmark (`v1`-`v10`) built around self-contained web pages and a different evaluation stack. Those sections are retained for historical continuity only.

## What Is Current

The active benchmark in this checkout is:

- environment/task based
- centered on `gmail`
- authored in YAML under `tasks/gmail/`
- seeded through the Gmail builder pipeline
- evaluated primarily from server-side Gmail state, with optional client `benchmark_state` checks where needed

## What Is Historical

Historical references may still mention:

- page counts such as 10, 12, or 15 pages
- page IDs instead of task IDs
- DOM-heavy validation language from the retired runtime
- version lines `v1` through `v10`
- archived result summaries from earlier benchmark iterations

Those notes are useful for understanding the benchmark's evolution, but they do not describe the current Gmail benchmark as shipped in this checkout.

## Compatibility Helpers

Some files still contain backward-compatibility support for older artifacts or terminology, for example:

- `result_utils.py`
- historical sections in `CHANGELOG.md`

This is intentional. The helpers remain so older result files can still be inspected without redefining the active benchmark.
