# Task Plan: Hard Benchmark Quality Pass

## Goal
Improve the quality of the active hard/expert/frontier benchmark slice in `amazon`, `booking`, `gmail`, `reddit`, and `robinhood`. Ignore `lms` and `patient_portal`. Keep easy/medium tasks in the tree for now, but prioritize hard, diverse, meaningful tasks and primitive-aligned variants.

## Current Phase
Phase 9

## Phases
### Phase 1: Audit and Triage
- [x] Recheck hard/expert/frontier coverage in the active environments
- [x] Identify missing hard variants and malformed task seeds
- [x] Identify under-graded hard tasks whose evals do not enforce the instruction contract
- **Status:** complete

### Phase 2: Task and Runner Repairs
- [x] Fix the Amazon hard-task seed aliasing bug exposed by `amazon_diagnose_cart`
- [x] Fix Robinhood hard-task target resolution for `rh_options_covered_call`
- [x] Tighten the weakest Reddit hard/frontier task graders around exact bodies, settings, read-state cleanup, and baseline-aware negative checks
- [x] Extend the managed hard-variant generator to the remaining uncovered Reddit task
- **Status:** complete

### Phase 3: Regeneration and Validation
- [x] Regenerate the managed hard variants
- [x] Materialize the full active hard/expert/frontier slice at seed `42`
- [x] Create sessions for every managed hard variant to verify variant loading and injection
- [x] Recheck hard-task variant coverage by environment
- **Status:** complete

### Phase 4: Cross-Environment Hardening
- [x] Strengthen the weakest remaining hard-task graders outside Reddit
- [x] Replace low-signal Gmail flagship variants with realistic thread/email decoys
- [x] Revalidate the touched variants and re-run whole hard-slice materialization
- **Status:** complete

### Phase 5: Delivery
- [ ] Summarize the benchmark-quality improvements and remaining risks for the user
- **Status:** in_progress

### Phase 6: Negative-Check Deepening
- [x] Strengthen the remaining hard tasks that still have only `2` negative checks
- [x] Use environment-specific patterns instead of generic caps:
  - Robinhood: audit-log guards for wrong mutation surfaces
  - Gmail: wrong-thread / wrong-recipient / wrong-compose negatives
  - Reddit: wrong-target / wrong-user / wrong-post/message negatives
  - Amazon: wrong-order / wrong-product / wrong-address/payment negatives
- [x] Re-run targeted and full-slice validation after the patch batch
- **Status:** complete

### Phase 7: Three-Negative Cohort Reduction
- [x] Target the lowest-check remaining hard tasks still at `3` negatives across Amazon, Gmail, Reddit, and Robinhood
- [x] Replace residual generic negatives with exact-object or audit-log-aware negatives
- [x] Revalidate the touched tasks and rerun the full hard-slice recount
- **Status:** complete

### Phase 8: `uv` / `pytest` Bring-Up
- [x] Restore a repeatable `uv`-based test path from `~/Documents/projects/LLMOS`
- [x] Fix stale imports, controller-secret wiring, and outdated test fixtures so collection succeeds
- [x] Update the remaining failing `e2e` and canary tests to match current task and variant contracts
- [x] Re-run the high-signal pytest slice under `uv`
- **Status:** complete

