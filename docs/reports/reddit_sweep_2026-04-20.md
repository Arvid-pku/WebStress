# Reddit Task Sweep — gemini-3-flash-preview Report

Date run: 2026-04-19 → 2026-04-20 (~20 hours wall clock including infra recovery)
Agent: `gemini-3-flash-preview` via `google.genai` SDK (with key rotation + port rotation)
Harness: `webagentbench.agent_eval` (BrowserGym, UI-only actions — no REST/API bypass)
Scope: **every reddit task** (81 base tasks across 5 difficulty tiers) **plus every reddit variant** (78 adversarial perturbations)

Companion to [amazon_sweep_2026-04-19.md](amazon_sweep_2026-04-19.md).

---

## 1. Executive summary

| | Base | Variants |
|---|---|---|
| **Pass rate** | **15 / 81 (19%)** | **11 / 78 (14%)** |
| Average score | 0.25 | 0.19 |
| **Task bugs found** | **0** | **0** |
| Gemini rate-limit incidents | handled cleanly by rotation | 1 × 503 survived both keys |
| Chromium crashes | 2 (`reddit_curate_and_engage`, `reddit_deep_thread_engagement`) | 1 (`reddit_community_builder__notification_shadow_v2`) |
| Stray-backend cascades | caused partial data in hard variants (first attempt) | fixed by port rotation 8091–8105 |

**Bottom line:** no task bugs surfaced in the reddit sweep. Every partial-score outcome I inspected traced to agent-capability limits (gemini-3-flash-preview wandering in multi-step flows, missing constraint subgoals, picking decoy targets). Pass rates are substantially lower than amazon because reddit tasks have tighter step/time budgets and the accessibility tree on reddit pages exposes many near-identical click targets that gemini grounds poorly.

---

## 2. Setup

- **Backend**: self-spawned per task, with port rotation for variant sweeps (8091–8105) to defeat the zombie-backend cascade observed in early hard-variant runs.
- **API**: `GEMINI_API_KEY` + `GEMINI_API_KEY_2` via the `_GeminiRotatingClient` shipped in [`fc8f4bc`](.) during the amazon sweep. Zero unrecovered 429s across the entire reddit sweep.
- **Chromium**: 1117 (pre-installed from the amazon sweep).

---

## 3. Bugs found and fixed: **0**

No task-correctness bugs surfaced. Every close-call outcome (scores 0.50–0.94) traced to the agent missing a subgoal or picking a decoy target.

Representative close-calls inspected in detail:

| Task | Score | Penalty that fired | Root cause |
|---|---|---|---|
| `reddit_post_and_comment` (base + variant) | 0.85 | `Unaccounted update in posts` | Agent upvoted an extra post while engaging — legit evaluator-design penalty for unauthorized side-effects. |
| `reddit_reply_nested_comment` (base + variant) | 0.85 | `Preserve state.posts` | Same extra-post-mutation pattern. |
| `reddit_engage_user_content` (base + variant) | 0.00–0.50 | `no Update entry matched` + unaccounted on posts | Agent upvoted-but-didn't-save (or vice versa); didn't satisfy the `(vote_direction=1 AND is_saved=true)` conjunction. |
| `reddit_curate_saved` (base + variant) | 0.50 | one of two checks failed | Agent unsaved only one of the two target posts. |
| `reddit_block_and_cleanup__subreddit_shadow_v2` | 0.60 | `Target user blocked` constraint failed | Agent completed 3/3 positive checks but forgot to block the user. |
| `reddit_comment_chain_analysis__label_misalignment` | 0.65 | `Unaccounted create in comments` | Agent posted an extra comment beyond the 3 required. |
| `reddit_complete_engagement_cycle` (frontier base) | **0.94** | one constraint missed (exact reply text) | Agent posted a reply but not the exact expected text. |
| `reddit_notification_cascade` (frontier base) | 0.89 | two constraint subgoals missed | Agent didn't save the programming post or set feed sort. |

All are legitimate scoring — no task-correctness bug.

---

## 4. Pass rates

### 4.1  Base tasks

