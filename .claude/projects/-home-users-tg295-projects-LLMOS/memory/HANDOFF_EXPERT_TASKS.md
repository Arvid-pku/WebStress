# WebAgentBench Expert Tasks — Handoff

You are continuing systematic UI-verification of booking.com benchmark tasks. The prior agent tested 20+ tasks, fixed several task/site bugs, and now hands off the remaining **expert** difficulty tasks for you to test.

## Environment

- **Working dir**: `/home/users/tg295/projects/LLMOS`
- **Dev server**: runs on `http://localhost:8084/launch` (Booking env). User is SSH-tunneled to this port. Uvicorn backend is on `:8080`, Vite dev server for booking is on `:8084`.
- **Git branch**: `main`
- **User**: Tianchen Guan (Duke CS researcher, SSH session on compsci-login node). Workflow preference: **when eval fails, discuss with user first** to determine website bug vs. agent error before fixing. Do not silently apply fixes.
- **Today**: 2026-04-18

## Your task list (test these, in order)

All are `difficulty: expert`. **Skip** the two already done: `booking_expert_review_marathon`, `booking_expert_complete_account_review`.

1. `booking_expert_reservation_audit`
2. `booking_expert_cancel_chain`
3. `booking_expert_rebooking_workflow`
4. `booking_expert_compare_and_decide`
5. `booking_expert_account_migration`
6. `booking_expert_settings_and_security`
7. `booking_expert_family_vacation`
8. `booking_expert_deal_hunter`
9. `booking_expert_loyalty_optimizer`
10. `booking_expert_message_concierge`
11. `booking_expert_travel_planner`
12. `booking_expert_multi_city_booking`
13. `booking_expert_notification_workflow`

Read each task's YAML at `webagentbench/tasks/booking/<task_id>.yaml` first to understand the goal, constraints, and seed data.

## Verification protocol — MUST USE UI

The prior agent was criticized for using the API to shortcut actions. The user's rule: **tasks must be solvable by a human via the UI**. API calls can hide UI/UX bugs that would block a real user.

**Required flow per task**:

1. Navigate to `http://localhost:8084/launch` via `mcp__browser-use__browser_navigate`
2. Type task name fragment into the search input, click the task row, click **Launch**
3. Perform every step via `mcp__browser-use__browser_click` / `browser_type` / `browser_get_state`. The API is only for **read-only inspection** (curl to check state after UI action) — never for state changes.
4. Click the floating **WAB** button (bottom-right), then **Evaluate** in the panel that opens.
5. Screenshot the result and report score.

**If a step can't be completed via the UI**: STOP and ask the user. Don't assume it's a task bug. It might be:

- Your misunderstanding of the UI (ask a question)
- A real site bug needing a fix (discuss with user before fixing)
- Browser-use limitation (e.g., element index quirks, need to scroll first)

## Known bug pattern — review tasks

**Pattern**: Tasks that write a review for a completed reservation tend to fail with `[FAIL] Agent did not modify reservations` because writing a review flips `rating_submitted: False → True` on the underlying reservation, which trips an unfiltered `state.reservations preserve: ALL` invariant.

**Fix template** (apply only after discussing with user):

```yaml
seed:
  targets:
    # ... existing targets ...
    res_id_X: '{output.res_id_X}'   # add for each reviewed reservation
canonical_diff:
  update:                            # ADD this block if missing
    - entity: Reservation
      desc: Review submission flips rating_submitted on the reviewed reservation
      where:
        id: {expr: "x == target['res_id_X']"}
      changes:
        rating_submitted: {any: true}
  # ... existing create ...
  invariant:
    - collection: state.reservations
      filter: "a.id not in (target['res_id_1'], target['res_id_2'], ...)"  # EXCLUDE reviewed
      preserve: ALL
```

**Critical**: the `state.reservations preserve: ALL` invariant MUST have a filter that excludes the IDs in the update entries. Otherwise the task registry validator refuses to load the task with `ValueError: invariant on 'state.reservations' overlaps with positive diff target and has no filter`, which makes uvicorn crash on startup and the dev server stops responding entirely.

Other task/site bugs the prior agent fixed in this codebase:
- `environments/booking/src/pages/SearchResults.tsx:56`: amenity label `"Swimming Pool"` → `"Pool"` (matches seed data)
- `environments/booking/src/pages/Settings.tsx:563-596`: dietary restrictions now store lowercase values via `{label, value}` pairs
- `backend/seeders/booking.py:222`: `base["id_counters"]["pm"] = len(base.get("payment_methods", []))` in `_sync_id_counters`
- `booking_full_account_setup.yaml`: update entry for `is_default` flip when setting new default card

## Backend reload — critical

After editing a YAML task file, trigger uvicorn reload with:
```bash
touch /home/users/tg295/projects/LLMOS/webagentbench/backend/seeders/booking.py
```

