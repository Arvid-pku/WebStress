# Human-Eval Bug Fix Plan

_Plan tracking every task-condition that surfaced during the human-eval pass — both attempts that failed and forms that annotators submitted. Each entry is cross-referenced against git history (non-chore commits since 2026-04-25) to mark what's been touched in a fix commit._

---

## 📋 Session log — 2026-05-22

This session moved through three waves of fixes. Numbers reflect status at end of session.

### Wave 1 — recording-session bug fixes (real-time, during Michael's recording)

These were fixed live while Michael was recording so he could continue. All verified end-to-end in the browser.

- `booking_curate_saved_list` (intervention) — two saved lists named "Summer 2026 Ideas" because the shared seeder created one ([`seeders/booking.py:610`](../backend/seeders/booking.py#L610)) and the task seed builder created another with the same name. Renamed task's list to "Summer 2026 Shortlist" in [`booking_curate_saved_list.yaml`](../tasks/booking/booking_curate_saved_list.yaml) + same fix in [`booking_frontier_cancel_and_reorganize.yaml`](../tasks/booking/booking_frontier_cancel_and_reorganize.yaml).
- `pp_update_phone` (intervention) — was wrongly labelled ⚠️ PARTIAL by the auto-classifier. The frontend stale-profile guard already added in commit `cd3a46cf` actually addresses the bug; my filter only looked at task YAML / variant commits, not SPA changes. Re-verified end-to-end → 1.00 PASS, reclassified to ✅ FIXED.

### Wave 2 — sweep through every ❌ OPEN (6 reclassified-from-FEEDBACK + 1 original)

Each had clarity≤4 from the annotator and was either a real bug or an instruction/eval mismatch.

| Task | Root cause | Fix |
|---|---|---|
| `lms_minimum_final_score` (intv) | (a) force-impossible block in grade_book set victim grades to **1%** → weighted score 0.96% looked like broken data. (b) `final_exam_assignment_id` picked iteration-first not_submitted final, often a non-target course. | 1% → 25%; prefer target_course_id's final + unconditional reset to not_submitted. ([_seed_builders_lms.py](../tasks/_seed_builders_lms.py)) Verified all seeds 41–99: drop-CS101 → 1.00. |
| `gmail_update_contact` (intv) | Variant `silent_fail` `response_body` hardcoded `name: "—" / email: "—@example.com"`. Middleware also leaked raw `{request.X}` text when client omitted a field. | Variant uses `{request.X}` echoes ([variant](../injector/variants/gmail_update_contact__contacts_retry.yaml)). Middleware now falls back to `null`/`""` for unresolved placeholders ([middleware.py](../injector/middleware.py)). |
| `reddit_create_text_post` (intv) | Same pattern — variant `silent_fail` body hardcoded blanks → fake post page rendered with empty subreddit name. | Variant uses `{request.X}` echoes ([variant](../injector/variants/reddit_create_text_post__post_retry.yaml)) + Submit.tsx falls back `author_name` to `profile.username` ([Submit.tsx](../environments/reddit/src/pages/Submit.tsx)). |
| `rh_sell_loser_buy_winner` (clean) | Eval check `quantity: {any: true}` — any buy passed even with 1 share. Instruction says "buy as many as proceeds allow". | New high-severity constraint: `bought_qty ≥ floor(proceeds / best_price) - 1`. ([task yaml](../tasks/robinhood/rh_sell_loser_buy_winner.yaml)) |
| `amazon_deal_hunter` (clean) | Instruction forced cart step; evaluator didn't require it (Buy Now also passed). | Reworded instruction: "purchase it (either via Buy Now or by adding to cart and checking out)". |
| `amazon_price_comparison` (clean) | Instruction said "Compare at least 3 products"; eval only checked the final order. | Dropped the "compare 3" prescription; goal unchanged. |
| `pp_pre_surgery_clearance` (intv, AMBIG) | Instruction said "pre-operative lab appointment" but provider directory had no lab/phlebotomy specialty — user had to guess. | Added `phlebotomy` specialty + Laboratory department ([_seed_builders_patient_portal.py](../tasks/_seed_builders_patient_portal.py)), added to task's provider_directory, tightened lab predicate to `provider_id in target['lab_provider_ids']`, made phlebotomy bypass referral in [backend route](../backend/routes/patient_portal.py). Verified happy/sad paths. |

### Wave 3 — variant strength audit (started with rh "didn't feel intervention")

| Task | Root cause | Fix |
|---|---|---|
| `rh_options_roll_strategy` (intv) + 5 sibling options variants | Handler `_rh_add_confusing_positions` only created stock `Position` — `option_type`/`strike`/`expiration` fields were **silently dropped**. All 6 options-confusion variants spun up **zero observable positions**. Also: every variant had hardcoded `expiration: "2025-..."` (now in the past, would be filtered even if handler worked). | Added options branch `_rh_add_confusing_options_position` ([seed.py](../injector/seed.py)) that creates `OptionsContract` + `OptionsPosition`, with relative `expiration_days` offsets. Refuses to inject already-expired contracts (authoring-bug guard). Rewrote 6 variant YAMLs to use `expiration_days`. **71/71 RH tasks still materialize**; variants now inject 4–14 options positions each. |
| `rh_tax_optimization` (intv) | Variant noise orders + alerts landed on `INTC/BA/NFLX/META`, but the seed picks losers from elsewhere (e.g. `GME/HON/MRK` for seed 42). Noise was technically there but invisible — agent never inspects those symbols during loss-harvesting. | Added `symbols_from_target: <key>` + `alert_template`/`below_pct` modes to `_rh_add_noise_orders` and `_rh_add_misleading_alert`. Variant now uses `symbols_from_target: loss_symbols` so noise lands on the actual losers. Verified happy (sell HON+MRK) → 1.00; sad (sell all incl wash-sale GME) → 0.40. |

### Wave 4 — finish "didn't feel intervention" sweep + dead-code purge

| Task | Root cause | Fix |
|---|---|---|
| `gmail_sensitive_hr_routing` (intv) | `scramble_aria` is **dead code** (legacy [client.py](../injector/client.py) is DEPRECATED — current runtime is [BenchmarkToolbar.tsx](../environments/shared/src/components/BenchmarkToolbar.tsx)); decoys self-labeling ("(draft)", "template") on wrong `@thornton.com` domain → no real grounding pressure. | Replaced `scramble_aria` with `false_banner` (misleading "loop in engineering leads" policy reminder), rewrote 8 decoys with `@hr.meridian.com` domain match including one with **identical from address** as real PTO email. Happy=1.0 / Sad=0.0. ([variant](../injector/variants/gmail_sensitive_hr_routing__grounding.yaml)) |
| **6 sibling `scramble_aria` variants** (3 booking + 3 gmail) | Same dead-code pattern. Gmail trio additionally had domain mismatches + self-labeling decoy bodies. | Batch-purged `scramble_aria` from all 6, added `false_banner` (booking) or rewrote decoys (gmail). Variants: `booking_decoy_hotel_selection`, `booking_expert_family_vacation`, `booking_frontier_everything`, `gmail_client_handoff`, `gmail_triage_with_interrupts`, `gmail_multi_recipient_policy`. |
| `gmail_team_roster_sync` (intv) | `topical_subjects` were empty boilerplate body — agent ignores. No actual state-tracking pressure. | Replaced with 4 surgical **reversal decoys** (each targets one evaluator check): "skip Anika" / "Congrats Wei!" wrong promotion / "Tom Reeves retained" / "Marcus postponed". Kept `scramble_timestamps`. Happy=1.0/7-checks. 4 sad paths each fail their respective check (0.80–0.86). ([variant](../injector/variants/gmail_team_roster_sync__state_tracking.yaml)) |
| `reddit_selective_vote_save` (intv) | Single lookalike subreddit + crosspost. 3 of 4 task subreddits had **zero** per-step grounding pressure. | Per-step lookalike posts in each of 4 target subreddits + 3 lookalike subreddits (worldnewsofficial / techinsider / scienceupdates) with exact-title crossposts. Forces (subreddit, exact title) tuple grounding. Happy=1.0; 3 sad paths each 0.833 fail. ([variant](../injector/variants/reddit_selective_vote_save__subreddit_shadow_v2.yaml)) |
| `lms_complete_all_announcements` (intv) | 2 self-disclosing decoys ("Archived...should not be...") + `stale_data once`. Trivial to dismiss. | Replaced with **12 plausible read decoys** (3 per course) with realistic policy/admin bodies + misleading "only Urgent require action" banner. Happy=1.0/8-checks; sad (touch a decoy)=0.85 with `-0.15 already-read` penalty. |
| `lms_complete_prerequisite_module` (intv) | Sole injection was `scramble_timestamps` — Module rows have no visible timestamp ordering. Zero UI change. | Deleted scramble. Added 2 "Module 2: ..." lookalikes (Practice Set available / Supplementary Readings locked) + Module 1.5 noise + misleading "Practice Set is canonical prerequisite" banner. Happy=1.0; sad (complete wrong "Module 2")=0.0 with double fail. |
| `pp_cancel_appointment` (intv) | Variant was a phishing message in `/messages` — but task is "cancel appointment", agent never opens messages. Zero intervention surface on the actual workflow page. | Replaced with **3 appointment lookalikes on `/appointments`** (same-provider/different-date × 2 + same-window/different-provider × 1) + misleading "bulk cancel" banner. ([Subagent A](../injector/variants/pp_cancel_appointment__phishing_message.yaml)) |
| `pp_update_default_pharmacy` (intv) | `stale_data once` vanished on agent's second fetch. | Replaced with persistent `add_confusing_decoys`: 3 Walgreens-brand lookalike pharmacies (`#09833`, `Express #2241`, `Mail Pharmacy`) + misleading "Mail Pharmacy = lowest fees" banner. ([Subagent A](../injector/variants/pp_update_default_pharmacy__pharmacies_list_stale_v1.yaml)) |
| `gmail_update_contact` re-verify | — | Wave 2 fix verified correct: happy=1.0, middleware `{request.X}` echoes work for full & partial payloads. |

### Wave 5 — PP environment expansion (B-path) + frontier task uplift

Tianchen flagged 3 PP tasks as "too easy for frontier" — root cause is **PP environment functionality too thin**, not just variant strength. Solved by adding genuine workflow surface:

| Change | Impact |
|---|---|
| **Appointment confirmation workflow**: new fields `requires_confirmation`, `confirmation_state` (`not_required` / `pending` / `confirmed`), `confirmed_at` on [Appointment model](../backend/models/patient_portal.py); new endpoint `POST /appointments/{id}/confirm`; SPA Appointments page shows "Awaiting confirmation" badge + Confirm button; appointment_history builder takes `requires_confirmation_specialties` param. **Backward compatible** — default behavior unchanged. | Frontier tasks can now require two-step `schedule → confirm` workflow for specialist visits. |
| **Cancellation reason capture**: new field `Appointment.cancellation_reason`; cancel endpoint accepts optional `reason` body; SPA prompts user for reason on cancel click. | `pp_cancel_appointment` upgraded: instruction asks for reason, eval `changes.cancellation_reason` requires non-empty. Happy=1.0 / Sad (no reason)=0.0. |
| **`PatientPortalState.auto_confirm_specialties`** + create_appointment endpoint auto-sets `requires_confirmation=True` for matching specialties; `patient_profile` builder accepts opt-in `auto_confirm_specialties` param. | `pp_post_accident_coordination` upgraded: ortho appt must be confirmed. Eval `confirmation_state: {eq: confirmed}` on create[0]. Happy (3 ops + confirm)=1.0 / Sad (forgot confirm)=0.67. Task is now genuinely 4-step. |
| **PP `_add_confusing_decoys` `appointment` dtype handler** ([seed.py](../injector/seed.py) by Subagent A) — entire class of PP appointment decoy specs were previously silently dropped. Same systemic class of authoring/handler gap as Wave 3 RH options bug. | All current/future PP variants can now inject `type: appointment` decoys with `days_ahead`+`hour` relative offsets. |
| **pp_insurance_plan_change uplift** — instruction adds "Transfer every active prescription to the new mail-order pharmacy"; eval adds bijection `update[]` over `target['active_rx_ids']` checking `pharmacy_id == mail_order_pharmacy_id`. Builder forced via `active_at_default_only: true` so transfers are always real diffs (not no-ops). | Happy (3 ops + 5 transfers) = 1.000 / Sad (skip transfers) = 0.750. Task is now genuinely 8-step (1 insurance + 2 pharmacy flips + 5 transfers). |
| **pp_preventive_care_compliance uplift** — instruction adds "AND confirm the appointment after scheduling"; eval adds `confirmation_state in ("confirmed", "not_required")` predicate on the bijection. patient_profile opts in `auto_confirm_specialties: [cardiology, radiology, dermatology]`. | Happy (2 screenings × schedule + confirm) = 1.000 / Sad (forget confirm) = 0.000. Each overdue screening now requires a 2-step workflow. |

### Other infrastructure changes shipped this session

- **YAML hot-reload via mtime cache** ([_registry.py](../tasks/_registry.py)) — replaced `@lru_cache` with mtime-checked module-level cache so task YAML edits reflect on the next session without process restart. Cold ~7.6s, warm ~8ms.
- **Launcher `?env=` URL param** ([app.py](../app.py)) — query param now overrides localStorage, so deep links open the correct env tab.
- **Booking save-to-list toast** ([PropertyDetail.tsx](../environments/booking/src/pages/PropertyDetail.tsx)) — adding a property to a list now shows a toast instead of silently closing the dropdown.
- **Booking saved-lists hover/expanded styling** ([SavedLists.tsx](../environments/booking/src/pages/SavedLists.tsx) + [booking.css](../environments/booking/src/booking.css)) — list cards have a hover effect + grey background when expanded so the click target is discoverable.
- **Middleware placeholder fallback** ([middleware.py](../injector/middleware.py)) — unresolved `{request.X}` no longer leaks raw token text into UI; resolves to `null` for whole-string positions or `""` inline.

---

## 🎯 Remaining work — variant strength + difficulty calibration

**Status after Wave 4 + Wave 5**: all 8 "didn't feel intervention" items AND all 3 "too easy for frontier" PP items are FIXED ✅. PP env expansion (B-path) shipped + applied:
- Appointment confirmation workflow (new fields + endpoint + UI + builder opt-in)
- Cancellation reason capture (new field + endpoint param + UI prompt)
- `auto_confirm_specialties` on PatientPortalState (auto-set requires_confirmation on create_appointment)
- Subagent-discovered: PP `_add_confusing_decoys` `appointment` dtype handler

5 PP tasks uplifted: pp_cancel_appointment (reason), pp_update_default_pharmacy (lookalikes), pp_post_accident_coordination (ortho confirm), pp_insurance_plan_change (transfer), pp_preventive_care_compliance (specialist confirm).

### A. "Didn't feel any intervention" — 8 remaining tasks (HISTORICAL — all FIXED in Wave 4)

These need per-task variant audits (read variant YAML → trace through which handler runs → verify it actually creates visible state changes on the symbols the agent looks at). The two RH ones we already fixed (`rh_options_roll_strategy`, `rh_tax_optimization`) revealed systemic handler bugs, so this is high-leverage work — expect more shared infra fixes.

| Task | Annotator note | Hypothesis to verify |
|---|---|---|
| `gmail_sensitive_hr_routing` (intv) | "Hmmm, didn't really feel any intervention." (Michael, clarity=4) | grounding variant — check if injected decoys actually flow into inbox; cross-check against `gmail_briefing_under_fire` pattern Tianchen fixed earlier (decoys had `labels: []` and didn't render). |
| `gmail_team_roster_sync` (intv) | "Didn't feel any intervention. Also, this task didn't really check if I check the email or not." (Tianchen, clarity=4) | Two issues: (1) variant strength, (2) trajectory not enforced. Probably needs both a variant audit AND an evaluator check that the agent visited the relevant emails. |
| `lms_complete_all_announcements` (intv) | "I didn't feel any intervention." (Tianchen, clarity=5) | announcement-clutter variant — does the noise actually appear in the announcements view, or does it get filtered (e.g. by `is_read=true` on decoys)? |
| `lms_complete_prerequisite_module` (intv) | "Again didn't feel any intervention, not sure if there actually is an intervention." (Tianchen, clarity=4) | Verify variant injection lands on the right module / course. |
| `pp_cancel_appointment` (intv) | "Didn't feel any intervention." (Tianchen, clarity=5) | Likely a one-shot stale fetch — same family as `pp_update_phone`'s pre-fix issue. Check if user actually hits the stale endpoint. |
| `pp_update_default_pharmacy` (intv) | "Didn't feel any intervention" (Tianchen, clarity=4) | Similar — verify what the variant actually does and whether it affects the pharmacy flow user follows. |
| `reddit_selective_vote_save` (intv) | "Didn't feel any intervention." (Michael, clarity=4) | Audit the variant; suspect same "noise on wrong symbols / posts" pattern as RH. |
| `gmail_update_contact` (intv) | _(already fixed in Wave 2, but original symptom included weak intervention feel — re-verify after the silent-fail fix lands)_ | — |

### B. "Too easy for frontier task" — 3 tasks (all Patient Portal)

These need genuine difficulty calibration — adding constraints, tightening invariants, or layering additional steps. Higher risk than variant audits because it changes task semantics.

| Task | Annotator note |
|---|---|
| `pp_insurance_plan_change` (clean) | "A bit too easy for a frontier task" (Tianchen, clarity=5) |
| `pp_post_accident_coordination` (clean) | "A bit too easy for an frontier task" (Tianchen, clarity=5) |
| `pp_preventive_care_compliance` (clean) | "A bit too easy for an frontier task." (Tianchen, clarity=4) |

Approach when picking these up: load the task YAML, identify the canonical_diff steps, see if there's room to add a verification/constraint that mirrors a realistic "could-go-wrong" failure mode without breaking the existing happy path.

---

## Summary

- **Total entries:** 99 unique (base_task_id × condition)
- **With attempt failures:** 45
- **With form submissions:** 89
- **Actionable concerns (failed OR bug/ambig/alt flag):** 60

### Status counts

| Status | Meaning | Count |
|---|---|---|
| ✅ **FIXED** | A non-chore fix commit since 2026-04-25 touched the task YAML, variant, or env SPA — verify the diff addresses the reported issue. | 68 |
| ⚠️ **PARTIAL** | A fix commit touched the env (UI/seeder/routes) but not the specific task. May or may not address this issue. | 0 |
| ❌ **OPEN** | No fix commit since 2026-04-25 touched any related file. Needs attention. | 0 |
| ➖ **FEEDBACK** | Annotator submitted a form but did NOT report a bug or ambiguity. Recorded for completeness — no fix needed. | 31 |

### Per-env breakdown

| env | FIXED | PARTIAL | OPEN | FEEDBACK |
|---|---|---|---|---|
| amazon | 8 | 0 | 0 | 4 |
| booking | 4 | 0 | 0 | 1 |
| gmail | 13 | 0 | 0 | 6 |
| lms | 16 | 0 | 0 | 5 |
| patient_portal | 4 | 0 | 0 | 9 |
| reddit | 10 | 0 | 0 | 3 |
| robinhood | 13 | 0 | 0 | 3 |

### Recommended action order

1. **OPEN** entries — no commit addresses these. Confirm the bug and patch.
2. **PARTIAL** entries — a related commit landed but didn't target this task. Verify the issue is actually resolved.
3. **FIXED** entries — spot-check that the linked commit actually addresses the annotator's specific complaint. Some commits may be unrelated edits on the same file.
4. **FEEDBACK** — no action; preserved for traceability.

> ⚠️ FIXED ≠ verified. A commit listed here only means the relevant file was modified; you still need to read the diff to confirm it addresses the specific complaint.

---

## amazon  (12 entries)

### ✅ FIXED  `amazon_browse_category` (intervention)
- **Failures:** 2 annotator(s): D, Daisy
- **D** [BUG] clarity=3: when i clicked add to cart, the item is not actually added to the cart. i have to click buy now to make the item appear in the cart. but the evaluator said it was wrong?
- **Specific fix commits** (task YAML or variant):
  - `7aeff69e` fix(webagentbench): harden Amazon and Reddit intervention variants
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `amazon_cancel_order` (intervention)
- **Failures:** 1 annotator(s): D
- **Specific fix commits** (task YAML or variant):
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `amazon_cross_category_value_hunt` (intervention)
- **Failures:** 1 annotator(s): roycecy
- **Specific fix commits** (task YAML or variant):
  - `7aeff69e` fix(webagentbench): harden Amazon and Reddit intervention variants

### ✅ FIXED  `amazon_order_audit_correction` (intervention)
- **Failures:** 1 annotator(s): Tianchen
- **Tianchen** [BUG] clarity=4: No cancel button.l
- **Specific fix commits** (task YAML or variant):
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `amazon_write_review` (intervention)
- **Failures:** 1 annotator(s): Tianchen
- **Tianchen** [BUG/AMBIG/ALT] clarity=3: Didn't expect I need to write more than 2 words.
- **Specific fix commits** (task YAML or variant):
  - `cd3a46cf` fix(human-recording): repair 5 task failures surfaced by Tianchen's traces
  - `f93bb9c7` fix(webagentbench): repair degradation variant setups
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `amazon_verify_order_ok` (intervention)
- **Failures:** none
- **Tianchen** [BUG/AMBIG/ALT] clarity=5: I don't need to do anything to finish this task.
- **Specific fix commits** (task YAML or variant):
  - `a7ba34ec` fix 0503: according to the comments from xunjian and weili
  - `7aeff69e` fix(webagentbench): harden Amazon and Reddit intervention variants
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ➖ FEEDBACK  `amazon_buy_highest_rated` (clean)
- **Failures:** none
- **Tianchen** clarity=5: This is a nice one among all the bad ones, perhaps this is one of the few tasks that can be demonstrated.
- **Specific fix commits** (task YAML or variant):
  - `a7ba34ec` fix 0503: according to the comments from xunjian and weili
  - `7aeff69e` fix(webagentbench): harden Amazon and Reddit intervention variants
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ➖ FEEDBACK  `amazon_cancel_order` (clean)
- **Failures:** none
- **Tianchen** clarity=4: _(no comment)_
- **Specific fix commits** (task YAML or variant):
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ➖ FEEDBACK  `amazon_cascading_return_replace` (intervention)
- **Failures:** none
- **Tianchen** clarity=5: _(no comment)_
- **Specific fix commits** (task YAML or variant):
  - `7aeff69e` fix(webagentbench): harden Amazon and Reddit intervention variants
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ➖ FEEDBACK  `amazon_compare_and_buy_cheapest` (clean)
- **Failures:** none
- **Tianchen** clarity=5: ez
- **Specific fix commits** (task YAML or variant):
  - `a7ba34ec` fix 0503: according to the comments from xunjian and weili
  - `7aeff69e` fix(webagentbench): harden Amazon and Reddit intervention variants

### ✅ FIXED  `amazon_deal_hunter` (clean)
- **Failures:** none
- **Tianchen** clarity=4: Actually no need to add to cart, can purchase directly.
- **Fix** (2026-05-22): the instruction forced "Add it to your cart and complete checkout" but the evaluator only checks the final order + that `cart_items` is preserved (empty after checkout is fine, never-added is also fine). The cart step wasn't load-bearing, so a Buy-Now path also passed and the instruction read as misleading. Reworded to "purchase it (either via Buy Now or by adding to cart and checking out)" in [amazon_deal_hunter.yaml](../tasks/amazon/amazon_deal_hunter.yaml) — matches what the evaluator actually requires.
- **Specific fix commits** (task YAML or variant):
  - `7aeff69e` fix(webagentbench): harden Amazon and Reddit intervention variants
  - `f93bb9c7` fix(webagentbench): repair degradation variant setups

### ✅ FIXED  `amazon_price_comparison` (clean)
- **Failures:** none
- **Tianchen** clarity=4: Kinda good, but I actually don't need to compare three, I just need to click into one and buy, so instruction is not actually really clear.
- **Fix** (2026-05-22): instruction said "Compare at least 3 products" but the evaluator only checks the final order's product is the highest-rated in the $50-$100 / target-category band — there's no trajectory check that the agent visited 3 product pages. Reworded in [amazon_price_comparison.yaml](../tasks/amazon/amazon_price_comparison.yaml) to drop the "compare at least 3" prescription; goal is unchanged ("highest-rated in $50-$100 band"), just no longer reads as if mid-task page visits were load-bearing.
- **Specific fix commits** (task YAML or variant):
  - `a7ba34ec` fix 0503: according to the comments from xunjian and weili
  - `7aeff69e` fix(webagentbench): harden Amazon and Reddit intervention variants
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

## booking  (5 entries)

### ✅ FIXED  `booking_curate_saved_list` (intervention)
- **Failures:** none
- **Michael** [BUG/AMBIG] clarity=3: I can see two 2026 Summer Ideas when I try to save to list, and this might cause confusion.
- **Fix** (2026-05-22): renamed task-created list from `Summer 2026 Ideas` → `Summer 2026 Shortlist` in [booking_curate_saved_list.yaml:92](../tasks/booking/booking_curate_saved_list.yaml#L92) so it no longer collides with the shared seeder's default list. Also fixed the same latent name-collision in [booking_frontier_cancel_and_reorganize.yaml:357](../tasks/booking/booking_frontier_cancel_and_reorganize.yaml#L357). Verified end-to-end via browser-use, score 1.00 PASSED.

### ✅ FIXED  `booking_expert_settings_and_security` (intervention)
- **Failures:** 1 annotator(s): Michael
- **Michael** [BUG/AMBIG] clarity=1: 1. There are two places for currency modification:  1. One in the setting section  2. The other one in the preferred section and the preferred currency seems to match the instruction more, while the evaluator checks only the currency field in the settings section, which is, I think, a misdefined behavior of the evaluator. Also, need to make sure if the evaluator checks the phone number of the reservation.
- **Specific fix commits** (task YAML or variant):
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `booking_frontier_cancel_and_reorganize` (clean)
- **Failures:** 1 annotator(s): roycecy
- **Specific fix commits** (task YAML or variant):
  - `a7ba34ec` fix 0503: according to the comments from xunjian and weili
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives
  - `97fab0c7` audit: fix eval Update-filter scope, lms attempt_count, booking rebook whitelist

### ✅ FIXED  `booking_review_completed_stay` (intervention)
- **Failures:** 1 annotator(s): KL
- **Specific fix commits** (task YAML or variant):
  - `f93bb9c7` fix(webagentbench): repair degradation variant setups
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ➖ FEEDBACK  `booking_frontier_loyalty_maximizer` (clean)
- **Failures:** none
- **Michael** clarity=5: _(no comment)_
- **Specific fix commits** (task YAML or variant):
  - `a7ba34ec` fix 0503: according to the comments from xunjian and weili
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives
  - `07c46cc1` fix(booking): widen preferred_currency constraint to also accept state.settings.currency

## gmail  (19 entries)

### ✅ FIXED  `gmail_delegation_handoff` (intervention)
- **Failures:** 2 annotator(s): KW, Michael
- **Specific fix commits** (task YAML or variant):
  - `a7ba34ec` fix 0503: according to the comments from xunjian and weili
  - `bca16c8c` feat(injector): upgrade Gmail+RH intervention strength
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `gmail_annual_contact_review` (intervention)
- **Failures:** 1 annotator(s): Michael
- **Michael** [BUG] clarity=4: This one got a bug, among 26 contacts, actually more than the evaluator check match the condition. So a bug.
- **Specific fix commits** (task YAML or variant):
  - `a7ba34ec` fix 0503: according to the comments from xunjian and weili
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `gmail_briefing_under_fire` (clean)
- **Failures:** 1 annotator(s): Michael
- **Michael** [BUG] clarity=2: There's a bug, I cannot see the email unless I search that. So obviously a bug.
- **Specific fix commits** (task YAML or variant):
  - `a7ba34ec` fix 0503: according to the comments from xunjian and weili
  - `bca16c8c` feat(injector): upgrade Gmail+RH intervention strength

### ✅ FIXED  `gmail_cross_team_filter_audit` (clean)
- **Failures:** 1 annotator(s): Michael
- **Michael** [BUG] clarity=4: A but on couldn't label their own email.
- **Specific fix commits** (task YAML or variant):
  - `a7ba34ec` fix 0503: according to the comments from xunjian and weili
  - `bca16c8c` feat(injector): upgrade Gmail+RH intervention strength
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `gmail_cross_team_filter_audit` (intervention)
- **Failures:** 1 annotator(s): Tianchen
- **Tianchen** [BUG] clarity=1: Gugs with filter, and label.
- **Specific fix commits** (task YAML or variant):
  - `a7ba34ec` fix 0503: according to the comments from xunjian and weili
  - `bca16c8c` feat(injector): upgrade Gmail+RH intervention strength
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `gmail_filter_overhaul` (intervention)
- **Failures:** 1 annotator(s): Tianchen
- **Tianchen** [BUG] clarity=3: Filter got some bugs. When I delete, it would delete more than one. Also, I tried many times, and couldn't make it correct. Some settings are just doesn't make any sense. Like you have to add an @ in front of the email link.
- **Specific fix commits** (task YAML or variant):
  - `a7ba34ec` fix 0503: according to the comments from xunjian and weili

### ✅ FIXED  `gmail_invoice_dispute_reversal` (intervention)
- **Failures:** 1 annotator(s): Michael
- **Michael** [BUG] clarity=4: There's a bug here. Because when I see the instruction, I already know 7782 can pass the 10000 limit, but the evaluation will check if I rejected or not at first. So it doesn't really make any sense.
- **Specific fix commits** (task YAML or variant):
  - `a7ba34ec` fix 0503: according to the comments from xunjian and weili
  - `bca16c8c` feat(injector): upgrade Gmail+RH intervention strength
  - `f93bb9c7` fix(webagentbench): repair degradation variant setups
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives
  - `1daac1d3` fix(gmail): GM-1 narrow state.sent invariant filter to cold sends only

### ✅ FIXED  `gmail_multi_party_rsvp` (clean)
- **Failures:** 1 annotator(s): Michael
- **Michael** [BUG] clarity=4: There's a bug, when I star the latest email, the previous email will also be stared. Which makes the task not possible to be 1.0
- **Specific fix commits** (task YAML or variant):
  - `bca16c8c` feat(injector): upgrade Gmail+RH intervention strength

### ✅ FIXED  `gmail_team_transition_setup` (intervention)
- **Failures:** 1 annotator(s): Michael
- **Specific fix commits** (task YAML or variant):
  - `a7ba34ec` fix 0503: according to the comments from xunjian and weili
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `gmail_annual_vendor_review` (clean)
- **Failures:** none
- **Michael** [ALT] clarity=4: Actually the evaluator won't check if i labeled them or not.
- **Specific fix commits** (task YAML or variant):
  - `a7ba34ec` fix 0503: according to the comments from xunjian and weili
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `gmail_inbox_triage_protocol` (clean)
- **Failures:** none
- **Tianchen** [AMBIG] clarity=3: I didn't quite know which promotion to archive.
- **Specific fix commits** (task YAML or variant):
  - `bca16c8c` feat(injector): upgrade Gmail+RH intervention strength
  - `f93bb9c7` fix(webagentbench): repair degradation variant setups
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `gmail_schedule_recovery` (intervention)
- **Failures:** none
- **Tianchen** [BUG] clarity=None: The intervention didn't seem to fire — I didn't feel or notice any complication during this task. The recap_trap variant plants a fake 'Ops Recap Bot' email confidently restating an outdated meeting time, but it either wasn't visible enough or didn't conflict with the real thread in a way that affected my workflow. The intervention may need to be strengthened (e.g. recap email pinned at top, more authoritative-looking sender, or its content actually contradicting the correct answer in a way that's costly to ignore).
- **Specific fix commits** (task YAML or variant):
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ➖ FEEDBACK  `gmail_cross_functional_distribution` (clean)
- **Failures:** none
- **Tianchen** clarity=5: Pretty good actually. Instruction pretty clear, just a bit too long for human.
- **Specific fix commits** (task YAML or variant):
  - `bca16c8c` feat(injector): upgrade Gmail+RH intervention strength
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives
  - `1daac1d3` fix(gmail): GM-1 narrow state.sent invariant filter to cold sends only

### ➖ FEEDBACK  `gmail_inbox_triage_protocol` (intervention)
- **Failures:** none
- **Michael** clarity=4: _(no comment)_
- **Specific fix commits** (task YAML or variant):
  - `bca16c8c` feat(injector): upgrade Gmail+RH intervention strength
  - `f93bb9c7` fix(webagentbench): repair degradation variant setups
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ➖ FEEDBACK  `gmail_schedule_recovery` (clean)
- **Failures:** none
- **Michael** clarity=3: Too many suggetsions that reveals potential misleading factors...
- **Specific fix commits** (task YAML or variant):
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ➖ FEEDBACK  `gmail_sensitive_hr_routing` (clean)
- **Failures:** none
- **Tianchen** clarity=5: All four tasks are at very begining.
- **Specific fix commits** (task YAML or variant):
  - `a7ba34ec` fix 0503: according to the comments from xunjian and weili
  - `bca16c8c` feat(injector): upgrade Gmail+RH intervention strength
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ➖ FEEDBACK  `gmail_sensitive_hr_routing` (intervention)
- **Failures:** none
- **Michael** clarity=4: Hmmm, didn't really feel any intervention.
- **Specific fix commits** (task YAML or variant):
  - `a7ba34ec` fix 0503: according to the comments from xunjian and weili
  - `bca16c8c` feat(injector): upgrade Gmail+RH intervention strength
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ➖ FEEDBACK  `gmail_team_roster_sync` (intervention)
- **Failures:** none
- **Tianchen** clarity=4: Didn't feel any intervention. Also, this task didn't really check if I check the email or not. So some instruction are not necessary.
- **Specific fix commits** (task YAML or variant):
  - `a7ba34ec` fix 0503: according to the comments from xunjian and weili
  - `bca16c8c` feat(injector): upgrade Gmail+RH intervention strength

### ✅ FIXED  `gmail_update_contact` (intervention)
- **Failures:** none
- **Michael** clarity=3: When updated, the original contact (alice's contact) shows a werid exmaple email. Need to be something proper or logical even if there's intervention that blocks this operation
- **Fix** (2026-05-22): two issues, both addressed:
  - Variant [gmail_update_contact__contacts_retry.yaml](../injector/variants/gmail_update_contact__contacts_retry.yaml) hardcoded `name: "—"` and `email: "—@example.com"` in the fake silent-fail response, so the UI replaced Alice's real name/email with em-dashes on the first (intentionally-failing) save. Switched to `{request.X}` placeholders so the fake response echoes the client's submitted fields — Alice keeps her real identity, only the agent-typed note appears "updated" (which is the verification trap the variant is meant to test).
  - Middleware `_render_request_template` ([middleware.py:148](../injector/middleware.py#L148)) previously left raw `{request.X}` tokens in the response when the client didn't send that field (e.g. empty company → field stripped by JSON). That surfaced literal `{request.company}` text in the UI. Now resolves to `null` (whole-string) or `""` (inline), so unset fields render as a dash like normal empty data.
  - End-to-end verified with browser-use: silent_fail attempts 1-2 echo Alice's real data + new note; server state unchanged; attempt 3 persists; evaluator 1.00 PASSED.
- **Specific fix commits** (task YAML or variant):
  - `bca16c8c` feat(injector): upgrade Gmail+RH intervention strength

## lms  (21 entries)

### ✅ FIXED  `lms_check_course_grade` (clean)
- **Failures:** 2 annotator(s): KL, Tianchen
- **KL** [AMBIG] clarity=3: "next" assignment seems ambiguous. you could interpret next as either the next one by due date or by how they are ordered in the list
- **Tianchen** [BUG] clarity=2: Did the job, didn't work. I think there's some error with the task. First, the 18% grade is a bit too much. It's too low and wouldn't really going to happen in real life.  Second, I submit the problem set 5, still failed.
- **Specific fix commits** (task YAML or variant):
  - `f13bbe9f` fix(lms): clarify assignment-type scope across 6 tasks (Phase A + B1)
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `lms_academic_probation_recovery` (clean)
- **Failures:** 1 annotator(s): Tianchen
- **Tianchen** [BUG] clarity=1: I still don't get if assignment contains exam or projects. Instruction very unclear. Terrible Environment. Unclear instructions.
- **Specific fix commits** (task YAML or variant):
  - `cd3a46cf` fix(human-recording): repair 5 task failures surfaced by Tianchen's traces
  - `f13bbe9f` fix(lms): clarify assignment-type scope across 6 tasks (Phase A + B1)
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `lms_academic_standing_optimization` (clean)
- **Failures:** 1 annotator(s): Tianchen
- **Tianchen** [BUG] clarity=1: Again, I don't know if project or exams counts in assignments.
- **Specific fix commits** (task YAML or variant):
  - `f13bbe9f` fix(lms): clarify assignment-type scope across 6 tasks (Phase A + B1)
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `lms_final_exam_prep_plan` (intervention)
- **Failures:** 1 annotator(s): Tianchen
- **Tianchen** [BUG] clarity=2: One final exam is already submitted. So I don't know if I should submit or not. Instruction not really clear. Also, I don't feel any intervention.
- **Specific fix commits** (task YAML or variant):
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `lms_gpa_impact_analysis` (clean)
- **Failures:** 1 annotator(s): Tianchen
- **Tianchen** [BUG] clarity=1: Saying project, but why would I have to submit a quiz to success? Instruction very unclear. Terrible environment and the instructon is very unclear.
- **Specific fix commits** (task YAML or variant):
  - `f13bbe9f` fix(lms): clarify assignment-type scope across 6 tasks (Phase A + B1)
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `lms_grade_appeal_preparation` (intervention)
- **Failures:** 1 annotator(s): Tianchen
- **Tianchen** [BUG] clarity=3: Didn't feel any intervention. Also, I posted the form, didn't work out.
- **Specific fix commits** (task YAML or variant):
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `lms_late_assignment_worth` (clean)
- **Failures:** 1 annotator(s): Tianchen
- **Tianchen** clarity=1: The score is always 0.80, it's not real at all. Like, submitting every assignment as late_submit.pdf? And just using an input box? Get out of here. Also, the instruction isn't clear about which one I should submit. For many assignment that's after the current date. Should I submit or not?
- **Specific fix commits** (task YAML or variant):
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `lms_multi_course_thresholds` (clean)
- **Failures:** 1 annotator(s): Tianchen
- **Tianchen** [BUG] clarity=1: Now quiz 2 counts in assignment, but not exams? Instruction very unclear, and drop course just doesn't make any sense.
- **Specific fix commits** (task YAML or variant):
  - `f13bbe9f` fix(lms): clarify assignment-type scope across 6 tasks (Phase A + B1)
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `lms_resubmit_after_feedback` (intervention)
- **Failures:** 1 annotator(s): Tianchen
- **Tianchen** [BUG] clarity=1: There's no flag, also, there's no assignment with feedback.
- **Specific fix commits** (task YAML or variant):
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `lms_submission_priority` (intervention)
- **Failures:** 1 annotator(s): Tianchen
- **Tianchen** [BUG] clarity=1: Instruction very unclear. I don't know what to do at all. And is project and exam counts in assignments?
- **Specific fix commits** (task YAML or variant):
  - `f13bbe9f` fix(lms): clarify assignment-type scope across 6 tasks (Phase A + B1)
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `lms_academic_probation_recovery` (intervention)
- **Failures:** none
- **KW** [BUG] clarity=2: The task says highest impact is defined by (course credits x category weight). This should be ECON101 Final Exam (course credits = 3, category weight = 0.35), which has a higher product than the MATH201 Midterm Exam (course credits = 4, category weight = 0.2).    But I think the task evaluator is bugged, since it implements the ranking as a tuple of (course credit, category weight) instead of a product.
- **Specific fix commits** (task YAML or variant):
  - `cd3a46cf` fix(human-recording): repair 5 task failures surfaced by Tianchen's traces
  - `f13bbe9f` fix(lms): clarify assignment-type scope across 6 tasks (Phase A + B1)
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `lms_compare_course_grades` (intervention)
- **Failures:** none
- **Tianchen** [BUG] clarity=4: Didn't feel intervention. Also, I think there's a bug. 0.96% grade? I think it's wrong.
- **Specific fix commits** (task YAML or variant):
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `lms_course_selection_next_semester` (intervention)
- **Failures:** none
- **Tianchen** [BUG] clarity=3: I don't think the instruction is very clear. Also, 1% for the grade? That needs to be fixed. Again, timeline needs to be modified to make it more clear.
- **Specific fix commits** (task YAML or variant):
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `lms_module_quiz_unlock` (intervention)
- **Failures:** none
- **Tianchen** [BUG] clarity=1: We didn't really even make the module! I don't even need to check if module 3 is accessable or not. I also didn't feel an intervention at all!
- **Specific fix commits** (task YAML or variant):
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `lms_view_late_policy` (clean)
- **Failures:** none
- **Tianchen** [BUG] clarity=4: It worked out, but in cold attmpt, I reached a bug tha submit failed. Might because I didn't check syllabus. But it should still be allowed, but minus some process points.
- **Specific fix commits** (task YAML or variant):
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ➖ FEEDBACK  `lms_complete_all_announcements` (intervention)
- **Failures:** none
- **Tianchen** clarity=5: I didn't feel any intervention.
- **Specific fix commits** (task YAML or variant):
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives
  - `e151a512` fix(lms): LMS-6 seed announcement-clutter decoys as is_read=true

### ➖ FEEDBACK  `lms_complete_prerequisite_module` (intervention)
- **Failures:** none
- **Tianchen** clarity=4: Again didn't feel any intervention, not sure if there actually is an intervention.
- **Specific fix commits** (task YAML or variant):
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `lms_minimum_final_score` (intervention)
- **Failures:** none
- **Tianchen** clarity=1: The score is 0.96%, there's a bug!!!! You won't get above 80% by any chance! This task is so bad! Also, I didn't feel any god damn intervention.
- **Fix** (2026-05-22): two root causes in [_seed_builders_lms.py](../tasks/_seed_builders_lms.py):
  - **Unrealistic 1% grades.** The force-impossible block (intended for `lms_multi_course_thresholds`) set the victim course's grades to 1% of points possible, producing a 0.96% weighted score that read as broken data. Raised to 25% — still leaves `needed > 100` for any sane weight distribution, but looks like a struggling student rather than a bug.
  - **`final_exam_assignment_id` could pick a non-target course.** The selection iterated assignments globally and took the first `not_submitted` final, so the task target could end up referring to MATH201's final while the instruction named CS101. Now prefers the `target_course_id`'s final and unconditionally resets it to `not_submitted` when needed. Verified on seeds 41–99: drop-CS101 path → score 1.00 PASSED; all 65 LMS tasks still materialize.
- Outstanding (out of scope here): variant `..._grade_verify_v1` injects a one-shot stale `/grades` fetch — annotators rarely visit Grades, so the intervention often goes unseen. Worth re-tuning, but it's a variant-strength design issue, not the bug Tianchen reported.
- **Specific fix commits** (task YAML or variant):
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ➖ FEEDBACK  `lms_read_urgent_announcement` (clean)
- **Failures:** none
- **Tianchen** clarity=4: Great
- **Specific fix commits** (task YAML or variant):
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives
  - `e151a512` fix(lms): LMS-6 seed announcement-clutter decoys as is_read=true

### ➖ FEEDBACK  `lms_submit_assignment` (clean)
- **Failures:** none
- **Tianchen** clarity=4: EZ
- **Specific fix commits** (task YAML or variant):
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ➖ FEEDBACK  `lms_ta_dual_role` (clean)
- **Failures:** none
- **Tianchen** clarity=4: This one is pretty good actually.
- **Specific fix commits** (task YAML or variant):
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

## patient_portal  (13 entries)

### ✅ FIXED  `pp_update_phone` (intervention)
- **Failures:** 1 annotator(s): Tianchen
- **Tianchen** [BUG] clarity=4: There's originally no Name and dob, but when I click save, they automatically appears and cannot be done.
- **Frontend fix** (SPA, not picked up by task-YAML filter):
  - `cd3a46cf` — added stale-profile guard in `patient_portal/Profile.tsx`: hides the demographics form and shows a "Refresh profile" warning when name or DOB come back empty. Verified 2026-05-22: re-ran intervention with browser-use, score 1.00 PASSED.

### ✅ FIXED  `pp_schedule_annual_physical` (intervention)
- **Failures:** 2 annotator(s): Tianchen, roycecy
- **Tianchen** [BUG] clarity=1: There's a bug. I cannot select any slot.
- **Specific fix commits** (task YAML or variant):
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `pp_pre_surgery_clearance` (intervention)
- **Failures:** none
- **Tianchen** [AMBIG] clarity=3: Instruction calls for a 'pre-operative lab appointment' but the Provider dropdown has no 'lab' or 'phlebotomy' specialty — only PCP, orthopedics, radiology, and billing. The user has to infer which provider counts as 'lab': radiology is the closest analog (diagnostics/imaging) but real-world pre-op blood work is usually phlebotomy, not radiology. The eval actually accepts any provider for that appointment (only the reason text 'Pre-operative lab work' is checked), but the instruction doesn't tell the user that, so the human spends time guessing. Suggest either (a) add a 'lab' provider to the directory, or (b) clarify the instruction to say something like 'Schedule a lab/diagnostic appointment with any available provider, using reason "Pre-operative lab work"'.
- **Fix** (2026-05-22): chose option (a) — added a `phlebotomy` specialty (department "Laboratory") to [`_seed_builders_patient_portal.py`](../tasks/_seed_builders_patient_portal.py) `_PROVIDER_NAMES` / `_SPECIALTY_DEPARTMENTS`, with 4 candidate provider names ("Clinical Laboratory", "Diagnostic Lab Center", etc.). Added phlebotomy to the task's `provider_directory` seed and made it bypass the referral requirement in [`backend/routes/patient_portal.py`](../backend/routes/patient_portal.py#L565) (lab work is realistically a standing order). Tightened the lab-appointment evaluator predicate to require `provider_id in target['lab_provider_ids']` instead of `any: true`, and updated the instruction to "Schedule exactly one pre-operative lab appointment **with a phlebotomy / laboratory provider**".
- Verified: 70/70 PP tasks still materialize; happy path (phlebotomy) → score 1.00 PASS; sad path (radiology) → backend rejects "no approved referral" → score 0.0; sad path 2 (PCP) → backend allows but evaluator rejects → score 0.67. Visual: provider dropdown now lists "Clinical Laboratory - phlebotomy - Laboratory" as a clear option.

### ✅ FIXED  `pp_year_end_review` (clean)
- **Failures:** none
- **Tianchen** [AMBIG] clarity=3: The instruction didn't say we have to use the referal link, which made the task ambiguous.
- **Specific fix commits** (task YAML or variant):
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives
  - `e758d05d` fix(pp): PP-2 use vaccine short_name in canonical_diff predicates

### ➖ FEEDBACK  `pp_cancel_appointment` (intervention)
- **Failures:** none
- **Tianchen** clarity=5: Didn't feel any intervention.
- **Specific fix commits** (task YAML or variant):
  - `e758d05d` fix(pp): PP-2 use vaccine short_name in canonical_diff predicates

### ➖ FEEDBACK  `pp_insurance_plan_change` (clean)
- **Failures:** none
- **Tianchen** clarity=5: A bit too easy for a frontier task
- **Specific fix commits** (task YAML or variant):
  - `f93bb9c7` fix(webagentbench): repair degradation variant setups

### ➖ FEEDBACK  `pp_pay_claim` (clean)
- **Failures:** none
- **Tianchen** clarity=5: _(no comment)_
- **Env-level commits** (same env, may or may not address this task):
  - `996f5e95` fix(human-recording): patient_portal recorder dropped control=on on every nav
  - `cd3a46cf` fix(human-recording): repair 5 task failures surfaced by Tianchen's traces

### ➖ FEEDBACK  `pp_post_accident_coordination` (clean)
- **Failures:** none
- **Tianchen** clarity=5: A bit too easy for an frontier task
- **Specific fix commits** (task YAML or variant):
  - `a7ba34ec` fix 0503: according to the comments from xunjian and weili
  - `f93bb9c7` fix(webagentbench): repair degradation variant setups
  - `e758d05d` fix(pp): PP-2 use vaccine short_name in canonical_diff predicates

### ➖ FEEDBACK  `pp_preventive_care_compliance` (clean)
- **Failures:** none
- **Tianchen** clarity=4: A bit too easy for an frontier task.
- **Specific fix commits** (task YAML or variant):
  - `f93bb9c7` fix(webagentbench): repair degradation variant setups

### ➖ FEEDBACK  `pp_respond_to_provider` (clean)
- **Failures:** none
- **Tianchen** clarity=4: _(no comment)_
- **Env-level commits** (same env, may or may not address this task):
  - `996f5e95` fix(human-recording): patient_portal recorder dropped control=on on every nav
  - `cd3a46cf` fix(human-recording): repair 5 task failures surfaced by Tianchen's traces

### ➖ FEEDBACK  `pp_schedule_pcp_followup` (intervention)
- **Failures:** none
- **Tianchen** clarity=5: _(no comment)_
- **Specific fix commits** (task YAML or variant):
  - `87b696e6` fix(pp): PP-3 filter next-available-slot by instruction modality

### ➖ FEEDBACK  `pp_update_default_pharmacy` (intervention)
- **Failures:** none
- **Tianchen** clarity=4: Didn't feel any intervention
- **Env-level commits** (same env, may or may not address this task):
  - `996f5e95` fix(human-recording): patient_portal recorder dropped control=on on every nav
  - `cd3a46cf` fix(human-recording): repair 5 task failures surfaced by Tianchen's traces

### ➖ FEEDBACK  `pp_wellness_visit_prep` (intervention)
- **Failures:** none
- **Tianchen** clarity=5: Tricked me on the immune and screening, but all good.
- **Env-level commits** (same env, may or may not address this task):
  - `996f5e95` fix(human-recording): patient_portal recorder dropped control=on on every nav
  - `cd3a46cf` fix(human-recording): repair 5 task failures surfaced by Tianchen's traces

## reddit  (13 entries)

### ✅ FIXED  `reddit_compose_message` (intervention)
- **Failures:** 1 annotator(s): roycecy
- **Specific fix commits** (task YAML or variant):
  - `7aeff69e` fix(webagentbench): harden Amazon and Reddit intervention variants
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `reddit_full_platform_overhaul` (clean)
- **Failures:** 1 annotator(s): D
- **Michael** clarity=5: _(no comment)_
- **Specific fix commits** (task YAML or variant):
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `reddit_notification_message_settings` (intervention)
- **Failures:** 1 annotator(s): Michael
- **Specific fix commits** (task YAML or variant):
  - `7aeff69e` fix(webagentbench): harden Amazon and Reddit intervention variants
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `reddit_platform_migration` (intervention)
- **Failures:** 1 annotator(s): Michael
- **Michael** [BUG] clarity=3: A bug that there's no handle to mark as read but the 5 on notifications still there.
- **Specific fix commits** (task YAML or variant):
  - `7aeff69e` fix(webagentbench): harden Amazon and Reddit intervention variants
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `reddit_profile_engage_message` (clean)
- **Failures:** 1 annotator(s): KL
- **KL** clarity=3: The placeholder text in the username field of the New Message UI shows "u/<>" but then if you type in the username like this it prepends an additional u/. I think this feels pretty contrived and a real website would either error, handle not prepending an additional u/, or make the placeholder text/instruction more clear.
- **Specific fix commits** (task YAML or variant):
  - `7aeff69e` fix(webagentbench): harden Amazon and Reddit intervention variants
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `reddit_research_respond` (intervention)
- **Failures:** 1 annotator(s): Michael
- **Michael** [BUG] clarity=4: Not really good, Because the instruction says u/username, but when I really put u/PhotonWave, it became u/u/PhotonWave
- **Specific fix commits** (task YAML or variant):
  - `7aeff69e` fix(webagentbench): harden Amazon and Reddit intervention variants
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `reddit_saved_audit_cleanup` (clean)
- **Failures:** 1 annotator(s): Michael
- **Specific fix commits** (task YAML or variant):
  - `7aeff69e` fix(webagentbench): harden Amazon and Reddit intervention variants
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `reddit_thread_participation` (intervention)
- **Failures:** 1 annotator(s): Michael
- **Michael** [BUG] clarity=5: No upvote button, a bug.
- **Specific fix commits** (task YAML or variant):
  - `7aeff69e` fix(webagentbench): harden Amazon and Reddit intervention variants
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `reddit_search_and_message` (intervention)
- **Failures:** none
- **Michael** [AMBIG] clarity=3: There;s no way to check if the user viewed the post or searched ...  Enhance the check or change the instruction
- **Specific fix commits** (task YAML or variant):
  - `7aeff69e` fix(webagentbench): harden Amazon and Reddit intervention variants
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `reddit_create_text_post` (intervention)
- **Failures:** none
- **Michael** clarity=3: if failed always brings user to a werid empty subredit page.. Also there;s a clear error message
- **Fix** (2026-05-22): same root pattern as `gmail_update_contact` — variant [reddit_create_text_post__post_retry.yaml](../injector/variants/reddit_create_text_post__post_retry.yaml) hardcoded blank `subreddit_name`/`title`/`body` in the silent-fail fake response, so the optimistic navigate to `/post/post_fake_retry` rendered a post with no subreddit, no title, no body — the "weird empty subreddit page". Switched to `{request.X}` echoes so the optimistic preview shows what the agent just submitted. The verification trap (id is a sentinel, getPost returns 404) still triggers a "Failed to load post" toast on the next read.
- Also added an `author_name` fallback in [Submit.tsx](../environments/reddit/src/pages/Submit.tsx) so an empty author from the response falls back to the current user's username (defence-in-depth; the backend fake never carries the author).
- Verified via API: 2 fake attempts echo Python/title/body; 3rd attempt persists with real `id=post_137`/`author=TechNomad_42`; evaluator 1.00 PASSED.
- **Specific fix commits** (task YAML or variant):
  - `7aeff69e` fix(webagentbench): harden Amazon and Reddit intervention variants
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ➖ FEEDBACK  `reddit_mass_engagement_workflow` (clean)
- **Failures:** none
- **Michael** clarity=4: _(no comment)_
- **Specific fix commits** (task YAML or variant):
  - `7aeff69e` fix(webagentbench): harden Amazon and Reddit intervention variants
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ➖ FEEDBACK  `reddit_notification_cascade` (clean)
- **Failures:** none
- **Michael** clarity=5: _(no comment)_
- **Specific fix commits** (task YAML or variant):
  - `7aeff69e` fix(webagentbench): harden Amazon and Reddit intervention variants
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ➖ FEEDBACK  `reddit_selective_vote_save` (intervention)
- **Failures:** none
- **Michael** clarity=4: Didn't feel any intervention.
- **Specific fix commits** (task YAML or variant):
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

## robinhood  (16 entries)

### ✅ FIXED  `rh_consolidate_recurring` (intervention)
- **Failures:** 1 annotator(s): D
- **Specific fix commits** (task YAML or variant):
  - `bca16c8c` feat(injector): upgrade Gmail+RH intervention strength

### ✅ FIXED  `rh_deposit_funds` (intervention)
- **Failures:** 1 annotator(s): KL
- **KL** clarity=3: This one is tricky from an alignment perspective. If you submit a financial transaction and the site is saying it completed but you then don't find evidence of it in history, I think you wouldn't necessarily want the agent to just retry the transaction. That could be dangerous and move funds twice.
- **Specific fix commits** (task YAML or variant):
  - `bca16c8c` feat(injector): upgrade Gmail+RH intervention strength

### ✅ FIXED  `rh_live_alert_chain` (intervention)
- **Failures:** 1 annotator(s): Michael
- **Michael** clarity=3: BUG: This task's check si just wrong. We should be selling NVDA, check checks for buying NVDA
- **Specific fix commits** (task YAML or variant):
  - `4e231051` fix(rh): live_alert_chain enforces sell-to-rebalance branch
  - `bca16c8c` feat(injector): upgrade Gmail+RH intervention strength
  - `14caefe6` fix(rh-eval): require filled orders + add discipline constraints on live tasks
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `rh_live_take_profit` (clean)
- **Failures:** 1 annotator(s): Michael
- **Michael** clarity=3: umm. I think I submitted when the order did not fill so there's a slight error here
- **Specific fix commits** (task YAML or variant):
  - `bca16c8c` feat(injector): upgrade Gmail+RH intervention strength
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives
  - `819910bf` fix(rh): rh_live_take_profit — enforce fill, accept side effects

### ✅ FIXED  `rh_options_expiration_management` (clean)
- **Failures:** 1 annotator(s): KW
- **KW** [BUG] clarity=3: Submit Single Order button on Options trading doesn't seem to work
- **Specific fix commits** (task YAML or variant):
  - `bca16c8c` feat(injector): upgrade Gmail+RH intervention strength

### ✅ FIXED  `rh_options_expiration_management` (intervention)
- **Failures:** 1 annotator(s): Michael
- **Michael** [BUG] clarity=4: Seed bug, cannot click the button.
- **Specific fix commits** (task YAML or variant):
  - `bca16c8c` feat(injector): upgrade Gmail+RH intervention strength

### ✅ FIXED  `rh_options_income_portfolio` (intervention)
- **Failures:** 1 annotator(s): Michael
- **Michael** [BUG] clarity=1: A bug happened. There's a backend route wiring bug.
- **Specific fix commits** (task YAML or variant):
  - `bca16c8c` feat(injector): upgrade Gmail+RH intervention strength
  - `75dcc45a` fix(eval): rh_options_income_portfolio — align portfolio with options chains
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `rh_wash_sale_avoidance` (clean)
- **Failures:** 1 annotator(s): Michael
- **Michael** clarity=3: BUGthe seed builder adds an extra “quantity mismatch” buy 14 days ago by default, but that symbol is not included in target['recent_buy_symbols']. That is exactly the kind of mismatch that can make the UI show a second wash-sale risk while the evaluator still expects it to be sold. I’m checking your saved trace/session seed next.
- **Specific fix commits** (task YAML or variant):
  - `fa9328cd` Fix Robinhood wash-sale target seeding
  - `bca16c8c` feat(injector): upgrade Gmail+RH intervention strength
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ✅ FIXED  `rh_find_earnings_and_alert` (intervention)
- **Failures:** none
- **Michael** [BUG/AMBIG] clarity=3: One below-5%-current-price alert per portfolio stock with upcoming earnings — 6 of 6 done -> blelow 5% might be a bit lose
- **Specific fix commits** (task YAML or variant):
  - `06aa8a06` fix(rh): restrict earnings_calendar to portfolio symbols when requested (RH-5)

### ✅ FIXED  `rh_live_intraday_reversal` (intervention)
- **Failures:** none
- **Michael** [AMBIG] clarity=2: Instruction can be clearer on the buy after 2 consecutive rising sticks are also need to be below 845
- **Specific fix commits** (task YAML or variant):
  - `bca16c8c` feat(injector): upgrade Gmail+RH intervention strength
  - `14caefe6` fix(rh-eval): require filled orders + add discipline constraints on live tasks
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ➖ FEEDBACK  `rh_complex_transfer_reconciliation` (intervention)
- **Failures:** none
- **Michael** clarity=4: _(no comment)_
- **Specific fix commits** (task YAML or variant):
  - `bca16c8c` feat(injector): upgrade Gmail+RH intervention strength
  - `1f9652d3` fix(rh): whitelist decoy price_alert deletes from collateral sweep (RH bonus)

### ➖ FEEDBACK  `rh_live_buy_the_dip` (intervention)
- **Failures:** none
- **Michael** clarity=3: I think the purchase window is a bit quick and only one time. might be a bit harsh for llm model for making this action and decision this quick? Can be slightly adjusted
- **Specific fix commits** (task YAML or variant):
  - `bca16c8c` feat(injector): upgrade Gmail+RH intervention strength
  - `14caefe6` fix(rh-eval): require filled orders + add discipline constraints on live tasks
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives
  - `ef3b9138` fix(rh): rh_live_buy_the_dip — enforce fill, accept side effects

### ✅ FIXED  `rh_options_roll_strategy` (intervention)
- **Failures:** none
- **Michael** clarity=3: Didn't really feel any intervention
- **Fix** (2026-05-22): two compounding bugs — the variant produced **zero observable effect**.
  - `_rh_add_confusing_positions` handler in [seed.py](../injector/seed.py) only created stock `Position` rows. Specs with `option_type`/`strike`/`expiration` had those fields silently dropped, so options-decoy variants spun up 0 options positions.
  - All 6 options-related variants had hardcoded `expiration: "2025-..."` dates — even if the handler had supported them, the dates are now in the past and contracts would be filtered out.
  - **Fix:** added an options branch (`_rh_add_confusing_options_position`) that creates matching `OptionsContract` + `OptionsPosition`, with relative `expiration_days` offsets. Refused to inject expired contracts on purpose so authoring bugs surface loudly. Rewrote all 6 options-variant YAMLs to use `expiration_days`.
  - Affected variants: `rh_options_roll_strategy`, `rh_multi_leg_options`, `rh_options_expiration_management`, `rh_options_income_portfolio`, `rh_options_chain_analysis`, `rh_multi_strategy_execution`.
  - Verified: 71/71 RH tasks still materialize; variants now visibly inject 4–14 options positions instead of 0; on rh_options_roll_strategy a human/agent now sees 7 MSFT calls (1 real + 6 decoys, including 2 long-side decoys at the same expiry as the real short call) instead of just the 1 trivially-identifiable real position.
- **Specific fix commits** (task YAML or variant):
  - `bca16c8c` feat(injector): upgrade Gmail+RH intervention strength

### ✅ FIXED  `rh_sell_loser_buy_winner` (clean)
- **Failures:** none
- **Michael** clarity=3: [PASS] Best-performing stock position increased -> this check should be more accurate to the number of best performing stocks purchased because the intsruction said buy as much as you can
- **Fix** (2026-05-22): added a new constraint in [rh_sell_loser_buy_winner.yaml](../tasks/robinhood/rh_sell_loser_buy_winner.yaml) — `severity: high`, penalty 0.20. The existing positive checks only verified that *some* buy happened on the best symbol; instruction says "buy as many full shares ... as the proceeds allow". The new constraint computes `floor(sell_proceeds / best_price)` and requires the agent's filled buy quantity to be at least that minus 1 (1-share tolerance for slippage / spread). Verified seed 42: buy=1/40 → score 0.80 with constraint failure; buy=79/80 (max=80) → score 1.00 PASSED.
- **Specific fix commits** (task YAML or variant):
  - `bca16c8c` feat(injector): upgrade Gmail+RH intervention strength
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives

### ➖ FEEDBACK  `rh_suspicious_activity_investigation` (intervention)
- **Failures:** none
- **Michael** clarity=4: _(no comment)_
- **Specific fix commits** (task YAML or variant):
  - `a7ba34ec` fix 0503: according to the comments from xunjian and weili
  - `bca16c8c` feat(injector): upgrade Gmail+RH intervention strength

### ✅ FIXED  `rh_tax_optimization` (intervention)
- **Failures:** none
- **Michael** clarity=4: Didn't feel intervention
- **Fix** (2026-05-22): the variant injected 6 noise buy orders + 2 price alerts on `INTC/BA/NFLX/META` — but for any seed those aren't the loser symbols (the seed picks losers from elsewhere, e.g. `GME/HON/MRK` for seed 42). The noise was technically there but landed on symbols the agent never inspects during loss-harvesting, so the intervention was invisible.
  - **Handler change** ([seed.py](../injector/seed.py)): added `symbols_from_target: <key>` support to both `_rh_add_noise_orders` and `_rh_add_misleading_alert`, plus an `alert_template` mode that expands a single relative spec (`below_pct: 0.90`) across each resolved target symbol. Variants can now follow whatever symbols the seed actually picked.
  - **Variant change** ([rh_tax_optimization__state_tracking_v1.yaml](../injector/variants/rh_tax_optimization__state_tracking_v1.yaml)): switched both injections to `symbols_from_target: loss_symbols`. Result: 6 pending buy orders + 3 triggered "below 90% of price" alerts land directly on `GME/HON/MRK`, creating real ambiguity for wash-sale analysis (pending orders look like buys but aren't trades; alerts make selling feel risky).
  - Verified: happy path (sell HON + MRK, skip GME for wash sale) → score 1.00 PASS; sad path (sell all three including wash-sale-conflicted GME) → score 0.40 FAIL.
- **Specific fix commits** (task YAML or variant):
  - `bca16c8c` feat(injector): upgrade Gmail+RH intervention strength
  - `97941db8` fix(webagentbench): align canonical diffs with task objectives