### Phase 9: Final Hard-Slice Curation
- [x] Deepen the remaining active hard/expert/frontier tasks that still have only `3` negative checks
- [x] Add additional high-quality hard variants for Amazon, Booking, and Reddit so those environments are not mostly single-variant
- [x] Reduce noisy primitive tagging on the hard slice, aiming for one primary primitive and at most one secondary unless the task truly needs more
- [x] Re-run validation and recount the hard-slice quality metrics
- **Status:** complete

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Keep easy/medium tasks in place for now, but spend this pass on hard/expert/frontier quality | The user wants the simple slice available temporarily, but benchmark quality should come from the hard slice |
| Fix malformed tasks and graders instead of weakening validation | Broken task authoring silently poisons the benchmark; variants should not hide those defects |
| Add the last uncovered Reddit hard task to the managed generator instead of leaving one manual hole | Hard coverage should be complete and reproducible, not dependent on a one-off file |
| Tighten Reddit frontier graders around exact outcomes and baseline-aware counts | Several Reddit hard tasks were rewarding partial completion and some negative checks were impossible because the base state already contains sent messages and owner-authored posts |
| Follow the second pass with cross-environment hardening instead of stopping at Reddit | The weakest remaining hard tasks were spread across Gmail, Amazon, and Robinhood, and some flagship Gmail variants were still generic-noise rather than meaningful decoys |
| Treat low check-count tasks and low-signal variants as separate quality problems | Some tasks needed stricter graders, while others already had decent task contracts but weak generic variants that were not actually probing the intended primitive |
| Use audit-log-aware negatives for Robinhood instead of only raw end-state counts | Robinhood tasks frequently have clean mutation surfaces (orders, alerts, recurring, transfers, watchlists), so audit entries let the grader penalize wrong actions without baseline-count brittleness |
| Use wrong-target negatives for Gmail/Reddit/Amazon instead of more global caps | Generic “no excessive emails/posts/orders” guards miss the real failure modes; task-shaped negatives make the benchmark more diagnostic |
| Fix evaluator/schema mismatches when discovered during the negative-check pass | A “perfect” negative-check campaign is not credible if touched tasks still contain broken positive checks; `rh_dividend_reinvestment_analysis` needed its DRIP checks aligned to the actual Robinhood settings model |
| Prioritize the remaining `3`-negative cohort by lowest positive-check count and clearest action surfaces | This gives the largest benchmark-quality gain per edit while keeping each new negative concrete and task-shaped instead of padding the task with generic collateral guards |
| Keep the `uv`/`pytest` work in the same branch but track it as a separate phase | The benchmark content work is still in-flight, but the repo also needs a runnable test path; isolating the test bring-up in the plan keeps the state readable |
| Treat “do all of them” as a new benchmark-curation phase rather than a tiny follow-up | The remaining work spans task grading, variant-bank expansion, and metadata cleanup, so it needs explicit batching and validation instead of one-off edits |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| YAML parsing failed after adding `Re:` subjects to Reddit eval expressions | 1 | Rewrote those expressions as block scalars (`>-`) so the YAML parser treats them as plain strings |
| Amazon alias resolution treated a matched optional output with value `None` as if the alias lookup failed | 1 | Added a sentinel in `backend/seeders/amazon.py` so aliased `None` values are stored correctly |
| The Booking route validation helper was called with the wrong dependency argument name | 1 | Re-ran the async Booking session check using `sm=` instead of `session_manager=` |
| YAML parsed one unquoted Gmail `Re:` distractor subject as a mapping instead of a string | 1 | Quoted the `Re:` topical subject and re-ran Gmail variant session creation |
| YAML parsed new Gmail variant strings containing `:` as mappings instead of scalars | 1 | Quoted the `Status update:` subject and the `Working summary:` body in the new Gmail variant files and reran parsing/session creation |
| `rh_dividend_reinvestment_analysis` referenced a non-existent `state.dividend_settings` field during seeded evaluation | 1 | Rewrote the DRIP checks to use the actual Robinhood control exposed by the environment, `state.settings.reinvest_dividends` |
| YAML parsing failed on `gmail_misrouted_correction` because a new `desc:` string contained an unquoted `:` | 1 | Quoted the description scalar and reran the touched-task validation batch |
| A bundled Robinhood `apply_patch` batch failed because one hunk no longer matched the current file context | 1 | Reapplied the Robinhood edits file-by-file with exact contexts instead of one multi-file patch |
| Bare `python3 -m pytest` failed at collection because the interpreter did not have `playwright` | 1 | Switched to `uv run --with playwright --with browsergym-core ...` from the parent workspace and continued from there |
| Test collection then failed because `browsergym_task.py` imported `controller_headers` from `runner.py`, but `runner.py` did not define it | 1 | Added controller-secret helpers to `runner.py`, wired `app.state.controller_secret`, and updated test clients to send controller headers |