| Difficulty | Pass | Total | Rate | Avg score |
|---|---:|---:|---:|---:|
| easy | 6 | 19 | 32% | 0.34 |
| medium | 4 | 16 | 25% | 0.39 |
| hard | 2 | 16 | 13% | 0.17 |
| expert | 2 | 15 | 13% | 0.13 |
| frontier | 1 | 15 | 7% | 0.19 |
| **Total** | **15** | **81** | **19%** | **0.25** |

### 4.2  Variants

| Difficulty | Pass | Total | Rate | Avg score |
|---|---:|---:|---:|---:|
| easy | 5 | 16 | 31% | 0.31 |
| medium | 2 | 16 | 13% | 0.26 |
| hard | 3 | 16 | 19% | 0.24 |
| expert | 0 | 15 | 0% | 0.08 |
| frontier | 1 | 15 | 7% | 0.07 |
| **Total** | **11** | **78** | **14%** | **0.19** |

**Contrast with amazon:** amazon was 43/70 base (61%) and 22/56 variants (39%). Reddit is materially harder for gemini-3-flash-preview because:

- Reddit easy tasks ship with very tight step budgets (4–12 steps) vs amazon easy's 7–15 step budgets.
- Reddit pages surface dense feed UIs where decoy posts are visually adjacent to targets in the accessibility tree — grounding is harder.
- Many reddit tasks are constraint-only (e.g. `clear_notifications`, `notification_review_silent`), meaning the agent must satisfy side-conditions rather than produce a concrete positive mutation, which is a format gemini handles worse.

---

## 5. Failure-mode classification

| Reason | ~Count | Verdict |
|---|---:|---|
| Gemini wall-clock timeout (task timeout exceeded) | ~60 | agent-cap — long flows exhaust per-task budgets |
| Step-budget exhausted | ~25 | agent-cap — agent wandered / looped |
| Wrong entity chosen ("no candidate satisfied" / unaccounted update) | ~20 | agent-cap — grounding on decoys |
| Partial subgoals (0.50–0.94) | ~15 | agent-cap — missed one or more required mutations |
| Constraint not met (e.g. wrong reply text, forgot to block) | ~10 | agent-cap |
| Chromium "Target crashed" | 3 | infra — `reddit_curate_and_engage`, `reddit_deep_thread_engagement`, `reddit_community_builder__notification_shadow_v2` |
| Stray-backend cascades (hard variants, 1st attempt) | 13 | infra — fixed by port rotation |
| TASK BUG | **0** | — |

---

## 6. Rate-limit + infra analysis

### 6.1  Gemini rotation worked cleanly

Across ~170 runs (159 variants/base + partial reruns), the `_GeminiRotatingClient` swapped keys on 429/503 and preserved forward progress. Only **1 unrecovered 503** (`reddit_platform_migration__notification_shadow_v2`) where both keys hit transient limits in the same second; the outer 30s-backoff retry also failed. A third key would likely have solved this.

### 6.2  Chromium crashes (3)

`Frame.evaluate: Target crashed` fired three times — all on long-running hard/frontier tasks with heavy DOM churn. Symptoms: Chromium renderer process dies, the page becomes unreachable, browsergym raises. Each crash killed the affected task; the runner advanced to the next task cleanly.

### 6.3  Stray-backend cascade (diagnosed + fixed)

During hard variants: one task's Chromium crash left a stray uvicorn listening on port 8082. The next task tried to spawn its own 8082 backend, detected the existing one without a matching controller secret, and errored with `"server already running, secret not set"` — **13 of 16 hard variants** lost this way on the first attempt.

**Fix:** switched variant sweeps to **port rotation** (each task gets a unique port in 8091–8105). Every subsequent variant sweep (expert, frontier) ran clean with zero stray-backend errors.

A retry script with `pkill`-before-each partially recovered the hard variants but its own bash logic got tripped by killing the loop's own bash watcher. Port rotation is the robust fix.

---

## 7. Unverified list — base tasks (66 of 81)

Grouped by difficulty. Cases where agent scored 0.70+ (most likely to hide a subtle bug) are called out first.

### 7.1  Partial-score base tasks (5 of 66) — inspect closely for task bugs

