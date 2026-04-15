# Progress Log

## Session: 2026-04-12

### Phase 8: `uv` / `pytest` Bring-Up
- **Status:** complete
- Actions taken:
  - Verified that the ambient interpreter still fails pytest collection because it lacks `playwright`, then confirmed `uv run --with playwright --with browsergym-core ...` from `~/Documents/projects/LLMOS` resolves the missing browser packages cleanly.
  - Added controller-secret helper functions to `runner.py`, surfaced the active secret on `app.state`, and updated the affected API tests to send controller headers consistently.
  - Fixed stale variant references and controller-auth expectations in `test_benchmark_integrity.py`.
  - Aligned `test_e2e_integration.py` to the current public session-summary contract by asserting degradation metadata is exposed while internal `seed` is not.
  - Rewrote `test_canary_trajectories.py` around the current Gmail tasks and managed variants:
    - current easy-task contracts (`alice@thornton.com`, `dave@thornton.com`)
    - current retry variants (`*_star_retry`, `*_send_retry`, `*_forward_retry`, `*_filter_retry`)
    - current decoy / exploration variants (`*_spam_twin`, `*_budget_twin`, `*_label_trap`, `*_exploration`)
  - Re-ran the full high-signal pytest slice under `uv`.
- Files created/modified:
  - app.py
  - runner.py
  - tests/test_benchmark_integrity.py
  - tests/test_e2e_integration.py
  - tests/test_canary_trajectories.py
  - task_plan.md
  - findings.md
  - progress.md

### Hard Phase 1: Audit and Triage
- **Status:** complete
- Actions taken:
  - Recounted the active hard/expert/frontier task slice in `amazon`, `booking`, `gmail`, `reddit`, and `robinhood`.
  - Identified the final uncovered hard task (`reddit_post_edit_settings`) and the two malformed hard tasks that broke seed validation (`amazon_diagnose_cart`, `rh_options_covered_call`).
  - Audited several Reddit frontier workflows and found weak or impossible graders caused by missing exact checks and baseline-state assumptions.
- Files created/modified:
  - task_plan.md
  - findings.md
  - progress.md

### Hard Phase 2: Task and Runner Repairs
- **Status:** complete
- Actions taken:
  - Updated `scripts/generate_missing_hard_variants.py` so the managed hard pass includes `reddit_post_edit_settings`.
  - Fixed `amazon_diagnose_cart` output declarations and patched `backend/seeders/amazon.py` so aliased optional outputs with `None` values no longer raise false missing-output errors.
  - Updated `tasks/_seed_builders_robinhood.py` to export per-symbol seeded prices and patched `rh_options_covered_call` to request `stock_price_AAPL`.
  - Tightened five Reddit hard/frontier task YAMLs:
    - `reddit_complete_account_setup`
    - `reddit_full_inbox_management`
    - `reddit_platform_migration`
    - `reddit_inbox_driven_engagement`
    - `reddit_post_edit_settings`
  - Added exact-body/message/settings checks and corrected negative thresholds to account for the seeded Reddit baseline.
- Files created/modified:
  - backend/seeders/amazon.py
  - scripts/generate_missing_hard_variants.py
  - tasks/_seed_builders_robinhood.py
  - tasks/amazon/amazon_diagnose_cart.yaml
  - tasks/robinhood/rh_options_covered_call.yaml
  - tasks/reddit/reddit_complete_account_setup.yaml
  - tasks/reddit/reddit_full_inbox_management.yaml
  - tasks/reddit/reddit_platform_migration.yaml
  - tasks/reddit/reddit_inbox_driven_engagement.yaml
  - tasks/reddit/reddit_post_edit_settings.yaml

### Hard Phase 3: Regeneration and Validation
- **Status:** complete
- Actions taken:
  - Regenerated the managed hard variants and wrote `58` variant files.
  - Re-ran YAML sanity checks on all touched task files.
  - Materialized the full active hard/expert/frontier slice at seed `42`.
  - Created sessions for every managed hard variant across Amazon, Booking, Gmail, Reddit, and Robinhood.
  - Recomputed hard-task coverage by environment.