## Notes
- Preserve unrelated worktree changes, especially `tasks/_seed_builders_batch10.py`.
- Managed hard variants regenerated this pass: `58`.
- Active hard/expert/frontier coverage is now complete:
  - Amazon `33/33`
  - Booking `46/46`
  - Gmail `57/57`
  - Reddit `46/46`
  - Robinhood `44/44`
- Full active hard-task materialization now passes cleanly: `226` tasks, `0` errors.
- Managed hard-variant session creation now passes cleanly: `58` variants, `0` errors.
- Second-pass hardening strengthened these additional weak tasks:
  - `gmail_meeting_negotiation`
  - `gmail_action_item_extraction`
  - `amazon_return_and_rebuy`
  - `amazon_review_aggregation`
  - `rh_diagnose_portfolio_drop`
- Second-pass Gmail variant upgrades validated cleanly for:
  - `gmail_meeting_negotiation__grounding.yaml`
  - `gmail_action_item_extraction__state_tracking.yaml`
  - `gmail_thread_detective__exploration.yaml`
- Third-pass hardening strengthened these additional weak tasks:
  - `amazon_diagnose_cart`
  - `amazon_compare_and_buy_cheapest`
  - `amazon_deal_hunter`
  - `booking_diagnose_wrong_dates`
  - `gmail_priority_escalation`
  - `gmail_thread_blame_trace`
  - `reddit_end_to_end_workflow`
- Third-pass variant upgrades validated cleanly for:
  - `gmail_priority_escalation__grounding.yaml`
  - `gmail_thread_blame_trace__state_tracking.yaml`
  - `reddit_end_to_end_workflow__subreddit_collision.yaml`
- Post-pass weakest hard tasks by raw check count are now led by:
  - `gmail_thread_detective`
  - `gmail_diagnose_missing_reply`
  - several Robinhood hard workflows with `4` checks and `2` negatives
- The remaining negative-check backlog after the audit is `50` active hard/expert/frontier tasks with exactly `2` negative checks:
  - Amazon `5`
  - Gmail `10`
  - Reddit `7`
  - Robinhood `28`
- Phase 6 results:
  - `0` active hard tasks remain at `2` negative checks across Amazon, Gmail, Reddit, and Robinhood
  - the full active hard/expert/frontier slice still materializes cleanly: `226` tasks, `0` errors
  - the full active hard/expert/frontier slice now evaluates with `0` check or negative-check runtime errors at seed `42`
- Phase 7 strengthened these additional tasks:
  - Gmail: `gmail_meeting_negotiation`, `gmail_thread_blame_trace`, `gmail_incident_postmortem_assembly`, `gmail_thread_archaeology`
  - Amazon: `amazon_deal_discovery_checkout`, `amazon_wishlist_curation`
  - Reddit: `reddit_block_and_cleanup`, `reddit_content_management`, `reddit_profile_engage_message`
  - Robinhood: `rh_complex_transfer_reconciliation`, `rh_live_comparative_watch`, `rh_live_cross_stock_alert`, `rh_live_multi_stock_limits`, `rh_options_expiration_management`
- Phase 7 results:
  - touched-task validation stayed clean: `14` tasks, `0` YAML errors, `0` materialization errors, `0` eval-expression errors
  - the full active hard/expert/frontier slice still materializes and evaluates cleanly: `226` tasks, `0` errors
  - the non-booking `3`-negative cohort dropped from `45` to `31`
  - the current full-slice negative distribution is:
    - `3` negatives: `51`
    - `4` negatives: `104`
    - `5` negatives: `40`
    - `6` negatives: `16`
    - `7` negatives: `7`
    - `8` negatives: `5`
    - `9` negatives: `2`
    - `10` negatives: `1`