Then **wait for reload to finish** before creating a new session. Use:
```bash
until curl -sS --max-time 3 -X POST "http://localhost:8084/api/env/booking/session" \
  -H "Content-Type: application/json" \
  -d '{"task_id":"<task_id>"}' 2>/dev/null | grep -q session_id; do sleep 3; done
```
Reload can take 60–120 seconds (task registry validates all YAMLs). If the server goes to connection-refused, a YAML you wrote has a validation error; fix it and tell user to re-run `./scripts/webagentbench.sh dev --env booking`.

Vite hot-reloads `.tsx` automatically. `.py` and `.yaml` require the touch above.

## Browser-use MCP quirks

Full skill at `~/.claude/skills/browser-use-mcp/SKILL.md`. Key points:

- **First call may time out** with `BrowserStartEvent#XXX timed out after 30.0s` due to stale Singleton lock files from prior SSH sessions on NFS-shared `$HOME`. Fix:
  ```bash
  rm ~/.config/browseruse/profiles/default/Singleton{Lock,Cookie,Socket}
  ```
  Then ask the user to **reconnect the MCP** via `/mcp → Reconnect`. Retry after reconnect.

- **HTML5 date inputs**: must type in `YYYY-MM-DD` format (not `MM/DD/YYYY`).
- **`<select>` elements**: use `browser_type` with the option **value** (e.g. type `"1"` to select `<option value="1">`). There is no `browser_select_option`.
- **Deferred tool loading**: browser-use tools appear as names only. Before first use, load schemas via `ToolSearch` with `query: "select:mcp__browser-use__browser_navigate,mcp__browser-use__browser_click,mcp__browser-use__browser_type,mcp__browser-use__browser_get_state,mcp__browser-use__browser_screenshot,mcp__browser-use__browser_scroll,mcp__browser-use__browser_extract_content"`.
- **Date display quirk**: property/booking pages parse `new Date("2026-08-15")` as UTC midnight and display as "Aug 14" in negative-offset timezones. URL/backend values remain correct (`YYYY-MM-DD`), evals pass. Don't chase this cosmetic issue.
- **Reservation/booking page note**: clicking "Reserve" on a property page without first entering check-in/check-out dates creates a 1-night booking (URL missing date params). Always set dates on the property page before clicking Reserve.

## Per-task reporting format

For each task, report:
- **Title + task_id**
- **Seed targets / decoys identified** (which property is the true target, which are distractors)
- **UI steps performed** (e.g., "Searched Paris → filtered 4★+Pool → clicked See availability on Le Marais Grand Hotel → set dates → Reserve → filled guest info → Complete Booking")
- **Eval result** (score, pass/fail summary)
- If failed, **hypothesis** (what tripped, why, which layer) — and **stop for user confirmation before fixing**

## Read-only API inspection cheat sheet

```bash
SID="booking_..."  # from URL after launch
B="http://localhost:8084/api/env/booking"

curl -s "$B/reservations?session_id=$SID" | python3 -m json.tool
curl -s "$B/reservations/res_1?session_id=$SID" | python3 -m json.tool
curl -s "$B/payment-methods?session_id=$SID" | python3 -m json.tool
curl -s "$B/settings?session_id=$SID" | python3 -m json.tool
curl -s "$B/preferences?session_id=$SID" | python3 -m json.tool
curl -s "$B/notifications?session_id=$SID" | python3 -m json.tool
curl -s "$B/messages?session_id=$SID" | python3 -m json.tool
curl -s "$B/saved-lists?session_id=$SID" | python3 -m json.tool
curl -s "$B/reviews?session_id=$SID" | python3 -m json.tool
curl -s "$B/properties/<prop_id>?session_id=$SID" | python3 -m json.tool

# Dump eval result (useful for exact failure messages)
curl -s -X POST "$B/evaluate" -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SID\"}" | python3 -m json.tool
```

**DO NOT** use POST/PUT/DELETE to drive task state — that defeats the UI-solvability requirement. Use the browser.

## Memory system note

`~/.claude/projects/-home-users-tg295-projects-LLMOS/memory/` holds user/project memory. Update `MEMORY.md` as you discover new facts. See the auto-memory instructions in your system prompt.

## Start here

Begin with `booking_expert_reservation_audit`. Read its YAML, launch via UI, drive through the workflow, eval. Report back.

## Pending YAML-fix retest queue

Tasks where a YAML fix was applied during this session but **not yet re-verified** because a fresh uvicorn reload / dev-server restart is needed. After restarting, re-launch each and run WAB Evaluate to confirm 1.00.