- Files created/modified:
  - injector/variants/*
  - task_plan.md
  - findings.md
  - progress.md

### Hard Phase 4: Cross-Environment Hardening
- **Status:** complete
- Actions taken:
  - Strengthened five additional weak hard tasks across Gmail, Amazon, and Robinhood:
    - `gmail_meeting_negotiation`
    - `gmail_action_item_extraction`
    - `amazon_return_and_rebuy`
    - `amazon_review_aggregation`
    - `rh_diagnose_portfolio_drop`
  - Replaced low-signal Gmail variant noise with realistic email/thread decoys in:
    - `gmail_meeting_negotiation__grounding.yaml`
    - `gmail_action_item_extraction__state_tracking.yaml`
    - `gmail_thread_detective__exploration.yaml`
  - Re-ran targeted YAML, materialization, and Gmail variant session checks.
  - Re-ran full active hard-task materialization after the second-pass edits.
- Files created/modified:
  - tasks/gmail/gmail_meeting_negotiation.yaml
  - tasks/gmail/gmail_action_item_extraction.yaml
  - tasks/amazon/amazon_return_and_rebuy.yaml
  - tasks/amazon/amazon_review_aggregation.yaml
  - tasks/robinhood/rh_diagnose_portfolio_drop.yaml
  - injector/variants/gmail_meeting_negotiation__grounding.yaml
  - injector/variants/gmail_action_item_extraction__state_tracking.yaml
  - injector/variants/gmail_thread_detective__exploration.yaml
  - task_plan.md
  - findings.md
  - progress.md

### Hard Phase 4 Continued: Grader/Variant Deepening
- **Status:** complete
- Actions taken:
  - Strengthened seven more weak hard/frontier tasks across Amazon, Booking, Gmail, and Reddit:
    - `amazon_diagnose_cart`
    - `amazon_compare_and_buy_cheapest`
    - `amazon_deal_hunter`
    - `booking_diagnose_wrong_dates`
    - `gmail_priority_escalation`
    - `gmail_thread_blame_trace`
    - `reddit_end_to_end_workflow`
  - Replaced three more low-signal variants with task-specific decoys:
    - `gmail_priority_escalation__grounding.yaml`
    - `gmail_thread_blame_trace__state_tracking.yaml`
    - `reddit_end_to_end_workflow__subreddit_collision.yaml`
  - Re-ran targeted YAML parsing, task materialization, and route-level variant session creation for the touched files.
  - Re-ran full active hard-task materialization after the third-pass edits.
- Files created/modified:
  - tasks/amazon/amazon_diagnose_cart.yaml
  - tasks/amazon/amazon_compare_and_buy_cheapest.yaml
  - tasks/amazon/amazon_deal_hunter.yaml
  - tasks/booking/booking_diagnose_wrong_dates.yaml
  - tasks/gmail/gmail_priority_escalation.yaml
  - tasks/gmail/gmail_thread_blame_trace.yaml
  - tasks/reddit/reddit_end_to_end_workflow.yaml
  - injector/variants/gmail_priority_escalation__grounding.yaml
  - injector/variants/gmail_thread_blame_trace__state_tracking.yaml
  - injector/variants/reddit_end_to_end_workflow__subreddit_collision.yaml
  - task_plan.md
  - findings.md
  - progress.md

### Hard Phase 6: Negative-Check Deepening
- **Status:** complete
- Actions taken:
  - Re-audited the remaining `50` active hard tasks with exactly `2` negative checks across Amazon, Gmail, Reddit, and Robinhood.
  - Extracted current task contracts, targets, and negative descriptions by environment.
  - Inspected route mutation names/payloads to design audit-log-aware negatives, especially for Robinhood where wrong action surfaces are easy to detect precisely.
  - Chose environment-specific hardening patterns instead of adding more generic global caps.
  - Strengthened all `50` remaining hard/expert/frontier tasks that were still sitting at exactly `2` negative checks:
    - Gmail `10`
    - Reddit `7`
    - Amazon `5`
    - Robinhood `28`
  - Tightened several underspecified positive checks while touching the files, especially for Reddit workflows that were missing exact body/vote coverage.
  - Fixed the evaluator/schema mismatch in `rh_dividend_reinvestment_analysis` by replacing the non-existent `state.dividend_settings` checks with checks against `state.settings.reinvest_dividends`.
  - Re-ran YAML parsing, targeted seeded evaluation on all `50` touched tasks, and full active hard-slice materialization/evaluation.
- Files created/modified:
  - tasks/gmail/*
  - tasks/reddit/*
  - tasks/amazon/*
  - tasks/robinhood/*
  - task_plan.md
  - findings.md
  - progress.md

### Hard Phase 7: Three-Negative Cohort Reduction
- **Status:** complete
- Actions taken:
  - Recounted the remaining active hard tasks with exactly `3` negative checks and selected the lowest-check / cleanest-action-surface cohort in Amazon, Gmail, Reddit, and Robinhood.
  - Strengthened fourteen additional hard/expert/frontier tasks:
    - Gmail:
      - `gmail_meeting_negotiation`
      - `gmail_thread_blame_trace`
      - `gmail_incident_postmortem_assembly`
      - `gmail_thread_archaeology`
    - Amazon:
      - `amazon_deal_discovery_checkout`
      - `amazon_wishlist_curation`
    - Reddit:
      - `reddit_block_and_cleanup`
      - `reddit_content_management`
      - `reddit_profile_engage_message`
    - Robinhood:
      - `rh_complex_transfer_reconciliation`
      - `rh_live_comparative_watch`
      - `rh_live_cross_stock_alert`
      - `rh_live_multi_stock_limits`
      - `rh_options_expiration_management`
  - Converted several residual generic negatives into exact wrong-target or audit-log-aware negatives.
  - Tightened a few lingering loose positive checks, especially the Reddit content/outreach tasks.
  - Re-ran touched-task YAML/materialization/evaluation checks and a full active hard-slice materialization/evaluation recount.
- Files created/modified:
  - tasks/gmail/gmail_meeting_negotiation.yaml
  - tasks/gmail/gmail_thread_blame_trace.yaml
  - tasks/gmail/gmail_incident_postmortem_assembly.yaml
  - tasks/gmail/gmail_thread_archaeology.yaml
  - tasks/amazon/amazon_deal_discovery_checkout.yaml
  - tasks/amazon/amazon_wishlist_curation.yaml
  - tasks/reddit/reddit_block_and_cleanup.yaml
  - tasks/reddit/reddit_content_management.yaml
  - tasks/reddit/reddit_profile_engage_message.yaml
  - tasks/robinhood/rh_complex_transfer_reconciliation.yaml
  - tasks/robinhood/rh_live_comparative_watch.yaml
  - tasks/robinhood/rh_live_cross_stock_alert.yaml
  - tasks/robinhood/rh_live_multi_stock_limits.yaml
  - tasks/robinhood/rh_options_expiration_management.yaml
  - task_plan.md
  - findings.md
  - progress.md

## Test Results
| Test | Input | Expected | Actual | Status |
|------|-------|----------|--------|--------|
| Managed hard generator | `python3 scripts/generate_missing_hard_variants.py` | Regenerate the managed hard slice | `wrote 58 variants` | ✓ |
| Touched YAML parse check | `yaml.safe_load(...)` for touched Amazon/Robinhood/Reddit task files | All edited task YAMLs parse cleanly | All edited files parsed successfully | ✓ |
| Full hard materialization | Materialize every active `hard`/`expert`/`frontier` task at seed `42` | No task should fail to seed | `hard_tasks 226`, `materialize_errors 0` | ✓ |
| Managed hard session creation | Create a route-level session for every managed hard variant | Every managed variant should load and apply | `managed_variant_sessions 58`, `session_errors 0` | ✓ |
| Hard coverage audit | Active hard tasks vs variant base ids | Every hard task has at least one variant | Amazon `33/33`, Booking `46/46`, Gmail `57/57`, Reddit `46/46`, Robinhood `44/44` | ✓ |
| Second-pass YAML sanity | `yaml.safe_load(...)` on touched second-pass tasks and variants | All edited files parse cleanly | All touched files parsed successfully | ✓ |
| Second-pass task materialization | Materialize the five newly hardened tasks at seed `42` | All five materialize cleanly | All five returned `OK` | ✓ |
| Second-pass Gmail variant sessions | Direct Gmail `create_session(..., variant_filename=...)` for the three upgraded variants | All three variants load and apply | All three returned `OK` | ✓ |
| Full hard materialization recheck | Re-materialize every active hard task after the second-pass edits | No regression in seeded task state | `hard_tasks 226`, `materialize_errors 0` | ✓ |
| Third-pass YAML sanity | `yaml.safe_load(...)` on the 7 touched task YAMLs and 3 new variant YAMLs | All edited files parse cleanly | All touched files parsed successfully after quoting colon-bearing strings | ✓ |
| Third-pass task materialization | Create sessions for the 7 newly hardened tasks at seed `42` | All seven materialize cleanly | All seven returned `OK` | ✓ |
| Third-pass variant sessions | Route-level session creation for the 3 upgraded Gmail/Reddit variants | All three variants load and apply | All three returned `OK` | ✓ |

## Session: 2026-04-15

### Trajectory Visualizer Replay Repair
- **Status:** complete
- Actions taken:
  - Confirmed that the user-facing `element not found` failures were coming from the legacy HTML visualizer generated by `visualize.py`, which is linked from `/launch` → `/trajectories`.
  - Added Python-side normalization in `visualize.py` so raw flat target payloads are converted into the nested `targets.ref` / `targets.from_ref` / `targets.to_ref` shape expected by the embedded replay JS.
  - Fixed the embedded replay JS to:
    - merge `session` into existing `start_path` query strings instead of appending a second `?`
    - forward `variant_filename` and degradation data when creating replay sessions
    - use realm-safe iframe element checks instead of `instanceof HTMLElement`
    - score target candidates more flexibly across selector drift and role/name variations
  - Added focused regression tests in `tests/test_visualize.py`.
  - Regenerated `static/bedrock_subset_viz.html` and verified live interactive replay in the browser with `agent-browser`.
- Files created/modified:
  - visualize.py
  - scripts/viz_watcher.py
  - tests/test_visualize.py
  - task_plan.md
  - findings.md
  - progress.md

## Replay Repair Verification
| Test | Input | Expected | Actual | Status |
|------|-------|----------|--------|--------|
| Visualizer unit tests | `python3 -m pytest -q tests/test_visualize.py` | New normalization / HTML guard tests stay green | `5 passed` | ✓ |
| Python syntax check | `python3 -m py_compile visualize.py scripts/viz_watcher.py` | Patched Python files compile | Passed | ✓ |
| Embedded JS syntax | `node --check` on the generated `<script>` from `generate_html(...)` | No syntax errors in the replay JS | `node-check-ok` | ✓ |
| Visualizer regeneration | `python3 -m webagentbench.scripts.viz_watcher --once` | Regenerate `static/bedrock_subset_viz.html` with patched HTML | Rebuilt successfully | ✓ |
| Live replay smoke test | `agent-browser` on `http://127.0.0.1:8090/static/bedrock_subset_viz.html` | Interactive replay advances without immediate lookup failures | step 1 `clicked`, step 2 `clicked`, step 3 `clicked`, step 4 `filled "Alex Chen"` | ✓ |
| Full hard materialization after third pass | Re-materialize every active hard task after the latest edits | No regression in seeded task state | `hard_tasks 226`, `materialize_errors 0` | ✓ |
| Negative-check audit | Evaluate all active hard tasks at seed `42` and collect negative-check errors/counts | No runtime errors; identify remaining weak coverage | `neg_check_errors 0`, but `50/226` tasks still have only `2` negative checks | ✓ |
| Phase 6 YAML sanity | `yaml.safe_load(...)` on the `50` edited task YAMLs | All edited task files parse cleanly | `yaml_files 50`, `yaml_errors 0` | ✓ |
| Phase 6 touched-task evaluation | Materialize and evaluate the `50` edited tasks at seed `42` | No seed or eval-expression regressions in the touched batch | `materialize_errors 0`, `eval_errors 0` | ✓ |
| Phase 6 hard-slice materialization/eval | Materialize and evaluate every active hard task after the negative-check pass | No regressions across the full slice | `hard_tasks 226`, `materialize_errors 0`, `eval_errors 0` | ✓ |
| Phase 6 backlog recount | Recount active hard tasks with exactly `2` negatives | Remaining weak two-negative backlog removed | `neg_eq_2_total 0` | ✓ |
| Post-pass negative distribution | Recount negative-check counts across the full active hard slice | Identify the next weakest cohort after the repaired tail | `3-neg tasks 82`, `4-neg tasks 103` | ✓ |
| Interim touched-task validation | Parse, materialize, and evaluate the `17` tasks from the prior patch batch | Catch parser / seed / eval regressions before the next pass | `yaml_errors 0`, `materialize_errors 0`, `eval_errors 0` | ✓ |
| Phase 7 touched-task validation | Parse, materialize, and evaluate the `14` newly hardened tasks at seed `42` | No regressions in the next three-negative cohort batch | `yaml_errors 0`, `materialize_errors 0`, `eval_errors 0` | ✓ |
| Phase 7 hard-slice materialization/eval | Re-materialize and evaluate every active hard task after the new cohort pass | No regressions across the full slice | `hard_tasks 226`, `materialize_errors 0`, `eval_errors 0` | ✓ |
| Phase 7 backlog recount | Recount active non-booking hard tasks with exactly `3` negatives | Measure the reduction in the next weakest cohort | `non_booking_neg3_total 31` (down from `45`) | ✓ |
| Phase 7 negative distribution | Recount negative-check counts across the full active hard slice after the cohort pass | Identify the new frontier after the latest deepening batch | `{3: 51, 4: 104, 5: 40, 6: 16, 7: 7, 8: 5, 9: 2, 10: 1}` | ✓ |
| `uv` import probe | `uv run --with playwright --with browsergym-core python - <<'PY' ...` | Confirm `uv` can supply the missing browser packages without editing the parent workspace | `pytest`, `playwright`, `browsergym`, and `browsergym.core` all imported successfully under Python `3.10.17` | ✓ |
| Integrity pytest under `uv` | `uv run --with playwright --with browsergym-core python -m pytest -q webagentbench/tests/test_benchmark_integrity.py` | Integrity suite should collect and pass with current controller-secret wiring and variant names | `23 passed` | ✓ |
| `e2e` pytest under `uv` (initial) | `uv run --with playwright --with browsergym-core python -m pytest -q webagentbench/tests/test_e2e_integration.py` | Identify remaining stale assertions after the controller-header fixes | `18 passed, 1 failed` (`test_session_metadata_persisted` expecting public `seed`) | ✓ |
| Canary pytest under `uv` (initial) | `uv run --with playwright --with browsergym-core python -m pytest -q webagentbench/tests/test_canary_trajectories.py` | Identify remaining stale contracts/variant names in the canary slice | `6 passed, 15 failed` due to stale Gmail task targets, obsolete variant filenames, and outdated variant-behavior assertions | ✓ |
| `e2e` pytest under `uv` (final) | `uv run --with playwright --with browsergym-core python -m pytest -q webagentbench/tests/test_e2e_integration.py` | `e2e` suite should pass after aligning the public-session assertion | `19 passed` | ✓ |
| Canary pytest under `uv` (final) | `uv run --with playwright --with browsergym-core python -m pytest -q webagentbench/tests/test_canary_trajectories.py` | Rewritten Gmail canaries should match the current task and variant contracts | `15 passed` | ✓ |
| Combined high-signal pytest slice | `uv run --with playwright --with browsergym-core python -m pytest -q webagentbench/tests/test_benchmark_integrity.py webagentbench/tests/test_e2e_integration.py webagentbench/tests/test_canary_trajectories.py` | Integrity, `e2e`, and canary suites all pass together under the same `uv` invocation | `57 passed` | ✓ |

## Error Log
| Timestamp | Error | Attempt | Resolution |
|-----------|-------|---------|------------|
| 2026-04-12 | YAML scanner rejected inline Reddit eval expressions containing `Re:` | 1 | Switched those expr fields to block scalars |
| 2026-04-12 | Amazon alias resolution treated aliased `None` as a missing output | 1 | Added a sentinel-based alias resolution path in `backend/seeders/amazon.py` |
| 2026-04-12 | Booking route validation helper used `session_manager=` instead of `sm=` | 1 | Re-ran the Booking session check with the correct dependency argument |
| 2026-04-12 | Gmail variant parsing/validation misread unquoted `Re:` strings as mappings | 1 | Quoted the affected subject strings and reran Gmail variant session creation |
| 2026-04-12 | New Gmail variants with `Status update:` and `Working summary:` failed YAML parsing because the colon-bearing strings were unquoted | 1 | Quoted the subject/body scalars and reran variant parsing/session creation |
| 2026-04-12 | `gmail_misrouted_correction` failed YAML parsing because a new `desc:` string contained an unquoted `:` | 1 | Quoted the description scalar and reran the touched-task validation batch |
| 2026-04-12 | A bundled Robinhood `apply_patch` batch failed because one hunk no longer matched the current file context | 1 | Reapplied the Robinhood edits file-by-file with exact contexts |
| 2026-04-12 | Bare `python3 -m pytest` failed during collection because the ambient interpreter lacked `playwright` | 1 | Switched to `uv run --with playwright --with browsergym-core ...` from the parent workspace |
| 2026-04-12 | `pytest` collection under `uv` then failed because `controller_headers` was imported from `runner.py` but not defined there | 1 | Added controller-secret helpers to `runner.py`, surfaced the secret on `app.state`, and updated tests to send controller headers |
| 2026-04-12 | Rewritten canary filter test assumed `gmail_filter_repair_chain` seeded a narrow `invoices@acmewidgets.com` filter to delete | 1 | Switched the canary to exercise the retry on the actual create-filter path, which matches the current task seed and still validates the variant |
| 2026-04-12 | Rewritten canary spam-twin test asserted the old serialized email key `from` instead of the current `from_addr` | 1 | Updated the assertion to use `from_addr` after inspecting the live Gmail API payload |
| 2026-04-15 | `pnpm exec tsc --noEmit` failed from the repo root because `environments/shared` is a package, not the workspace root | 1 | Re-ran the typecheck from `environments/shared`, which passed |
| 2026-04-15 | The first repo-wide audit-action helper tried to AST-parse arbitrary eval expressions after naive `{target...}` substitution and hit syntax errors on quoted placeholders | 1 | Replaced the action-ref extraction with a regex-based collector that only targets explicit `e.action` comparisons |

## 5-Question Reboot Check
| Question | Answer |
|----------|--------|
| Where am I? | Phase 8 is complete; the `uv`-based high-signal pytest slice is green |
| Where am I going? | Hand the repo back with the repeatable `uv` command and the test-file changes recorded |
| What's the goal? | Keep the benchmark-quality work intact while also making the repo’s `uv`-based pytest path actually runnable |
| What have I learned? | The real blocker was stale repo-side test code, not `uv`; once controller auth and current Gmail contracts were reflected in the tests, the slice passed cleanly |
| What have I done? | Verified the `uv` path, fixed controller-secret test plumbing, aligned the `e2e` session-summary assertion to the public API, rewrote the Gmail canaries to the current managed variants, and ran the combined `57`-test slice successfully |

### Booking Evaluate Repair
- **Status:** complete
- Actions taken:
  - Reproduced the toolbar failure against `booking_add_payment` and confirmed the backend exception was `NameError: name 'request' is not defined` inside `backend/routes/booking.py`.
  - Added the missing FastAPI `request: Request` parameter to the Booking evaluate route.
  - Hardened `environments/shared/src/components/BenchmarkToolbar.tsx` so evaluate falls back to raw response text when the server does not return JSON.
  - Added a focused Booking regression to `tests/test_e2e_integration.py` that creates a `booking_add_payment` session, adds the required Discover `7777` card, and confirms evaluate returns success.
- Files created/modified:
  - backend/routes/booking.py
  - environments/shared/src/components/BenchmarkToolbar.tsx
  - tests/test_e2e_integration.py

## Booking Evaluate Verification
| Test | Input | Expected | Actual | Status |
|------|-------|----------|--------|--------|
| Booking/public evaluate regression slice | `python3 -m pytest -q tests/test_e2e_integration.py -k 'public_evaluate_allows_bound_session_task_without_controller_headers or booking_add_payment_can_evaluate_successfully_after_matching_mutation'` | Booking evaluate route returns JSON again and the task-specific add-payment flow scores successfully | `6 passed, 30 deselected` | ✓ |
| Shared toolbar typecheck | `pnpm exec tsc --noEmit` from `environments/shared` | Toolbar error-handling change stays type-safe | Passed | ✓ |
| Direct Booking API smoke test | Create `booking_add_payment` session and call `/api/env/booking/evaluate` before mutation | Endpoint should return a structured evaluation payload instead of a raw `500` | HTTP `200` with JSON score payload | ✓ |

### Negative-Check Audit Repair
- **Status:** complete
- Actions taken:
  - Audited repo-wide `e.action` references in task eval expressions against the backend's emitted audit actions.
  - Found one concrete dead-check family repeated across `6` Booking tasks: stale `payment_method.delete` references that never match the real `payment.remove` audit action.
  - Repaired the `6` Booking task YAMLs and tightened the two targeted removal guards that also had stale payload-key assumptions.
  - Added a linter in `tests/test_task_linter.py` that fails on any eval expression referencing an unknown audit action.
  - Added focused Booking evaluator regressions in `tests/test_booking_seed_stability.py` proving the repaired negatives now fail on wrong removals and allow intended removals.
- Files created/modified:
  - tasks/booking/booking_add_payment.yaml
  - tasks/booking/booking_expert_account_migration.yaml
  - tasks/booking/booking_expert_complete_account_review.yaml
  - tasks/booking/booking_frontier_payment_and_booking.yaml
  - tasks/booking/booking_full_account_setup.yaml
  - tasks/booking/booking_set_default_payment.yaml
  - tests/test_task_linter.py
  - tests/test_booking_seed_stability.py

## Negative-Check Audit Verification
| Test | Input | Expected | Actual | Status |
|------|-------|----------|--------|--------|
| Audit-action linter | `python3 -m pytest -q tests/test_task_linter.py -k 'eval_audit_action_refs_match_emitted_actions'` | All explicit audit-action refs in evals match backend emitters | `1 passed` | ✓ |
| Focused Booking negative-check regressions | `python3 -m pytest -q tests/test_booking_seed_stability.py -k 'booking_add_payment_negative_check_penalizes_removed_payment_method or booking_payment_removal_negative_checks_bind_allowed_target'` | Repaired Booking negatives fire on wrong removal events and allow intended removal targets | `3 passed` | ✓ |
| Booking materialization/eval sweep | `python3 -m pytest -q tests/test_booking_seed_stability.py -k 'all_booking_tasks_have_error_free_eval or all_booking_tasks_materialize'` | Booking task corpus still seeds and evaluates cleanly after YAML changes | `2 passed` | ✓ |
| Repo-wide audit-action scan | custom Python audit over all task eval expressions vs backend-emitted actions | No stale explicit audit-action refs remain | `invalid_action_refs 0` | ✓ |