- Phase 8 current state:
  - `uv run --with playwright --with browsergym-core python -m pytest -q webagentbench/tests/test_benchmark_integrity.py` is green
  - `uv run --with playwright --with browsergym-core python -m pytest -q webagentbench/tests/test_e2e_integration.py` is green
  - `uv run --with playwright --with browsergym-core python -m pytest -q webagentbench/tests/test_canary_trajectories.py` is green after rewriting the Gmail canaries to the current managed variants
  - combined high-signal pytest slice is green: `57 passed`
- Phase 9 starting point:
  - `51` active hard/expert/frontier tasks still have only `3` negative checks
  - Booking and Reddit hard tasks are still mostly single-variant; Amazon is close to that too
  - `61` active hard/expert/frontier tasks still carry `6` or `7` primitive tags, which is too noisy for clean primitive analysis
- Phase 9 results:
  - no active hard/expert/frontier tasks remain at `3` or fewer negative checks
  - all active hard/expert/frontier tasks now carry exactly `1` primary primitive and at most `1` secondary primitive (`226` tasks at `2` total tags)
  - all active hard Amazon, Booking, and Reddit tasks now have at least `2` variants
  - managed `v2` hard variants now validate cleanly across the full generated set: `250` created sessions, `0` failures
- active-env linter-style validation is clean for `amazon`, `booking`, `gmail`, `reddit`, and `robinhood`: `3308` eval expressions checked, `0` focused violations
- the focused `uv` pytest slice remains green after the curation pass: `57 passed`

## Follow-up Task: Trajectory Visualizer Replay Repair

### Goal
- Make the legacy trajectory visualizer generated by `visualize.py` replay steps reliably from `/launch` → `/trajectories`, especially in interactive mode where the current viewer frequently reports `element not found`.

### Phases
#### Phase A: Diagnose interactive replay failures
- [x] Identify why replay sessions load the wrong page state or fail to resolve targets
- [x] Reproduce the failure on a live generated `*_viz.html`
- **Status:** complete

#### Phase B: Patch replay payloads and target lookup
- [x] Normalize raw trajectory targets before embedding them into the visualizer HTML
- [x] Fix replay URL construction so `start_path` query params survive `session` attachment
- [x] Forward variant/degradation info when creating replay sessions
- [x] Harden iframe target lookup so it works across iframe realms and selector/name drift
- **Status:** complete

#### Phase C: Verify end to end
- [x] Add focused regression tests for the Python-side visualizer prep path
- [x] Regenerate the subset visualizer and replay live steps in the browser
- **Status:** complete

### Replay Repair Findings
- `visualize.py` was embedding raw trajectory steps without reshaping flat target payloads into the nested `targets.ref` structure that its own replay JS expects.
- Interactive replay URLs were malformed for query-bearing start routes like Gmail's `/inbox?label=inbox`, because the code appended `?session=...` blindly instead of merging query params.
- Degraded/variant trajectories could not recreate the recorded state reliably because the replay session creation payload ignored `variant_filename` / degradation metadata.
- The iframe DOM matcher filtered candidates with `instanceof HTMLElement`, which fails across iframe realms and caused false `element not found` errors even when the target was visibly present.

### Validation
- `tests/test_visualize.py`: `5 passed`
- `python3 -m py_compile visualize.py scripts/viz_watcher.py`: passed
- `node --check` on the generated embedded visualizer script: passed
- Live browser smoke test on `static/bedrock_subset_viz.html` via `agent-browser`:
  - Amazon replay step 1: `#1: clicked`
  - Amazon replay step 2: `#2: clicked`
  - Amazon replay step 3: `#3: clicked`
  - Amazon replay step 4: `#4: filled "Alex Chen"`

## Follow-up Task: Booking Evaluate Repair

### Goal
- Restore the `/api/env/booking/evaluate` path used by the launcher toolbar and make the shared toolbar surface non-JSON server failures cleanly.