- `booking_expert_compare_and_decide` — applied review-task fix (2026-04-18): added `completed_res_id` target, added `update` block flipping `rating_submitted` on the Savoy reservation, and extended the `state.reservations` invariant filter to exclude `completed_res_id`. Original eval was 0.85 (penalty −0.15 from "Unaccounted update in reservations (id=res_1)" — standard review-flip pattern).
- `booking_expert_account_migration` — applied card-type normalization fix (2026-04-18): changed `card_type: {eq: "American Express"}` → `card_type: {eq: "Amex"}` in the Amex create check. Root cause: site dropdown option label is "American Express" but backend stores as "Amex" (consistent with pre-existing pm_3 card). Original eval was 0.60 — positive check failed + "Unaccounted create in payment_methods (id=pm_7)" (−0.20). Everything else passed (profile edits, Visa 6666 default, Alex 5555 exp 03/27 removed while baseline Alex 5555 exp 01/30 preserved).

## Site fixes applied this session (Vite hot-reloaded, no restart needed)

- `environments/booking/src/pages/Settings.tsx` (2026-04-18): added "Preferred Room Type" select (No preference/Standard/Deluxe/Suite/Family) and wired it into `handleSavePreferences`. Root cause: `preferred_room_type` was a state field with no UI control, so the `preferred_room_type == 'family'` constraint in `booking_expert_family_vacation` could not be satisfied via UI. After the fix + re-save, the task re-evaluated to 1.00 in the same session.
- `environments/booking/src/pages/Settings.tsx` (2026-04-18): added "Preferred Currency" select (No preference/USD/EUR/GBP/JPY) under Travel Preferences and wired `preferred_currency` into `handleSavePreferences` + `api.updatePreferences`. Root cause: site had two currency concepts — `settings.currency` (bound to the Language & Currency section's USD/EUR/… dropdown) and `travel_preferences.preferred_currency` (no UI). Evals using the latter (e.g. `booking_expert_loyalty_optimizer`'s "Preferred currency updated to EUR" constraint) could not pass without this control.

## Backend fixes applied this session (REQUIRES UVICORN RESTART to take effect)

- `backend/routes/booking.py` (2026-04-18): rewrote `POST /wallet/apply` from a no-op stub to an actual implementation that deducts from `state.wallet.balance` via `state.use_wallet_credit(amount, description)`. Accepts optional `reservation_id` (for description label) and `amount` (defaults to full balance, clamped). Root cause: the `booking_expert_loyalty_optimizer` task has a "wallet credit was applied" constraint but the previous endpoint just echoed the balance and returned a message without mutating. Also added `api.applyWallet()` + an "Apply Wallet Credit" button on the `ReservationDetail.tsx` Actions card so a user can trigger it from /trips/{res_id}. Note: changes to routes/booking.py require `touch webagentbench/backend/seeders/booking.py` + uvicorn reload before they are live.

## Pending retest after backend restart (in addition to task 4, 5 earlier)

- `booking_expert_loyalty_optimizer` — original eval 0.65. Two failures: "Wallet credit was applied" (−0.15 medium) and "Preferred currency updated to EUR" (−0.20 high). Currency fix is frontend-only (already hot-reloaded). Wallet fix needs backend restart. To retest, relaunch, book target (Le Petit Belloy Saint-Germain prop_3 Comfort Room with Breakfast 2026-08-15→2026-08-20, 2 guests, Mastercard 8888), save to "Genius Picks", Settings → Preferred Currency=EUR + Save Preferences, Trips→res_X→**Apply Wallet Credit** button, then Evaluate.
- `booking_expert_message_concierge` — applied YAML fix (2026-04-18): (a) added a wildcard `update` entry `where: {sender: {eq: property}} changes: {read: {any: true}}` at the top of `canonical_diff.update` to permit read-flips on any property-origin message while the user browses the inbox (otherwise the `state.messages preserve: ALL` invariant trips for msg_initial_* distractors the user opens while locating targets, and also for any mistake-replies the agent sent to target hotels). (b) Reworded step 5 of `instruction_template` from "add 'spa' to your accessibility needs" → "enable accessibility needs" since `accessibility_needs` is a boolean in state with no per-item UI. Original eval was 0.70 on both the prior agent and me (msg_initial_11/12 from opening distractors, or msg_19/20 from mis-threaded replies). Retest: replicate the run, expect 1.00.
- `booking_expert_travel_planner` — applied review-flip fix (2026-04-18): added `review_res_id` target, added `update` block flipping `rating_submitted` on the reviewed Hotel Lumiere Paris reservation, extended `state.reservations` invariant filter to `a.property_id != target['cheapest_id'] and a.id != target['review_res_id']`. Confirmed the bug by running: 0.85 with single penalty "Unaccounted update in reservations (id=res_1)". Same pattern as task 4. Retest: replicate the run (book Shinjuku Granbell Tokyo 2026-10-01→2026-10-05, save all 3 to "World Tour", write Hotel Lumiere Paris review), expect 1.00.
