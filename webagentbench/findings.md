# Findings & Decisions

## Requirements
- Review the current benchmark design carefully.
- Identify both unreasonable design choices and concrete bugs.
- Use browser validation when runtime behavior materially affects the benchmark.

## Research Findings
- The repo mixes five benchmark environments: `booking`, `gmail`, `amazon`, `reddit`, and `robinhood`.
- Planning files in the repo were stale and described a prior Booking-only audit, so they were replaced for the current repo-wide review.
- The public docs are materially stale relative to the implementation: `README.md` still says the current checkout exposes only Gmail and says `gmail_search_and_star` requires a recorded search event, while `manifest.json` exposes five environments and the task no longer checks client events.
- The evaluator executes raw Python `eval` against the live `state` object and allows arbitrary method calls on that object. A synthetic check of `state.touch()` passed and mutated state during grading, so the evaluator is not side-effect free.
- Robinhood live-price tasks are wall-clock-driven via `RobinhoodState.tick()`, which advances trajectories on request-time reads. `SessionManager.create_session()` installs the `PriceEngine` but does not synchronize seeded stock prices to trajectory tick 0.
- Reproduction on seed `42` shows trajectory mismatch at session start for multiple Robinhood live tasks: `rh_live_buy_the_dip` starts AAPL at `194.58` while the task trajectory starts at `190.0`; `rh_live_alert_chain` starts NVDA at `880.27` while the trajectory starts at `875.0`; `rh_live_watch_and_buy` also starts AAPL at `194.58` while the trajectory starts at `190.0`.
- The Reddit corpus contains multiple long, multi-step frontier tasks with severely under-specified grading. `reddit_platform_migration` has eight numbered instructions and `expected_steps: 55`, but its grader only checks `theme == dark` and `unread_notification_count() == 0`, with no negative checks.
- Reproduction confirms the Reddit under-grading is exploitable: using only `/api/env/reddit/notifications/mark-all-read` and `/api/env/reddit/settings {theme: dark}` yields `score: 1.0` and `success: true` for `reddit_platform_migration`, while all other requested work is skipped.
- The benchmark validation surface is heavily Gmail-skewed. `tests/test_scoring_audit.py` only scans `tasks/gmail`, and `tests/test_canary_trajectories.py` hardcodes Gmail endpoints and tasks.
- The Gmail canary suite is stale relative to the task YAMLs. The canaries still send to `alice@company.test` and `dave@company.test`, while `gmail_compose_new` and `gmail_forward_email` now require `alice@thornton.com` and `dave@thornton.com`.
- Running the non-browser integrity subset produced `5292 passed, 5 failed`; all five failures were stale Gmail canaries around `gmail_compose_new` and `gmail_forward_email`.
- Booking’s session API is inconsistent with the other environments: it returns `targets` instead of `resolved_targets`, omits `title` and `degradation_active`, and does not validate variant-task mismatch before applying Booking variants.
- Reproduction on the live server shows Booking variant mismatch handling is weaker than Gmail’s: posting `task_id=booking_view_reservation` with `variant_filename=booking_reply_to_hotel__planning.yaml` returns HTTP 500 instead of a clean task/variant mismatch error.

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| Start from docs, schema, and evaluator before sampling tasks | Design bugs are easier to spot once the intended contract is explicit |
| Sample each environment instead of reading every task exhaustively | The corpus is large enough that representative checks are more efficient initially |
| Use browser validation only where grading depends on actual UI/client behavior | Static inspection alone can miss instrumentation or route-based scoring issues |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| Previous planning files did not match the current task | Rewrote `task_plan.md`, `findings.md`, and `progress.md` for the benchmark audit |

## Resources
- `README.md`
- `share_docs/TASK_GENERATION_STANDARD.md`
- `tasks/_schema.py`
- `tasks/_registry.py`
- `tasks/_evaluator.py`
- `evaluator.py`
- `tests/`