### Phases
#### Phase D: Reproduce and diagnose
- [x] Map the user's failing prompt to its task YAML and environment
- [x] Reproduce the current evaluate failure against the Booking route
- [x] Identify the backend exception behind the frontend JSON parse error
- **Status:** complete

#### Phase E: Patch backend, toolbar, and regression coverage
- [x] Fix the Booking evaluate route so it passes the request object into evaluation-access checks
- [x] Harden the shared benchmark toolbar's evaluate handler to fall back to raw response text on non-JSON errors
- [x] Add a Booking regression test that performs the matching payment-method mutation and then evaluates successfully
- **Status:** complete

### Booking Evaluate Findings
- The failing instruction is `tasks/booking/booking_add_payment.yaml`, not an Amazon task.
- The Booking evaluate route called `require_evaluation_access(request, ...)` but its FastAPI signature did not accept a `request: Request` parameter, so every Booking evaluate attempt raised `NameError: name 'request' is not defined`.
- The launcher toolbar always called `response.json()` for evaluate, so the plain-text `Internal Server Error` body turned into the misleading client-side message `Unexpected token 'I'`.

### Booking Evaluate Validation
- `python3 -m pytest -q tests/test_e2e_integration.py -k 'public_evaluate_allows_bound_session_task_without_controller_headers or booking_add_payment_can_evaluate_successfully_after_matching_mutation'`: `6 passed, 30 deselected`
- `pnpm exec tsc --noEmit` from `environments/shared`: passed
- direct in-process API check on `booking_add_payment`:
  - fresh session evaluate now returns HTTP `200` with a structured evaluation payload instead of a raw `500`

## Follow-up Task: Negative-Check Audit Repair

### Goal
- Audit repo-wide negative checks for evaluator guards that do not actually bind to backend-emitted audit actions, and repair any dead checks found.

### Phases
#### Phase F: Repo-wide audit
- [x] Inspect the existing negative-check linting and evaluation coverage
- [x] Compare audit-log action refs in task evals against the backend's emitted action names
- [x] Check audit-log payload-key usage for obvious stale-field mismatches
- **Status:** complete

#### Phase G: Patch and lock in
- [x] Repair the broken negative checks found in Booking task YAMLs
- [x] Add a linter that fails when any eval expression references a non-existent audit action
- [x] Add focused Booking regressions that prove the repaired negative checks now trigger
- [x] Re-run Booking materialization/eval coverage after the patch
- **Status:** complete

### Negative-Check Audit Findings
- The current repo-wide audit found one real dead negative-check family: Booking tasks were still looking for `payment_method.delete`, but the Booking backend emits `payment.remove`.
- That stale action name appeared in `6` Booking tasks:
  - `booking_add_payment`
  - `booking_expert_account_migration`
  - `booking_expert_complete_account_review`
  - `booking_frontier_payment_and_booking`
  - `booking_full_account_setup`
  - `booking_set_default_payment`
- Two of those tasks also used stale payload assumptions:
  - `booking_expert_account_migration` checked deleted-card `card_type` / `last_four`, but Booking remove events only log `pm_id`
  - `booking_frontier_payment_and_booking` checked `payment_method_id`, but the real payload key is `pm_id`
- A broader audit over audit-log payload-key usage did not surface any other clear stale-key mismatches after the Booking fixes.

### Negative-Check Audit Validation
- `python3 -m pytest -q tests/test_task_linter.py -k 'eval_audit_action_refs_match_emitted_actions'`: `1 passed`
- `python3 -m pytest -q tests/test_booking_seed_stability.py -k 'booking_add_payment_negative_check_penalizes_removed_payment_method or booking_payment_removal_negative_checks_bind_allowed_target'`: `3 passed`
- `python3 -m pytest -q tests/test_booking_seed_stability.py -k 'all_booking_tasks_have_error_free_eval or all_booking_tasks_materialize'`: `2 passed`
- repo-wide audit-action scan after the patch: `invalid_action_refs 0`