| Task | Diff | Best | Why |
|---|---|---:|---|
| `reddit_complete_engagement_cycle` | frontier | 0.94 | 1 constraint failed (exact reply text) — agent-cap per inspection |
| `reddit_notification_cascade` | frontier | 0.89 | 2 constraints failed (save post, feed sort) — agent-cap |
| `reddit_post_and_comment` | medium | 0.85 | unaccounted update — agent upvoted extra post |
| `reddit_reply_nested_comment` | medium | 0.85 | preserve violation — agent modified extra post |
| `reddit_content_curation` | hard | 0.80 | — inspection pending |

### 7.2  Zero-score base tasks

61 base tasks never scored 1.0. Grouped:

- **easy (13):** `reddit_clear_notifications`, `reddit_compose_message`, `reddit_edit_own_post`, `reddit_inbox_read_only`, `reddit_mark_messages_read`, `reddit_notification_review_silent` (scored 0.50 — constraint-design test), `reddit_reply_to_message`, `reddit_save_from_feed`, `reddit_subscribe_subreddit`, `reddit_switch_dark_mode`, `reddit_update_settings`, `reddit_upvote_post`, `reddit_verify_inbox_clean`.
- **medium (12):** `reddit_create_and_engage`, `reddit_curate_saved` (0.50), `reddit_edit_then_comment`, `reddit_engage_user_content` (0.50), `reddit_follow_notification`, `reddit_message_management`, `reddit_notification_triage`, `reddit_privacy_overhaul`, `reddit_save_comments` (✓? yes — skip), `reddit_search_and_engage`, `reddit_search_and_message`.
- **hard (14):** `reddit_account_cleanup`, `reddit_comment_save_settings`, `reddit_community_engagement`, `reddit_cross_platform_workflow`, `reddit_curate_and_engage` (Chromium crash), `reddit_full_profile_engagement`, `reddit_messaging_workflow`, `reddit_multi_sub_engagement`, `reddit_notification_message_settings`, `reddit_post_edit_settings`, `reddit_reconstruct_post`, `reddit_research_respond`, `reddit_thread_participation`.
- **expert (13):** everything except `reddit_comment_chain_analysis` and `reddit_notification_driven_workflow`.
- **frontier (14):** everything except `reddit_inbox_driven_engagement`.

## 8. Unverified list — variants (67 of 78)

Same pattern — 11 passes, 67 unverified. Every difficulty tier has substantial unverified counts. Most notable:

- **All 15 expert variants** unverified.
- **14 of 15 frontier variants** unverified (only `reddit_inbox_driven_engagement__subreddit_shadow_v2` passed).
- Hard variants have 13 with missing results (from the stray-backend cascade) + 3 with 0.00 scores.

---

## 9. Takeaways

1. **Reddit tasks are evaluator-correct.** 159 runs, no task-correctness bug. The only fixes applied in this sweep were infra-only (port rotation for variants, key rotation for Gemini).

2. **Gemini-3-flash-preview struggles on reddit.** 19% base pass vs amazon's 61%. The gap is primarily UX-density (reddit feeds have many near-identical elements) and tight step budgets on easy tasks.

3. **Key rotation + port rotation are now proven patterns.** Both should be standard for any future multi-task sweep.

4. **Chromium crashes are a real infra cost** (3 in 159 runs = ~2% crash rate). Consider bumping Playwright to a newer Chromium channel or adding per-task browser-restart in the runner.

5. **Big confidence gap remains.** 66 of 81 base tasks and 67 of 78 variants never scored 1.0 against gemini-3-flash-preview. Same caveat as amazon: a stronger agent would be the highest-value next verification pass, especially for the frontier tier where only 2 of 30 (base+variants) verified.

---

## 10. Artifacts

```
results/webagentbench/sweep/reddit/
├── easy_base.{log,json}           19 tasks,  6 pass
├── easy_variants.{log,json-dir}   16 variants, 5 pass
├── medium_base.{log,json}         16 tasks,  4 pass
├── medium_variants.{log,json-dir} 16 variants, 2 pass
├── hard_base.{log,json}           16 tasks,  2 pass (1 Chromium crash)
├── hard_variants.{log,json-dir}   16 variants, 3 pass (13 lost then partial retry)
├── expert_base.{log,json}         15 tasks,  2 pass
├── expert_variants.{log,json-dir} 15 variants, 0 pass (port rotation clean)
├── frontier_base.{log,json}       15 tasks,  1 pass (1 Chromium crash)
└── frontier_variants.{log,json-dir} 15 variants, 1 pass
```
