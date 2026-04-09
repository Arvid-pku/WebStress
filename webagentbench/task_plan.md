# Task Plan: Benchmark Design Audit

## Goal
Review the current benchmark design across task generation, evaluation, environments, and runtime behavior to identify unreasonable assumptions, buggy grading logic, or benchmark choices that could distort agent comparisons.

## Current Phase
Phase 4

## Phases
### Phase 1: Contract Review
- [x] Read the benchmark docs, schema, registry, evaluator, and benchmark entrypoints
- [x] Extract the intended guarantees: determinism, realism, task difficulty, grading, and safety boundaries
- [x] Record initial concerns in `findings.md`
- **Status:** complete

### Phase 2: Corpus Sampling
- [x] Inspect representative tasks, seed builders, and tests across Booking, Gmail, Amazon, Reddit, and Robinhood
- [x] Look for always-pass graders, underspecified targets, impossible actions, or duplicated task templates
- [x] Record cross-environment patterns in `findings.md`
- **Status:** complete

### Phase 3: Runtime Validation
- [x] Run targeted local checks for evaluator behavior and task determinism
- [x] Exercise selected browser flows where the benchmark depends on client-side instrumentation or fragile UI behavior
- [x] Separate benchmark-design bugs from isolated environment implementation bugs
- **Status:** complete

### Phase 4: Delivery
- [x] Summarize prioritized findings with file references
- [x] Distinguish hard bugs, design risks, and improvement advice
- [x] Note verification performed and remaining gaps
- **Status:** complete

## Key Questions
1. Are task instructions, seeded state, and grader logic aligned tightly enough for reliable scoring?
2. Does the benchmark reward real task completion, or can agents exploit shortcuts, client-state leaks, or evaluator loopholes?
3. Are the environments and task corpus balanced and realistic enough to support meaningful comparisons?

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Audit the benchmark at the repo level instead of a single environment | The user asked about the current benchmark design overall |
| Combine static inspection with targeted runtime checks | Benchmark issues often hide in grading contracts and UI instrumentation |
| Treat environment bugs separately from benchmark-design bugs | Some defects hurt UX, but only a subset invalidates the benchmark |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| Existing planning files described a previous Booking-only audit | 1 | Replaced them with a repo-wide benchmark review plan |
| `tests/test_benchmark_integrity.py` could not collect in the local `uv` environment | 1 | Continued with the remaining integrity subset; the local environment is missing `playwright` |

## Notes
- Preserve unrelated worktree changes in `app.py` and `manifest.json`.
- Focus on benchmark validity first: determinism, grading robustness, task reasonableness, and exploit resistance.
- Browser validation confirmed Booking action-log grading works live for `booking_view_reservation`.
- Browser validation confirmed `gmail_search_and_star` now succeeds on pure outcome grading without any client-event requirement.
